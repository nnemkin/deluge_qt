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

from PyQt4 import QtGui, QtCore
from twisted.internet import defer

import deluge.common
from deluge import component

from .generated.ui import Ui_TorrentDetails
import formats


class TabProxy(QtCore.QObject):

    def __init__(self, parent, i):
        super(TabProxy, self).__init__(parent)
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


class LabelUpdater(object):

    def __init__(self):
        self.updaters = []
        self._fields = set()

    def add(self, name, **kwargs):
        for role, args in kwargs.items():
            setter = { 'text': 'setText', 'value': 'setValue' }[role]
            if isinstance(args, tuple):
                func, fields = args[0], args[1:]
                def updater(widget, status): getattr(getattr(widget, name), setter)(func(*(status[field] for field in fields)))
                self._fields.update(fields)
            else:
                def updater(widget, status): getattr(getattr(widget, name), setter)(status[args])
                self._fields.add(args)
            self.updaters.append(updater)

    def fields(self):
        return list(self._fields)


class TorrentDetails(QtGui.QTabWidget, Ui_TorrentDetails, component.Component):

    updater = LabelUpdater()
    updater.add("status_pieces", text=(formats.fpieces, "num_pieces", "piece_length"))
    updater.add("status_availability", text=(formats.fratio, "distributed_copies"))
    updater.add("status_total_downloaded", text=(formats.fsize2, "all_time_download", "total_payload_download"))
    updater.add("status_total_uploaded", text=(formats.fsize2, "total_uploaded", "total_payload_upload"))
    updater.add("status_download_speed", text=(formats.fspeed, "download_payload_rate", "max_download_speed"))
    updater.add("status_upload_speed", text=(formats.fspeed, "upload_payload_rate", "max_upload_speed"))
    updater.add("status_seeders", text=(deluge.common.fpeer, "num_seeds", "total_seeds"))
    updater.add("status_peers", text=(deluge.common.fpeer, "num_peers", "total_peers"))
    updater.add("status_eta", text=(deluge.common.ftime, "eta"))
    updater.add("status_share_ratio", text=(formats.fratio, "ratio"))
    updater.add("status_tracker_status", text="tracker_status")
    updater.add("status_next_announce", text=(deluge.common.ftime, "next_announce"))
    updater.add("status_active_time", text=(deluge.common.ftime, "active_time"))
    updater.add("status_seed_time", text=(deluge.common.ftime, "seeding_time"))
    updater.add("status_seed_rank", text=(str, "seed_rank"))
    updater.add("status_auto_managed", text=(str, "is_auto_managed"))
    updater.add("status_date_added", text=(deluge.common.fdate, "time_added"))
    updater.add("status_name", text="name")
    updater.add("status_total_size", text=(deluge.common.fsize, "total_size"))
    updater.add("status_num_files", text=(str, "num_files"))
    updater.add("status_tracker", text="tracker")
    updater.add("status_torrent_path", text="save_path")
    updater.add("status_message", text="message")
    updater.add("status_hash", text="hash")
    updater.add("status_comments", text="comment")
    updater.add("progress_bar", text=(lambda p: deluge.common.fpcnt(p * 0.01), "progress"))
    updater.add("progress_bar", value=(lambda p: int(p * 10), "progress"))

    def __init__(self, parent=None):
        QtGui.QTabWidget.__init__(self, parent)
        Ui_TorrentDetails.__init__(self)
        component.Component.__init__(self, "TorrentDetails", interval=2)

        self.setupUi(self)
        self.progress_bar.setText("")

        self.tab_proxies = [TabProxy(self, i) for i in xrange(self.count())]
        self.tabBar().setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        self.tabBar().addActions(self.get_tab_actions())

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

    def start(self):
        pass

    def stop(self):
        self._clear()

    def shutdown(self):
        # Save the state of the tabs
        pass

    @defer.inlineCallbacks
    def update(self):
        if self.torrent_ids:
            status = yield component.get("SessionProxy").get_torrent_status(self.torrent_ids[0], self.updater.fields())

            if status != self.status:
                for updater in self.updater.updaters:
                    updater(self, status)
                self.status = status

    def _clear(self):
        self.progress_bar.setValue(0)
        self.progress_bar.setText("")
        for widget in self.findChildren(QtGui.QLabel):
            if widget.objectName().startswith("status_"):
                widget.setText("")

    def get_tab_actions(self):
        return [tab.action for tab in self.tab_proxies]
