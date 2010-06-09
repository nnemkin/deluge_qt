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
from deluge import component
from deluge.ui.client import client

import formats
from .ui_tools import ProgressBarDelegate, HeightFixItemDelegate, IconLoader, HeaderActionList, context_menu_pos, natsortkey
from .ui_common import DictModel, Column, TrackerIconsCache


class TorrentViewModel(DictModel):

    _state_icons = {"Allocating": IconLoader.customIcon("checking16.png"),
                    "Checking": IconLoader.customIcon("checking16.png"),
                    "Downloading": IconLoader.customIcon("downloading16.png"),
                    "Seeding": IconLoader.customIcon("seeding16.png"),
                    "Paused": IconLoader.customIcon("inactive16.png"),
                    "Error": IconLoader.customIcon("alert16.png"),
                    "Queued": IconLoader.customIcon("queued16.png")}

    def _refresh_trackers(self, result):
        tracker_columns = self.columnsForFields(["tracker"])
        self.dataChanged.emit(self.index(0, min(tracker_columns), len(self.order) - 1, max(tracker_columns)))

    def _tracker_icon(self, host):
        d = TrackerIconsCache.get(host)
        try:
            return d.result
        except AttributeError:
            d.addCallback(self._refresh_trackers)
            return QtGui.QIcon()

    def _create_columns(self):

        def fprogress(state, progress):
            if state != "Seeding" and progress < 100:
                return "%s %s" % (_(state), deluge.common.fpcnt(progress))
            return _(state)

        def fargs(*args): return args

        return [Column("#", text=(formats.fqueue, "queue"), sort="queue", width=4),
                Column("Name", text="name", icon=(self._state_icons.get, "state"), sort=(natsortkey, "name"), width=45),
                Column("Size", text=(deluge.common.fsize, "total_wanted"), sort="total_wanted", width=8),
                Column("Progress", text=(fprogress, "state", "progress"), user=(lambda p: p * 0.01, "progress"),
                       sort=(fargs, "progress", "state"), width=18),
                Column("Seeders", text=(deluge.common.fpeer, "num_seeds", "total_seeds"),
                       sort=(fargs, "num_seeds", "total_seeds"), width=8),
                Column("Peers", text=(deluge.common.fpeer, "num_peers", "total_peers"),
                       sort=(fargs, "num_peers", "total_peers"), width=8),
                Column("Down Speed", text=(formats.fspeed, "download_payload_rate"), sort="download_payload_rate", width=10),
                Column("Up Speed", text=(formats.fspeed, "upload_payload_rate"), sort="upload_payload_rate", width=10),
                Column("ETA", text=(deluge.common.ftime, "eta"), sort="eta", width=8),
                Column("Ratio", text=(formats.fratio, "ratio"), sort="ratio", width=6),
                Column("Avail", text=(formats.fratio, "distributed_copies"), sort="distributed_copies", width=6),
                Column("Added", text=(deluge.common.fdate, "time_added"), sort="time_added", width=16),
                Column("Tracker", text="tracker_host", icon=(self._tracker_icon, "tracker_host"), sort="tracker_host", width=20),
                Column("Save Path", text="save_path", sort="save_path", width=20)]


class TorrentView(QtGui.QTreeView, component.Component):

    selection_changed = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        component.Component.__init__(self, "TorrentView", interval=2, depend=["SessionProxy"])

        self.setModel(TorrentViewModel(self))
        self.setItemDelegateForColumn(3, ProgressBarDelegate(self))
        HeightFixItemDelegate.install(self)
        self.model().resize_header(self.header())

        self.filter = {}

        client.register_event_handler("TorrentStateChangedEvent", self.update)
        client.register_event_handler("TorrentAddedEvent", self.update)
        client.register_event_handler("TorrentRemovedEvent", self.update)
        client.register_event_handler("TorrentQueueChangedEvent", self.update)
        client.register_event_handler("SessionPausedEvent", self.update)
        client.register_event_handler("SessionResumedEvent", self.update)

        HeaderActionList(self)

    def selected_torrent_id(self):
        try:
            return self.selected_torrent_ids()[0]
        except IndexError:
            return None

    def selected_torrent_ids(self):
        return [index.internalPointer() for index in self.selectedIndexes()]

    @defer.inlineCallbacks
    def start(self):
        status = yield component.get("SessionProxy").get_torrents_status({}, self.model().fieldsForColumns())
        self.model().update(status)

    def stop(self):
        self.model().clear()

    @defer.inlineCallbacks
    def update(self, unused=None):
        status = yield component.get("SessionProxy").get_torrents_status(self.filter, self.model().fieldsForColumns(self.isColumnHidden))
        self.model().update(status)

    def selectionChanged(self, selected, deselected):
        super(TorrentView, self).selectionChanged(selected, deselected)
        self.selection_changed.emit(self.selected_torrent_ids())

    def contextMenuEvent(self, event):
        pos = context_menu_pos(self, event)
        if pos:
            component.get("MainWindow").menu_torrent.popup(pos)

    @QtCore.pyqtSlot(object)
    def set_filter(self, filter):
        if self.filter != filter:
            self.filter = filter
            self.update()
