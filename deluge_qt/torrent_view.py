#
# torrent_view.py
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
from deluge import component, configmanager
from deluge.ui.client import client

import formats
from .ui_tools import ProgressBarDelegate, HeightFixItemDelegate, IconLoader, header_view_actions, treeContextMenuHandler
from .ui_common import TrackerIconsCache, ColumnModel


class TorrentViewModel(ColumnModel):

    _state_icons = {"Allocating": IconLoader.customIcon("checking16.png"),
                    "Checking": IconLoader.customIcon("checking16.png"),
                    "Downloading": IconLoader.customIcon("downloading16.png"),
                    "Seeding": IconLoader.customIcon("seeding16.png"),
                    "Paused": IconLoader.customIcon("inactive16.png"),
                    "Error": IconLoader.customIcon("alert16.png"),
                    "Queued": IconLoader.customIcon("queued16.png")}

    def _create_columns(self):

        def fprogress(state, progress):
            if state != "Seeding" and progress < 100:
                return "%s %s" % (_(state), deluge.common.fpcnt(progress))
            return _(state)

        def fargs(*args): return args

        return [self.Column("#", text=(formats.fqueue, "queue"), sort="queue", width=4),
                self.Column("Name", text="name", icon=(self._state_icons.get, "state"), sort="name", width=45),
                self.Column("Size", text=(deluge.common.fsize, "total_wanted"), sort="total_wanted", width=8),
                self.Column("Progress", text=(fprogress, "state", "progress"), user=(lambda p: p * 0.01, "progress"),
                            sort=(fargs, "progress", "state"), width=18),
                self.Column("Seeders", text=(deluge.common.fpeer, "num_seeds", "total_seeds"),
                            sort=(fargs, "num_seeds", "total_seeds"), width=8),
                self.Column("Peers", text=(deluge.common.fpeer, "num_peers", "total_peers"),
                            sort=(fargs, "num_peers", "total_peers"), width=8),
                self.Column("Down Speed", text=(formats.fspeed, "download_payload_rate"), sort="download_payload_rate", width=10),
                self.Column("Up Speed", text=(formats.fspeed, "upload_payload_rate"), sort="upload_payload_rate", width=10),
                self.Column("ETA", text=(deluge.common.ftime, "eta"), sort="eta", width=8),
                self.Column("Ratio", text=(formats.fratio, "ratio"), sort="ratio", width=6),
                self.Column("Avail", text=(formats.fratio, "distributed_copies"), sort="distributed_copies", width=6),
                self.Column("Added", text=(deluge.common.fdate, "time_added"), sort="time_added", width=16),
                self.Column("Tracker", text="tracker_host", icon=(TrackerIconsCache, "tracker_host"), sort="tracker_host", width=20),
                self.Column("Save Path", text="save_path", sort="save_path", width=20)]


class TorrentView(QtGui.QTreeView, component.Component):

    selection_changed = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        component.Component.__init__(self, "TorrentView", interval=2, depend=["SessionProxy"])

        self.ui_config = configmanager.ConfigManager('qtui.conf')

        self.setModel(TorrentViewModel(self))

        self.setItemDelegateForColumn(3, ProgressBarDelegate(self))
        HeightFixItemDelegate.install(self)

        self.filter = {}

        client.register_event_handler("TorrentStateChangedEvent", self.update)
        client.register_event_handler("TorrentAddedEvent", self.update)
        client.register_event_handler("TorrentRemovedEvent", self.update)
        client.register_event_handler("TorrentQueueChangedEvent", self.update)
        client.register_event_handler("SessionPausedEvent", self.update)
        client.register_event_handler("SessionResumedEvent", self.update)

        try:
            self.header().restoreState(QtCore.QByteArray.fromBase64(self.ui_config['torrent_view_state']))
        except KeyError:
            em = self.header().fontMetrics().width('M')
            for i, column in enumerate(self.model().columns):
                self.header().resizeSection(i, column.width * em)

    def selected_torrent_id(self):
        try:
            return self.selected_torrent_ids()[0]
        except IndexError:
            return None

    def selected_torrent_ids(self):
        return self.model().ids_from_indices(self.selectedIndexes())

    def get_column_actions(self):
        return [] # TODO header_view_actions(self)

    @defer.inlineCallbacks
    def start(self):
        status = yield component.get("SessionProxy").get_torrents_status({}, self.model().fields())
        self.model().update(status)

    def stop(self):
        self.model().clear()

    def shutdown(self):
        self.ui_config['torrent_view_state'] = self.header().saveState().toBase64().data()

    @defer.inlineCallbacks
    def update(self, unused=None):
        status = yield component.get("SessionProxy").get_torrents_status(self.filter, self.model().fields(self.isColumnHidden))
        self.model().update(status)

    def selectionChanged(self, selected, deselected):
        super(TorrentView, self).selectionChanged(selected, deselected)
        self.selection_changed.emit(self.selected_torrent_ids())

    def contextMenuEvent(self, event):
        treeContextMenuHandler(self, event, component.get("MainWindow").menu_torrent)

    @QtCore.pyqtSlot(object)
    def set_filter(self, filter):
        if self.filter != filter:
            self.filter = filter
            self.update()
