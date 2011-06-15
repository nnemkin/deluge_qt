#
# torrent_details.py
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

import logging
import cPickle as pickle

from PyQt4 import QtGui, QtCore
from twisted.internet import defer

from deluge import component

import formats
from .generated.ui import Ui_TorrentDetails

log = logging.getLogger(__name__)


class TabProxy(QtCore.QObject):

    def __init__(self, parent, i):
        QtCore.QObject.__init__(self, parent)
        self.weight = i
        self.widget = parent.widget(i)
        self.icon = parent.tabIcon(i)
        self.text = parent.tabText(i)
        self.tooltip = parent.tabToolTip(i)
        self.visible = True
        self.action = QtGui.QAction(self.icon, self.text, parent, checkable=True, checked=True, toggled=self.setVisible)

    @QtCore.pyqtSlot(bool)
    def setVisible(self, visible):
        if self.visible != visible:
            parent = self.parent()
            if visible:
                index = sum(tab.visible and tab.weight < self.weight for tab in parent.tab_proxies)
                parent.insertTab(index, self.widget, self.icon, self.text)
                parent.setTabToolTip(index, self.tooltip)
            else:
                index = parent.indexOf(self.widget)
                if index != -1:
                    parent.removeTab(index)
            self.visible = visible
            self.action.setChecked(visible)


class TorrentDetails(QtGui.QTabWidget, Ui_TorrentDetails, component.Component):

    def __init__(self, parent=None):
        QtGui.QTabWidget.__init__(self, parent)
        Ui_TorrentDetails.__init__(self)
        component.Component.__init__(self, "TorrentDetails", interval=2)

        self.setupUi(self)
        self.progress_bar.setText("")

        self.tab_proxies = [TabProxy(self, i) for i in xrange(self.count())]
        self.tabBar().setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        self.tabBar().addActions([tab.action for tab in self.tab_proxies])

        self.bindings = [
            (self.status_pieces, formats.fpieces, "num_pieces", "piece_length"),
            (self.status_availability, formats.fratio, "distributed_copies"),
            (self.status_total_downloaded, formats.fsize2, "all_time_download", "total_payload_download"),
            (self.status_total_uploaded, formats.fsize2, "total_uploaded", "total_payload_upload"),
            (self.status_download_speed, formats.fspeed, "download_payload_rate", "max_download_speed"),
            (self.status_upload_speed, formats.fspeed, "upload_payload_rate", "max_upload_speed"),
            (self.status_seeders, formats.fpeer, "num_seeds", "total_seeds"),
            (self.status_peers, formats.fpeer, "num_peers", "total_peers"),
            (self.status_eta, formats.ftime, "eta"),
            (self.status_share_ratio, formats.fratio, "ratio"),
            (self.status_tracker_status, str, "tracker_status"),
            (self.status_next_announce, formats.ftime, "next_announce"),
            (self.status_active_time, formats.ftime, "active_time"),
            (self.status_seed_time, formats.ftime, "seeding_time"),
            (self.status_seed_rank, str, "seed_rank"),
            (self.status_auto_managed, str, "is_auto_managed"),
            (self.status_date_added, formats.fdate, "time_added"),
            (self.status_name, str, "name"),
            (self.status_total_size, formats.fsize, "total_size"),
            (self.status_num_files, str, "num_files"),
            (self.status_tracker, str, "tracker"),
            (self.status_torrent_path, str, "save_path"),
            (self.status_message, str, "message"),
            (self.status_hash, str, "hash"),
            (self.status_comments, str, "comment")]

        self.fields = set(("progress",))
        for binding in self.bindings:
            self.fields.update(binding[2:])

        self.status = None
        self.torrent_ids = []

    @QtCore.pyqtSlot(object)
    def set_torrent_ids(self, torrent_ids):
        if self.torrent_ids != torrent_ids:
            self.torrent_ids = torrent_ids
            if torrent_ids:
                self.update()
            else:
                self._clear()

    def stop(self):
        self._clear()

    @defer.inlineCallbacks
    def update(self):
        if self.torrent_ids:
            status = yield component.get("SessionProxy").get_torrent_status(self.torrent_ids[0], self.fields)

            if self.status == status:
                return

            for binding in self.bindings:
                label, func, args = binding[0], binding[1], binding[2:] 
                label.setText(func(*(status[arg] for arg in args)))

            self.progress_bar.setText(formats.fpcnt(status["progress"] * 0.01))
            self.progress_bar.setValue(int(status["progress"] * 10))

            self.status = status

    def _clear(self):
        self.progress_bar.setValue(0)
        self.progress_bar.setText("")
        for widget in self.findChildren(QtGui.QLabel):
            if widget.objectName().startswith("status_"):
                widget.setText("")

    def saveState(self):
        return QtCore.QByteArray(pickle.dumps([tab.visible for tab in self.tab_proxies], pickle.HIGHEST_PROTOCOL))

    def restoreState(self, state):
        try:
            for i, visible in enumerate(pickle.loads(str(state))):
                self.tab_proxies[i].setVisible(visible)
        except Exception:
            log.debug("Failed to restore tab state", exc_info=True)
