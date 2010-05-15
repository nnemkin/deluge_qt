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
from deluge.log import LOG as log

import formats
from .ui_tools import ProgressBarDelegate, HeightFixItemDelegate, IconLoader, header_view_actions, treeContextMenuHandler
from .ui_common import TreeItem, TreeColumns, TrackerIconsCache


def _fprogress(state, progress):
    if state != "Seeding" and progress < 100:
        return "%s %s" % (_(state), deluge.common.fpcnt(progress))
    return _(state)

def _fargs(*args): return args


class TorrentItem(TreeItem):

    _state_icons = {"Allocating": IconLoader.customIcon("checking16.png"),
                    "Checking": IconLoader.customIcon("checking16.png"),
                    "Downloading": IconLoader.customIcon("downloading16.png"),
                    "Seeding": IconLoader.customIcon("seeding16.png"),
                    "Paused": IconLoader.customIcon("inactive16.png"),
                    "Error": IconLoader.customIcon("alert16.png"),
                    "Queued": IconLoader.customIcon("queued16.png")}

    columns = TreeColumns()
    columns.add("#", text=(formats.fqueue, "queue"), sort="queue", width=4)
    columns.add(_("Name"), text="name", icon=(_state_icons.get, "state"), sort="name", width=45)
    columns.add(_("Size"), text=(deluge.common.fsize, "total_wanted"), sort="total_wanted", const=True, width=8)
    columns.add(_("Progress"), text=(_fprogress, "state", "progress"), user=(lambda p: p * 0.01, "progress"),
                sort=(_fargs, "progress", "state"), width=18)
    columns.add(_("Seeders"), text=(deluge.common.fpeer, "num_seeds", "total_seeds"),
                sort=(_fargs, "num_seeds", "total_seeds"), width=8)
    columns.add(_("Peers"), text=(deluge.common.fpeer, "num_peers", "total_peers"),
                sort=(_fargs, "num_peers", "total_peers"), width=8)
    columns.add(_("Down Speed"), text=(formats.fspeed, "download_payload_rate"), sort="download_payload_rate", width=10)
    columns.add(_("Up Speed"), text=(formats.fspeed, "upload_payload_rate"), sort="upload_payload_rate", width=10)
    columns.add(_("ETA"), text=(deluge.common.ftime, "eta"), sort="eta", width=8)
    columns.add(_("Ratio"), text=(formats.fratio, "ratio"), sort="ratio", width=6)
    columns.add(_("Avail"), text=(formats.fratio, "distributed_copies"), sort="distributed_copies", width=6)
    columns.add(_("Added"), text=(deluge.common.fdate, "time_added"), sort="time_added", const=True, width=16)
    columns.add(_("Tracker"), text="tracker_host", icon=(TrackerIconsCache, "tracker_host"), sort="tracker_host", width=20)
    columns.add(_("Save Path"), text="save_path", sort="save_path", width=20)

    def __init__(self, torrent_id, status, sort_column):
        super(TorrentItem, self).__init__(status, sort_column)
        self.torrent_id = torrent_id


def multiply_status(status):
    return dict(("%s_%04d" % (torrent_id, i), status[torrent_id]) for i in xrange(400) for torrent_id in status)


class TorrentView(QtGui.QTreeWidget, component.Component):

    selection_changed = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        component.Component.__init__(self, "TorrentView", interval=2, depend=["SessionProxy"])

        self.ui_config = configmanager.ConfigManager('qtui.conf')

        self.setHeaderLabels(TorrentItem.columns.names)
        self.setItemDelegateForColumn(3, ProgressBarDelegate(self))

        HeightFixItemDelegate.install(self)

        self.filter = {}
        self.items = {}

        client.register_event_handler("TorrentStateChangedEvent", self.on_client_torrentStateChanged)
        client.register_event_handler("TorrentAddedEvent", self.on_client_torrentAdded)
        client.register_event_handler("TorrentRemovedEvent", self.on_client_torrentRemoved)
        client.register_event_handler("TorrentQueueChangedEvent", self.update)
        client.register_event_handler("SessionPausedEvent", self.update)
        client.register_event_handler("SessionResumedEvent", self.update)

        self.itemSelectionChanged.connect(self.on_itemSelectionChanged)

        try:
            self.header().restoreState(QtCore.QByteArray.fromBase64(self.ui_config['torrent_view_state']))
        except KeyError:
            em = self.header().fontMetrics().width('M')
            for i, width in enumerate(TorrentItem.columns.widths):
                self.header().resizeSection(i, width * em)

    def selected_torrent_id(self):
        try:
            return self.selectedItems()[0].torrent_id
        except IndexError:
            return None

    def selected_torrent_ids(self):
        return [torrent.torrent_id for torrent in self.selectedItems()]

    def get_column_actions(self):
        return header_view_actions(self)

    @defer.inlineCallbacks
    def start(self):
        status = yield component.get("SessionProxy").get_torrents_status({}, TorrentItem.fields())
        status = multiply_status(status)

        sort_column = self.sortColumn()
        self.items = dict((torrent_id, TorrentItem(torrent_id, torrent_status, sort_column))
                          for torrent_id, torrent_status in status.iteritems())
        self.addTopLevelItems(self.items.values())

    def stop(self):
        self.clear()
        self.items.clear()

    def shutdown(self):
        self.ui_config['torrent_view_state'] = self.header().saveState().toBase64().data()

    @defer.inlineCallbacks
    def update(self):
        column_visibility = [not self.isColumnHidden(i) for i in xrange(self.columnCount())]
        status = yield component.get("SessionProxy").get_torrents_status(self.filter, TorrentItem.fields(column_visibility))
        status = multiply_status(status)

        self.setSortingEnabled(False)
        new_items = {}
        for torrent_id, item in self.items.iteritems():
            if torrent_id in status:
                if item:
                    item.update(status[torrent_id])
                    item.setHidden(False)
                else:
                    item = TorrentItem(torrent_id, status[torrent_id], self.sortColumn())
                    new_items[torrent_id] = item
            else:
                item.setHidden(True)

        self.items.update(new_items)
        self.addTopLevelItems(new_items.values())
        self.setSortingEnabled(True)

    def contextMenuEvent(self, event):
        treeContextMenuHandler(self, event, component.get("MainWindow").menu_torrent)

    def on_client_torrentAdded(self, torrent_id):
        self.items[torrent_id] = None
        self.update()

    def on_client_torrentRemoved(self, torrent_id):
        try:
            self.takeTopLevelItem(self.indexOfTopLevelItem(self.items[torrent_id]))
            del self.items[torrent_id]
        except KeyError:
            log.debug("Torrent not found: %s", torrent_id)

    def on_client_torrentStateChanged(self, torrent_id, state):
        try:
            self.items[torrent_id].update({"state": state})
        except IndexError:
            log.debug("Torrent not found: %s", torrent_id)

    @QtCore.pyqtSlot(object)
    def set_filter(self, filter):
        if self.filter != filter:
            self.filter = filter
            self.update()

    @QtCore.pyqtSlot()
    def on_itemSelectionChanged(self):
        self.selection_changed.emit(self.selected_torrent_ids())
