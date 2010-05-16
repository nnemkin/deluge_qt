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
from .ui_tools import QtBug7674ItemDelegate
from .ui_common import FileItem, FileItemRoot, WidgetLoader


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

        header = self.tree_files.header()
        header.setResizeMode(0, QtGui.QHeaderView.Stretch)
        header.setResizeMode(1, QtGui.QHeaderView.Fixed) # NB: ResizeToContents is slow
        header.setDefaultSectionSize(self.tree_files.fontMetrics().width("M") * 12)

        QtBug7674ItemDelegate.install(self.tree_files)

        self.start()

    @defer.inlineCallbacks
    def start(self):
        core_config = yield client.core.get_config_values(self._core_keys_to_torrent_keys.keys())
        self.default_options = dict((self._core_keys_to_torrent_keys[k], v) for k, v in core_config.items())

    def torrents(self):
        return map(self.list_torrents.item, range(self.list_torrents.count()))

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
        """Handles lists of local filenames or magnet uris"""
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
        torrent.file_root.takeFrom(self.tree_files)

    def _load_options(self, torrent):
        WidgetLoader.to_widgets(torrent.options or self.default_options, self)
        torrent.file_root.addTo(self.tree_files)

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
            self.tree_files.clear()
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
                torrent.options.update(torrent.file_root.file_options())
                client.core.add_torrent_file(torrent.filename, base64.encodestring(torrent.filedata), torrent.options)

        super(AddTorrentsDialog, self).accept()


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
            self.file_root = TorrentFileRoot(info.files)
            self.setText(info.name)

        self.options = {}
        self.priorities = []

    def __eq__(self, other):
        return other and other.info_hash == self.info_hash


class TorrentFileItem(FileItem):

    _flags_file = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable # TODO | QtCore.Qt.ItemIsDragEnabled
    _flags_folder = _flags_file | QtCore.Qt.ItemIsTristate | QtCore.Qt.ItemIsDropEnabled

    def __init__(self, parent, name, file=None):
        super(TorrentFileItem, self).__init__(parent, name, file)

        self.setFlags(self._flags_file if file else self._flags_folder)
        self.setCheckState(0, QtCore.Qt.Checked)
        self.setTextAlignment(1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class TorrentFileRoot(FileItemRoot):

    item_type = TorrentFileItem
    name_sep = os.sep

    def __init__(self, files):
        # we need file["index"] not provided by TorrentInfo
        files = [{"path": file["path"], "size": file["size"], "index": i} for i, file in enumerate(files)]
        super(TorrentFileRoot, self).__init__(files)

    def file_options(self):
        return {"mapped_files": self._mapped_files('', self, {}),
                "file_priorities": [item.checkState(0) == QtCore.Qt.Checked for item in self._file_items]}

    def _mapped_files(self, path, item, mapping):
        new_path = os.path.join(path, item.text(0))
        if item.file:
            if item.file["path"] != new_path:
                mapping[item.index] = new_path
        else:
            for child in item.children():
                self._mapped_files(new_path, child, mapping)
        return mapping
