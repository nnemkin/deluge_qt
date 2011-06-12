
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
import logging

from PyQt4 import QtCore, QtGui
from twisted.python.compat import inet_pton
from twisted.internet import defer

import deluge.common
from deluge.ui.countries import COUNTRIES
from deluge import component

from .lang_tools import memoize
from .ui_tools import ProgressBarDelegate, HeightFixItemDelegate, IconLoader
from .ui_common import DictModel, Column

log = logging.getLogger(__name__)


class PeerViewModel(DictModel):

    def _create_columns(self):
        @memoize
        def flag_icon(country):
            try:
                if country:
                    return IconLoader.packageIcon("data/pixmaps/flags/%s.png" % country.lower())
            except Exception:
                log.debug("Unable to load flag: %s", exc_info=True)

        def ip_sort_key(ip):
            addr, port = ip.rsplit(':', 1)
            addr = inet_pton(socket.AF_INET6 if ':' in addr else socket.AF_INET, addr)
            return (addr, port)

        peer_icon = IconLoader.customIcon("downloading16.png")
        seed_icon = IconLoader.customIcon("seeding16.png")

        return [Column("", icon=(flag_icon, "country"), toolTip=(COUNTRIES.get, "country"), sort="country", width=3),
                Column("Address", text="ip", icon=(lambda flag: seed_icon if flag else peer_icon, "seed"),
                       sort=(ip_sort_key, "total_wanted"), width=20),
                Column("Client", text="client", sort="client", width=15),
                Column("Progress", text=(deluge.common.fpcnt, "progress"), user="progress", sort="progress", width=15),
                Column("Down Speed", text=(deluge.common.fspeed, "down_speed"), sort="down_speed", width=10),
                Column("Up Speed", text=(deluge.common.fspeed, "up_speed"), sort="up_speed", width=10)]


class PeerView(QtGui.QTreeView, component.Component):

    def __init__(self, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        component.Component.__init__(self, "PeerView", interval=2)

        self.torrent_ids = []

        self.setModel(PeerViewModel(self))
        self.model().resize_header(self.header())

        HeightFixItemDelegate.install(self)
        self.setItemDelegateForColumn(3, ProgressBarDelegate(self))

    def stop(self):
        self.model().clear()

    def showEvent(self, event):
        self.update()
        super(PeerView, self).showEvent(event)

    @defer.inlineCallbacks
    def update(self):
        if self.torrent_ids and self.isVisible():
            status = (yield component.get("SessionProxy").get_torrent_status(self.torrent_ids[0], ["peers"]))
            peers = dict((peer["ip"], peer) for peer in status["peers"])
            self.model().update(peers)

    @QtCore.pyqtSlot(object)
    def set_torrent_ids(self, torrent_ids):
        if self.torrent_ids != torrent_ids:
            self.torrent_ids = torrent_ids
            if torrent_ids:
                self.update()
            else:
                self.model().clear()
