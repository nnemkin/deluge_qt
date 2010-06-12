#
# add_torrents_dialog.py
#
# Copyright (C) 2010 Nikita Nemkin <nikita@nemkin.ru>
#
# This file is part of Deluge.
#
# Deluge is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Deluge. If not, see <http://www.gnu.org/licenses/>.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#

import os
import base64

from PyQt4 import QtGui, QtCore
from twisted.internet import defer

import deluge.common
from deluge.log import LOG as log
from deluge.ui.client import client
from deluge.ui.common import TorrentInfo
from deluge.configmanager import ConfigManager

from .generated.ui import Ui_AddTorrentsDialog, Ui_AddHashDialog, Ui_AddUrlDialog
from .ui_tools import HeightFixItemDelegate
from .ui_common import WidgetLoader, FileModel


class AddTorrentsDialog(QtGui.QDialog, Ui_AddTorrentsDialog):

    _core_keys_to_torrent_keys = {"download_location": "download_location",
                                  "compact_allocation": "compact_allocation",
                                  "max_connections_per_torrent": "max_connections",
                                  "max_upload_slots_per_torrent": "max_upload_slots",
                                  "max_download_speed_per_torrent": "max_download_speed",
                                  "max_upload_speed_per_torrent": "max_upload_speed",
                                  "prioritize_first_last_pieces": "prioritize_first_last_pieces",
                                  "add_paused": "add_paused"}

    def __init__(self, parent):
        super(AddTorrentsDialog, self).__init__(parent, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)

        self.ui_config = ConfigManager("qtui.conf")
        self.default_options = {}
        self._selected_item = None

        self.download_location_browse.setVisible(client.is_localhost())

        self.EMPTY_FILE_MODEL = TorrentFileModel([], self)
        self.tree_files.setModel(self.EMPTY_FILE_MODEL)
        header = self.tree_files.header()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(header.fontMetrics().width("M") * 10)
        header.setResizeMode(0, QtGui.QHeaderView.Stretch)
        header.setResizeMode(1, QtGui.QHeaderView.Fixed) # NB: ResizeToContents is slow

        HeightFixItemDelegate.install(self.tree_files)

        self._update_default_options()

    @defer.inlineCallbacks
    def _update_default_options(self):
        core_config = yield client.core.get_config_values(self._core_keys_to_torrent_keys.keys())
        self.default_options = dict((self._core_keys_to_torrent_keys[k], v) for k, v in core_config.items())

    def torrents(self):
        return [self.list_torrents.item(i) for i in xrange(self.list_torrents.count())]

    @defer.inlineCallbacks
    def add_url(self, url):
        import tempfile, urlparse
        tmp_file = urlparse.urlsplit(url).path
        if tmp_file and tmp_file[-1] != "/":
            tmp_file = os.path.join(tempfile.gettempdir(), tmp_file.split("/")[-1]) # XXX: temp file name important?
        else:
            (fd, tmp_file) = tempfile.mkstemp(".torrent", "deluge_")
            os.close(fd)
        log.debug("add_url temporary file: %s", tmp_file)

        dialog = QtGui.QProgressDialog("Deluge", _("Cancel"), 0, 0, minimumDuration=2, modal=True)

        def on_part(data, current_length, total_length):
            if dialog.wasCanceled():
                raise UserCancelledError() # XXX: how to stop download?
            if total_length:
                label = "%.2f%% (%s / %s)" % (100. * current_length / total_length,
                                              deluge.common.fsize(current_length),
                                              deluge.common.fsize(total_length))
                dialog.pyqtConfigure(value=current_length, maximum=total_length, labelText=label)
            else:
                dialog.setLabelText(deluge.common.fsize(current_length))

        import deluge.httpdownloader
        try:
            tmp_file = yield deluge.httpdownloader.download_file(url, tmp_file, on_part)
        except Exception:
            if not dialog.wasCanceled():
                dialog.reset()
                QtGui.QMessageBox.critical(self, _("Download Failed"), _("Failed to download : %s") % url,
                                  QtGui.QMessageBox.Close)
        else:
            self.add_torrents([tmp_file])

        dialog.deleteLater()
        # XXX: unlink tmp_file?

    def add_torrents(self, uris):
        """Handles lists of local filenames or magnet uris."""
        torrent = None
        for uri in uris:
            try:
                torrent = TorrentItem(uri)
            except Exception, e:
                log.debug("Unable to open torrent file: %s", uri, exc_info=True)
                QtGui.QMessageBox.critical(self, _("Invalid File"), unicode(e), QtGui.QMessageBox.Close)
            else:
                if torrent not in self.torrents():
                    self.list_torrents.addItem(torrent)
                else:
                    QtGui.QMessageBox.information(self, _("Duplicate Torrent"), _("You cannot add the same torrent twice."))

        if torrent:
            torrent.setSelected(True)

    def _save_options(self, torrent):
        torrent.options.update(WidgetLoader.from_widgets(self, self.default_options))

    def _load_options(self, torrent):
        WidgetLoader.to_widgets(torrent.options or self.default_options, self)
        self.tree_files.setModel(torrent.file_model)
        self.tree_files.expandToDepth(0)

    @QtCore.pyqtSlot()
    def on_button_file_clicked(self):
        filter = "%s (%s);;%s (%s)" % (_("Torrent files"), "*.torrent", _("All files"), "*")
        filenames = QtGui.QFileDialog.getOpenFileNames(self, _('Add File'), self.ui_config["default_load_path"], filter)
        if filenames:
            self.ui_config["default_load_path"] = os.path.dirname(filenames[0]) # XXX: ugly
            self.add_torrents(map(QtCore.QDir.toNativeSeparators, filenames))

    @QtCore.pyqtSlot()
    def on_button_url_clicked(self):
        dialog = QtGui.QDialog(self, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        try:
            dialog_ui = Ui_AddUrlDialog()
            dialog_ui.setupUi(dialog)

            url = QtGui.QApplication.clipboard().text()
            if deluge.common.is_url(url):
                dialog_ui.text_url.setText(url)

            if dialog.exec_():
                url = dialog_ui.text_url.text().strip()
                if deluge.common.is_url(url):
                    self.add_url(url)
                elif deluge.common.is_magnet(url):
                    self.add_torrents([url])
                else:
                    QtGui.QMessageBox.critical(self, _("Invalid URL"), _("%s is not a valid URL.") % url, QtGui.QMessageBox.Close)
        finally:
            dialog.deleteLater()

    @QtCore.pyqtSlot()
    def on_button_hash_clicked(self):
        dialog = QtGui.QDialog(self, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        try:
            dialog_ui = Ui_AddHashDialog()
            dialog_ui.setupUi(dialog)
            if dialog.exec_():
                infohash = dialog_ui.text_infohash.text().strip()
                trackers = dialog_ui.text_trackers.toPlainText().strip()
                trackers = [tracker for tracker in trackers.split("\n") if deluge.common.is_url(tracker)]
                magnet_url = deluge.common.create_magnet_uri(infohash, trackers=trackers)
                self.add_url(magnet_url)
        finally:
            dialog.deleteLater()

    @QtCore.pyqtSlot()
    def on_button_download_location_browse(self):
        directory = QtGui.QFileDialog.getExistingDirectory(self, directory=self.download_location.text())
        if directory:
            self.download_location.setText(directory)

    @QtCore.pyqtSlot()
    def on_button_remove_clicked(self):
        index = self.list_torrents.currentRow()
        if index != -1:
            self.list_torrents.takeItem(index)

    @QtCore.pyqtSlot()
    def on_button_revert_clicked(self):
        if self._selected_item:
            self._load_options(self._selected_item)

    @QtCore.pyqtSlot()
    def on_button_apply_to_all_clicked(self):
        options = WidgetLoader.from_widgets(self, self.default_options);
        for torrent in self.torrents():
            torrent.options.update(options)

    @QtCore.pyqtSlot()
    def on_list_torrents_itemSelectionChanged(self):
        if self._selected_item:
            self._save_options(self._selected_item)
        try:
            self._selected_item = self.list_torrents.selectedItems()[0]
        except IndexError:
            self._selected_item = None
            self.tree_files.setModel(self.EMPTY_FILE_MODEL)
        else:
            self._load_options(self._selected_item)

        self.tab_options.setEnabled(self._selected_item is not None)
        self.tab_files.setEnabled(self._selected_item is not None)

    @QtCore.pyqtSlot()
    def accept(self):
        self.list_torrents.clearSelection() # deselect to save data 

        for torrent in self.torrents():
            if deluge.common.is_magnet(torrent.filename):
                client.core.add_torrent_magnet(torrent.filename, torrent.options)
            else:
                torrent.options.update(torrent.file_model.file_options())
                client.core.add_torrent_file(torrent.filename, base64.encodestring(torrent.filedata), torrent.options)

        super(AddTorrentsDialog, self).accept()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_torrents([url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()])


class UserCancelledError(Exception):
    pass


class TorrentItem(QtGui.QListWidgetItem):

    def __init__(self, uri):
        super(TorrentItem, self).__init__(None)

        if deluge.common.is_magnet(uri):
            # TODO: better magnet parsing
            s = uri.split("&")[0][20:]
            if len(s) == 32:
                self.info_hash = base64.b32decode(s).encode("hex")
            elif len(s) == 40:
                self.info_hash = s

            for i in uri.split("&"):
                if i.startswith("dn="):
                    self.setText("%s (%s)" % (i[3:], uri))
                    break
            else:
                self.setText(uri)
        else:
            info = TorrentInfo(uri)
            self.filename = os.path.basename(uri)
            self.info_hash = info.info_hash
            self.filedata = info.filedata
            self.file_model = TorrentFileModel(info.files, None)
            self.setText(info.name)

        self.options = {}
        self.priorities = []

    def __eq__(self, other):
        return other and other.info_hash == self.info_hash


class TorrentFileModel(FileModel):

    NAME_SEP = os.sep

    class Item(FileModel.Item):

        @property
        def checkState(self):
            if self.is_file():
                return QtCore.Qt.Checked if self.model.priorities[self.index] else QtCore.Qt.Unchecked
            else:
                children_states = list(frozenset(child.checkState for child in self.children))
                return children_states[0] if len(children_states) == 1 else QtCore.Qt.PartiallyChecked

        # @checkState.setter
        def setCheckState(self, state):
            if self.is_file():
                self.model.priorities[self.index] = (state == QtCore.Qt.Checked)
            else:
                for child in self.children:
                    child.setCheckState(state)

    def __init__(self, files, parent):
        super(TorrentFileModel, self).__init__(parent)
        super(TorrentFileModel, self).update(files)

        self.priorities = [1] * len(files)

    def file_options(self):
        return {"mapped_files": [],
                "file_priorities": self.priorities}

    def _create_columns(self):
        columns = super(TorrentFileModel, self)._create_columns()
        columns[0].augment(checkState="checkState")
        columns[1].augment(align=(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,))
        return columns

    def _mapped_files(self, path, item, mapping):
        new_path = os.path.join(path, item.name)
        if item.is_file():
            if item.file["path"] != new_path:
                pass # FIXME mapping[item.index] = new_path
        else:
            for child in item.children:
                self._mapped_files(new_path, child, mapping)
        return mapping

    def flags(self, index):
        flags = super(FileModel, self).flags(index)
        if index.column() == 0:
            flags |= QtCore.Qt.ItemIsUserCheckable
        return flags

    def setData(self, index, value, role):
        if super(TorrentFileModel, self).setData(index, value, role):
            return True

        item = index.internalPointer()
        if item and index.column() == 0 and role == QtCore.Qt.CheckStateRole:
            item.setCheckState(QtCore.Qt.Checked if item.checkState != QtCore.Qt.Checked else QtCore.Qt.Unchecked)
            self.dataChanged.emit(index.child(0, 0), index.child(self.rowCount(index), 0))
            while index.isValid():
                self.dataChanged.emit(index, index)
                index = index.parent()
            return True

        return False
