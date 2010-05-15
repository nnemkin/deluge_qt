#
# status_bar.py
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

import time

from PyQt4 import QtGui, QtCore
from twisted.internet import defer

import deluge.common
from deluge import component
from deluge.ui.client import client

from .ui_tools import IconLoader
import formats


class StatusBarItem(QtGui.QWidget):

    _small_icon_size = QtGui.qApp.style().pixelMetric(QtGui.QStyle.PM_SmallIconSize)

    clicked = QtCore.pyqtSignal()

    def __init__(self, parent, icon, minimumWidth=75, context_menu=None, text="", **kwargs):
        super(StatusBarItem, self).__init__(parent, **kwargs)

        icon = QtGui.QLabel(self, pixmap=icon.pixmap(self._small_icon_size))
        icon.setFixedWidth(self._small_icon_size)
        self.label = QtGui.QLabel(text, self)

        layout = QtGui.QHBoxLayout(spacing=4)
        layout.setContentsMargins(2, 0, 4, 0)
        layout.addWidget(icon)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.setMinimumWidth(minimumWidth)

        self._pressed = False
        self._context_menu = context_menu

        parent.addWidget(self)

    def text(self):
        return self.label.text()

    def setText(self, text):
        self.label.setText(text)

    def mousePressEvent(self, event):
        self._pressed = event.button()  in (QtCore.Qt.LeftButton, QtCore.Qt.RightButton)
        super(StatusBarItem, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pressed and event.button() in (QtCore.Qt.LeftButton, QtCore.Qt.RightButton):
            if self._context_menu:
                self._context_menu.popup(self.mapToGlobal(event.pos()))

            self.clicked.emit()
        self._pressed = False

        super(StatusBarItem, self).mouseReleaseEvent(event)


class StatusBar(QtGui.QStatusBar, component.Component):

    core_config_keys = ["max_connections_global", "max_download_speed", "max_upload_speed", "dht"]
    session_status_keys = ["upload_rate", "download_rate", "payload_upload_rate", "payload_download_rate", "dht_nodes",
                           "has_incoming_connections"]

    def __init__(self, parent=None):
        QtGui.QStatusBar.__init__(self, parent)
        component.Component.__init__(self, "StatusBar", interval=3)

        self.status_not_connected = StatusBarItem(self,
                                                  text=_("Not Connected"),
                                                  toolTip=_("Not Connected"),
                                                  icon=IconLoader.themeIcon("network-offline"),
                                                  clicked=self._show_connection_dialog)
        self.status_connections = StatusBarItem(self,
                                                visible=False,
                                                toolTip=_("Connections"),
                                                icon=IconLoader.themeIcon("network-workgroup"),
                                                context_menu=component.get("MainWindow").menu_max_connections)
        self.status_download = StatusBarItem(self,
                                             visible=False,
                                             toolTip=_("Download Speed"),
                                             icon=IconLoader.customIcon("downloading16.png"),
                                             context_menu=component.get("MainWindow").menu_download_speed)
        self.status_upload = StatusBarItem(self,
                                           visible=False,
                                           toolTip=_("Upload Speed"),
                                           icon=IconLoader.customIcon("seeding16.png"),
                                           context_menu=component.get("MainWindow").menu_upload_speed)
        self.status_protocol = StatusBarItem(self,
                                             visible=False,
                                             toolTip=_("Protocol Traffic Download/Upload"),
                                             icon=IconLoader.customIcon("traffic16.png"),
                                             clicked=self._show_network_preferences)
        self.status_disk_space = StatusBarItem(self,
                                              visible=False,
                                              toolTip=_("Free Disk Space"),
                                              icon=IconLoader.themeIcon("drive-harddisk"),
                                              clicked=self._show_preferences)
        self.status_health = StatusBarItem(self,
                                           visible=False,
                                           text=_("No Incoming Connections!"),
                                           toolTip=_("No Incoming Connections!"),
                                           icon=IconLoader.themeIcon("dialog-error"),
                                           clicked=self._show_network_preferences)
        self.status_dht = StatusBarItem(self,
                                        visible=False,
                                        toolTip=_("DHT Nodes"),
                                        icon=IconLoader.customIcon("dht16.png"))

        self.status_items = self.findChildren(StatusBarItem)

        self.core_config = {}
        client.register_event_handler("ConfigValueChangedEvent", self.on_client_configvaluechanged)

        self._time_sent_recv = (time.time(), 0, 0)

    @defer.inlineCallbacks
    def start(self):
        self.core_config = yield client.core.get_config_values(self.core_config_keys)

        for item in self.status_items:
            item.setVisible(item != self.status_not_connected)
        self.status_dht.setVisible(self.core_config["dht"])

    def stop(self):
        for item in self.status_items:
            item.setVisible(item == self.status_not_connected)

    def _update_sesion_status(self, status):
        payload_download_rate = formats.fspeed(status["payload_download_rate"],
                                               self.core_config["max_download_speed"])
        payload_upload_rate = formats.fspeed(status["payload_upload_rate"],
                                             self.core_config["max_upload_speed"])
        protocol_rate = "%.2f/%.2f %s" % ((status["download_rate"] - status["payload_download_rate"]) * 1e-3,
                                          (status["upload_rate"] - status["payload_upload_rate"]) * 1e-3,
                                          _("KiB/s"))

        self.status_download.setText(payload_download_rate)
        self.status_upload.setText(payload_upload_rate)
        self.status_protocol.setText(protocol_rate)
        self.status_dht.setText(str(status["dht_nodes"]))
        self.status_health.setVisible(status["has_incoming_connections"])

    def _update_num_connections(self, num_connections):
        connections = deluge.common.fpeer(num_connections, self.core_config["max_connections_global"])
        self.status_connections.setText(connections)

    def _update_free_space(self, free_space):
        self.status_disk_space.setText(deluge.common.fsize(free_space))

    def update(self):
        client.core.get_session_status(self.session_status_keys).addCallback(self._update_sesion_status)
        client.core.get_num_connections().addCallback(self._update_num_connections)
        client.core.get_free_space().addCallback(self._update_free_space)

    def on_client_configvaluechanged(self, key, value):
        if key in self.core_config_keys:
            self.core_config[key] = value

    @QtCore.pyqtSlot()
    def _show_connection_dialog(self):
        from .connection_dialog import ConnectionDialog
        ConnectionDialog(self).show()

    @QtCore.pyqtSlot()
    def _show_preferences(self):
        from .preferences_dialog import PreferencesDialog
        PreferencesDialog(self).show()

    @QtCore.pyqtSlot()
    def _show_network_preferences(self):
        from .preferences_dialog import PreferencesDialog
        PreferencesDialog(self, "network").show()
