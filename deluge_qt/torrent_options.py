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

from deluge.ui.client import client
from deluge import component

from .generated.ui import Ui_TorrentOptions, Ui_EditTackersDialog
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
    def on_button_edit_trackers_clicked(self):
        EditTrackersDialog(self).show()

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

    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)
        self.setupUi(self)
