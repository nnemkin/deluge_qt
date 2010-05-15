#
# file_view.py
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

from PyQt4 import QtCore, QtGui
from twisted.internet import defer

import deluge.common
from deluge.ui.client import client
from deluge import component, configmanager

from .ui_tools import ProgressBarDelegate, HeightFixItemDelegate, IconLoader, treeContextMenuHandler
from .ui_common import TreeColumns, FileItem, FileItemRoot


class TorrentFileItem(FileItem):

    _flags_file = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable # TODO | QtCore.Qt.ItemIsDragEnabled
    _flags_folder = _flags_file | QtCore.Qt.ItemIsTristate | QtCore.Qt.ItemIsDropEnabled

    _priority_icons = {0: IconLoader.customIcon("gtk-no.png"),
                       1: IconLoader.customIcon("gtk-yes.png"),
                       2: IconLoader.themeIcon("go-up"),
                       5: IconLoader.themeIcon("go-top")}

    columns = TreeColumns()
    columns.add("Filename", width=45, const=True)
    columns.add("Size", width=10, const=True)
    columns.add("Progress", width=10)
    columns.add("Priority", width=10)

    def __init__(self, parent, name, file=None):
        super(TorrentFileItem, self).__init__(parent, name, file)

        self.setFlags(self._flags_file if file else self._flags_folder)
        self.setTextAlignment(1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

    def setSortColumn(self, column):
        pass

    def update(self, progress, priority):
        self.setText(2, deluge.common.fpcnt(progress))
        self.setData(2, QtCore.Qt.UserRole, progress)
        self.setText(3, _(deluge.common.FILE_PRIORITY[priority]))
        self.setIcon(3, self._priority_icons.get(priority))


class TorrentFileRoot(FileItemRoot):

    item_type = TorrentFileItem
    name_sep = "/"

    def __init__(self, files, progress, priorities):
        super(TorrentFileRoot, self).__init__(files)

        self.update(progress, priorities)

    def file_priorities(self):
        return [item.data(3, QtCore.Qt.UserRole) for item in self._file_items]

    def update(self, progress, priorities):
        for i, item in enumerate(self._file_items):
            item.update(progress[i], priorities[i])


class FileView(QtGui.QTreeWidget, component.Component):

    def __init__(self, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        component.Component.__init__(self, "FileView", interval=2)

        self.ui_config = configmanager.ConfigManager('qtui.conf')

        self.torrent_ids = []
        self.items = {}
        self.files_cache = {}

        HeightFixItemDelegate.install(self)
        self.setHeaderLabels(TorrentFileItem.columns.names)
        self.setItemDelegateForColumn(2, ProgressBarDelegate(self))

        self.header().sortIndicatorChanged.connect(self.on_header_sortIndicatorChanged)

        client.register_event_handler("TorrentFileRenamedEvent", self.on_client_torrentFileRenamed)
        client.register_event_handler("TorrentFolderRenamedEvent", self.on_client_torrentFileRenamed)
        client.register_event_handler("TorrentRemovedEvent", self.on_client_torrentRemoved)

        try:
            self.header().restoreState(QtCore.QByteArray.fromBase64(self.ui_config['file_view_state']))
        except KeyError:
            em = self.header().fontMetrics().width('M')
            for i, width in enumerate(TorrentFileItem.columns.widths):
                self.header().resizeSection(i, width * em)

    def start(self):
        pass

    def stop(self):
        pass

    def shutdown(self):
        self.ui_config['file_view_state'] = self.header().saveState().toBase64().data()

    @defer.inlineCallbacks
    def update(self):
        if self.torrent_ids and self.isVisible():
            fields = ["compact", "file_progress", "file_priorities"]
            try:
                files = self.files_cache[self.torrent_ids[0]]
            except KeyError:
                files = None
                fields.append("files")

            status = yield component.get("SessionProxy").get_torrent_status(self.torrent_ids[0], fields)
            if not files:
                self.files_cache[self.torrent_ids[0]] = files = status["files"]

            if not self.topLevelItemCount():
                TorrentFileRoot(files, status["file_progress"], status["file_priorities"]).addTo(self)

    def contextMenuEvent(self, event):
        treeContextMenuHandler(self, event, component.get("MainWindow").popup_menu_files)

    def on_client_torrentFileRenamed(self, torrent_id, *args):
        try:
            del self.files_cache[torrent_id]
        except KeyError:
            pass
        else:
            if self.torrent_ids[0] == torrent_id:
                self.update()

    def on_client_torrentRemoved(self, torrent_id):
        self.on_client_torrentFileRenamed(torrent_id)

    def _clear(self):
        pass

    @QtCore.pyqtSlot(object)
    def set_torrent_ids(self, torrent_ids):
        if self.torrent_ids != torrent_ids:
            self.torrent_ids = torrent_ids
            self.clear()
            if torrent_ids:
                self.update()

    @QtCore.pyqtSlot(int, QtCore.Qt.SortOrder)
    def on_header_sortIndicatorChanged(self, index, order):
        pass
        #for item in self.items.itervalues():
        #    item.setSortColumn(index)

    @QtCore.pyqtSlot(QtGui.QTreeWidgetItem, int)
    @defer.inlineCallbacks
    def on_item_activated(self, item, column):
        if client.is_localhost:
            pass # TODO
