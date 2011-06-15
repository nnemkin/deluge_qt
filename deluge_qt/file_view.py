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
from deluge import component

from .ui_tools import ProgressBarDelegate, HeightFixItemDelegate, IconLoader, HeaderActionList, context_menu_pos
from .ui_common import FileModel, Column


class FileViewModel(FileModel):

    _priority_icons = {None: QtGui.QIcon(),
                       0: IconLoader.customIcon("gtk-no.png"),
                       1: IconLoader.customIcon("gtk-yes.png"),
                       2: IconLoader.themeIcon("go-up"),
                       5: IconLoader.themeIcon("go-top")}

    class Item(FileModel.Item):

        @property
        def progress(self):
            if self.is_file():
                return self.model.progress[self.index]
            else:
                return sum(child.progress for child in self.children) / len(self.children)

        @property
        def priority(self):
            if self.is_file():
                return self.model.priorities[self.index]
            else:
                if len(frozenset(child.priority for child in self.children)) == 1:
                    return self.children[0].priority

    def __init__(self, files, parent):
        FileModel.__init__(self, parent)
        FileModel.update(self, files)

        self.priorities = self.progress = [0] * len(files)
        self._expanded = []

    def _create_columns(self):
        fprio = lambda p: _(deluge.common.FILE_PRIORITY[p]) if p is not None else ''

        columns = FileModel._create_columns(self)
        columns += [Column("Progress", text=(deluge.common.fpcnt, "progress"), user="progress", width=12),
                    Column("Priority", text=(fprio, "priority"), icon=(self._priority_icons.get, "priority"), width=12)]
        return columns

    def update(self, progress, priorities):
        if self.progress != progress or self.priorities != priorities:
            self.progress = progress
            self.priorities = priorities

            active_range = self.columnsForFields(["progress", "priority"])
            active_range = min(active_range), max(active_range)
            self.dataChanged.emit(self.index(0, active_range[0]),
                                  self.index(len(self.root.children) - 1, active_range[1]))


class FileView(QtGui.QTreeView, component.Component):

    EMPTY_MODEL = FileViewModel([], None)

    def __init__(self, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        component.Component.__init__(self, "FileView", interval=2)

        self.torrent_ids = []
        self.file_models = {}

        self.setModel(self.EMPTY_MODEL)
        self.model().resize_header(self.header())

        HeightFixItemDelegate.install(self)
        self.setItemDelegateForColumn(2, ProgressBarDelegate(self))

        client.register_event_handler("TorrentFileRenamedEvent", self.on_client_torrentFileRenamed)
        client.register_event_handler("TorrentFolderRenamedEvent", self.on_client_torrentFolderRenamed)
        client.register_event_handler("TorrentRemovedEvent", self.on_client_torrentRemoved)

        HeaderActionList(self)

    def start(self):
        pass

    def stop(self):
        self.setModel(self.EMPTY_MODEL)
        self.file_models.clear()
        self.torrent_ids = []

    def showEvent(self, event):
        self.update()
        QtGui.QTreeView.showEvent(self, event)

    @defer.inlineCallbacks
    def update(self):
        if self.torrent_ids and self.isVisible():
            fields = ["compact", "file_progress", "file_priorities"]

            model = self.file_models.get(self.torrent_ids[0])
            if not model:
                fields.append("files")

            status = yield component.get("SessionProxy").get_torrent_status(self.torrent_ids[0], fields)
            if not model:
                self.file_models[self.torrent_ids[0]] = model = FileViewModel(status["files"], self)
                model.filesRenamed.connect(self.on_model_filesRenamed)
                model.folderRenamed.connect(self.on_model_folderRenamed)
                model.indexesAdded.connect(self.on_model_indexesAdded)
                self.setModel(model)
                self.expandToDepth(0)

            model.update(status["file_progress"], status["file_priorities"])

    def contextMenuEvent(self, event):
        pos = context_menu_pos(self, event)
        if pos:
            component.get("MainWindow").popup_menu_files.popup(pos)

    @QtCore.pyqtSlot(object)
    def on_model_filesRenamed(self, renames):
        client.core.rename_files(self.torrent_ids[0], renames)

    @QtCore.pyqtSlot(str, str)
    def on_model_folderRenamed(self, old_name, new_name):
        client.core.rename_folder(self.torrent_ids[0], old_name, new_name)

    @QtCore.pyqtSlot(object)
    def on_model_indexesAdded(self, indexes):
        current_index = self.currentIndex()
        for index in indexes:
            self.expand(index)
        if not self.selectionModel().isSelected(current_index):
            self.setCurrentIndex(current_index)
            self.scrollTo(current_index)

    def on_client_torrentFileRenamed(self, torrent_id, index, name):
        try:
            model = self.file_models[torrent_id]
        except KeyError:
            pass
        else:
            model.renameFile(index, name)

    def on_client_torrentFolderRenamed(self, torrent_id, old_name, new_name):
        try:
            model = self.file_models[torrent_id]
        except KeyError:
            pass
        else:
            model.renameFolder(old_name, new_name)

    def on_client_torrentRemoved(self, torrent_id):
        self.file_models.pop(torrent_id, None)

    @QtCore.pyqtSlot(object)
    def set_torrent_ids(self, torrent_ids):
        if self.torrent_ids != torrent_ids:
            self.torrent_ids = torrent_ids
            if torrent_ids:
                try:
                    model = self.file_models[self.torrent_ids[0]]
                except KeyError:
                    pass
                else:
                    self.setModel(model)
                    self.expandToDepth(0)
                self.update()
            else:
                self.setModel(self.EMPTY_MODEL)

    @QtCore.pyqtSlot(QtGui.QTreeWidgetItem, int)
    @defer.inlineCallbacks
    def on_item_activated(self, item, column):
        if client.is_localhost:
            pass # TODO
