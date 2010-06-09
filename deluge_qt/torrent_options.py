#
# torrent_options.py
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

from PyQt4 import QtGui, QtCore
from twisted.internet import defer

import deluge.common
from deluge.ui.client import client
from deluge import component

from .generated.ui import Ui_TorrentOptions, Ui_EditTackersDialog, Ui_AddTrackersDialog
from .ui_common import WidgetLoader


class TorrentOptions(QtGui.QWidget, Ui_TorrentOptions, component.Component):

    _option_keys = ["max_download_speed", "max_upload_speed", "max_connections", "max_upload_slots",
                    "private", "prioritize_first_last", "is_auto_managed", "stop_at_ratio", "stop_ratio",
                    "remove_at_ratio", "move_on_completed", "move_on_completed_path"]

    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        component.Component.__init__(self, "TorrentOptions", interval=2)

        self.setupUi(self)

        self.torrent_ids = []
        self.options = {}

    def start(self):
        self.setEnabled(True)

    def stop(self):
        self.setEnabled(False)

    def showEvent(self, event):
        self.update()
        super(TorrentOptions, self).showEvent(event)

    @defer.inlineCallbacks
    def update(self):
        if self.torrent_ids and self.isVisible():
            options = yield component.get("SessionProxy").get_torrent_status(self.torrent_ids[0], self._option_keys)
            if options != self.options:
                modified_options = dict((key, value) for key, value in options.iteritems() if value != self.options.get(value))
                WidgetLoader.to_widgets(modified_options, self)
                self.options = options

    @QtCore.pyqtSlot(object)
    def set_torrent_ids(self, torrent_ids):
        if self.torrent_ids != torrent_ids:
            self.torrent_ids = torrent_ids
            if torrent_ids and self.isVisible():
                self.update()

    @QtCore.pyqtSlot()
    @defer.inlineCallbacks
    def on_button_edit_trackers_clicked(self):
        torrent_id = self.torrent_ids[0]
        options = yield component.get("SessionProxy").get_torrent_status(torrent_id, ["trackers"])
        if torrent_id == self.torrent_ids[0]: # check if selection changed
            print torrent_id, options
            edit_trackers = EditTrackersDialog(self, options["trackers"])
            if edit_trackers.exec_():
                client.core.set_torrent_trackers(torrent_id, edit_trackers.trackers)

    @QtCore.pyqtSlot()
    def on_button_apply_clicked(self):
        new_options = WidgetLoader.from_widgets(self, self.options)
        del new_options["private"]
        #if not new_options["move_on_completed"]:
        #    del new_options["move_on_completed_path"]
        for key, value in new_options.iteritems():
            if self.options[key] != value:
                getattr(client.core, "set_torrent_" + key)(self.torrent_ids[0], value) # XXX: use set_torrent_options ?
        self.options = new_options


class EditTrackersDialog(QtGui.QDialog, Ui_EditTackersDialog):

    class TrackerTreeModel(QtCore.QAbstractTableModel):

        def headerData(self, section, orientation):
            pass

        def rowCount(self, parent):
            pass

        def columnCount(self, parent):
            pass

        def data(self):
            pass

    def __init__(self, parent, trackers=[]):
        super(EditTrackersDialog, self).__init__(parent, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)

        self.trackers = trackers
        self.tree_trackers.addTopLevelItems([QtGui.QTreeWidgetItem([str(tracker["tier"]), tracker["url"]]) for tracker in trackers])

    def _tracker_items(self):
        return map(self.tree_trackers.topLevelItem, xrange(self.tree_trackers.topLevelItemCount()))

    @QtCore.pyqtSlot()
    def on_button_add_clicked(self):
        dialog = QtGui.QDialog(self)
        try:
            dialog_ui = Ui_AddTrackersDialog()
            dialog_ui.setupUi(dialog)
            if dialog.exec_():
                existing_trackers = set(item.text(1) for item in self._tracker_items())
                tier = max(int(item.text(0)) for item in self._tracker_items())
                for url in dialog.text_trackers().strip().split("\n"):
                    if url and deluge.common.is_url(url) and not url in existing_trackers:
                        tier += 1
                        item = QtGui.QTreeWidgetItem(self.tree_trackers, [tier, url])
                        # prevent drop overwrite
                        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsDragEnabled)
        finally:
            dialog.deleteLater()

    @QtCore.pyqtSlot()
    def on_button_edit_clicked(self):
        try:
            item = self.tree_trackers.selectedItems()[0]
        except IndexError:
            pass
        else:
            url = QtGui.QInputDialog.getText(self, _("Edit Tracker"), _("Tracker:"), text=item.text(1))[0]
            if url and deluge.common.is_url(url):
                item.setText(1, url)

    @QtCore.pyqtSlot()
    def on_button_remove_clicked(self):
        try:
            self.tree_trackers.takeTopLevelItem(self.tree_trackers.selectedIndexes()[0].row())
        except IndexError:
            pass

    @QtCore.pyqtSlot()
    def on_button_up_clicked(self):
        try:
            item = self.tree_trackers.selectedItems()[0]
        except IndexError:
            pass
        else:
            pass

    @QtCore.pyqtSlot()
    def on_button_down_clicked(self):
        try:
            row = self.tree_trackers.selectedIndexes()[0].row()
        except IndexError:
            pass
        else:
            if row < self.tree_trackers.topLevelItemCount() - 1:
                self.tree_trackers.insertTopLevelItem(row + 1, self.tree_trackers.topLevelItem(row))

    def accept(self):
        self.trackers = [{"tier": int(item.text(0)), "url": item.text(1)} for item in self._tracker_items()]
        super(EditTrackersDialog, self).accept()
