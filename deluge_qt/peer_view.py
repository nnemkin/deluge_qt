#
# peer_view.py
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

import socket

from PyQt4 import QtCore, QtGui
from twisted.python.compat import inet_pton
from twisted.internet import defer

from deluge.log import LOG as log
from deluge import component, configmanager
from deluge.ui.countries import COUNTRIES

import deluge.common
from .ui_tools import ProgressBarDelegate, HeightFixItemDelegate, IconLoader
from .ui_common import TreeItem, TreeColumns
from .lang_tools import memoize


@memoize
def _flag_icon(country):
    try:
        return IconLoader.packageIcon("data/pixmaps/flags/%s.png" % country.lower())
    except Exception:
        log.debug("Unable to load flag: %s", exc_info=True)


class PeerSeedIconsCache(object):

    _icon_peer = IconLoader.customIcon("downloading16.png")
    _icon_seed = IconLoader.customIcon("seeding16.png")

    def __call__(self, seed):
        return self._icon_seed if seed else self._icon_peer


def _ip_sort_key(ip):
    addr, port = ip.rsplit(':', 1)
    addr = inet_pton(socket.AF_INET6 if ':' in addr else socket.AF_INET, addr)
    return (addr, port)


class PeerItem(TreeItem):

    columns = TreeColumns()
    columns.add("", icon=(_flag_icon, "country"), toolTip=(COUNTRIES.get, "country"), sort="country",
                const=True, width=3)
    columns.add(_("Address"), text="ip", icon=(PeerSeedIconsCache(), "seed"), sort=(_ip_sort_key, "total_wanted"),
                const=True, width=20)
    columns.add(_("Client"), text="client", sort="client", const=True, width=15)
    columns.add(_("Progress"), text=(deluge.common.fpcnt, "progress"), user="progress", sort="progress", width=15)
    columns.add(_("Down Speed"), text=(deluge.common.fspeed, "down_speed"), sort="down_speed", width=10)
    columns.add(_("Up Speed"), text=(deluge.common.fspeed, "up_speed"), sort="up_speed", width=10)

    @classmethod
    def is_const_column(cls, index):
        return index < 3


class PeerView(QtGui.QTreeWidget, component.Component):

    def __init__(self, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        component.Component.__init__(self, "PeerView", interval=2)

        self.ui_config = configmanager.ConfigManager('qtui.conf')

        self.torrent_ids = []
        self.items = {}

        HeightFixItemDelegate.install(self)
        self.setItemDelegateForColumn(3, ProgressBarDelegate(self))
        self.setHeaderLabels(PeerItem.columns.names)

        try:
            self.header().restoreState(QtCore.QByteArray.fromBase64(self.ui_config['peer_view_state']))
        except KeyError:
            em = self.header().fontMetrics().width('M')
            for i, width in enumerate(PeerItem.columns.widths):
                self.header().resizeSection(i, width * em)

    def start(self):
        pass

    def stop(self):
        self._clear()

    def shutdown(self):
        self.ui_config['peer_view_state'] = self.header().saveState().toBase64().data()

    @defer.inlineCallbacks
    def update(self):
        if self.torrent_ids:
            sort_column = self.sortColumn()
            peers = (yield component.get("SessionProxy").get_torrent_status(self.torrent_ids[0], ["peers"]))["peers"]

            new_items = []
            for peer in peers:
                try:
                    item = self.items[peer["ip"]]
                except KeyError:
                    item = PeerItem(peer, sort_column)
                    self.items[peer["ip"]] = item
                    new_items.append(item)
                else:
                    item.update(peer)

            deleted_ips = set(self.items)
            deleted_ips.difference_update(peer["ip"] for peer in peers)

            disable_sort = (deleted_ips or new_items) and not PeerItem.is_const_column(sort_column)
            if disable_sort:
                self.setSortingEnabled(False)

            for ip in deleted_ips:
                self.takeTopLevelItem(self.indexOfTopLevelItem(self.items[ip]))
                del self.items[ip]

            if new_items:
                self.addTopLevelItems(new_items)

            if disable_sort:
                self.setSortingEnabled(True)

    @QtCore.pyqtSlot(object)
    def set_torrent_ids(self, torrent_ids):
        if self.torrent_ids != torrent_ids:
            self.torrent_ids = torrent_ids
            if torrent_ids:
                self.update()
            else:
                self._clear()

    def _clear(self):
        self.clear()
        self.items.clear()
