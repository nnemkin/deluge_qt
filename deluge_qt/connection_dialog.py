#
# connection_dialog.py
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

import uuid

from PyQt4 import QtGui, QtCore
from twisted.internet import defer

from deluge import configmanager, component
from deluge.ui.client import client, Client
from deluge.log import LOG as log

from .generated.ui import Ui_ConnectionDialog, Ui_AddHostDialog
from .ui_tools import HeightFixItemDelegate, IconLoader
import async_tools


class HostItem(QtGui.QTreeWidgetItem):

    _icon_dead = IconLoader.customIcon("gtk-no.png")
    _icon_alive = IconLoader.customIcon("gtk-yes.png")
    _icon_connected = IconLoader.customIcon("gtk-connect.png")

    def __init__(self, (id, host, port, username, password)=(None, "localhost", 58846, "", "")):
        QtGui.QTreeWidgetItem.__init__(self)
        self.id = id or uuid.uuid1().hex
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.version = ""
        self.setIcon(0, self._icon_dead)
        self.update()

    def __eq__(self, other):
        return other and self.host == other.host and self.port == other.port and self.username == other.username

    @async_tools.inlineCallbacks
    def update(self):
        self.setText(0, u"%s@%s:%d" % (self.username, self.host, self.port))
        if self.is_connected():
            self.version = yield client.daemon.info()
            self.setIcon(0, self._icon_connected)
            self.setText(1, self.version)
        else:
            c = Client()
            try:
                yield c.connect(self.host, self.port, self.username, self.password)
                self.version = yield c.daemon.info()
                self.setIcon(0, self._icon_alive)
            except Exception:
                log.debug("Connection failed", exc_info=True)
                self.version = ""
                self.setIcon(0, self._icon_dead)
            finally:
                if c.connected():
                    c.disconnect()
            self.setText(1, self.version)

    def is_local(self):
        return self.host in ("127.0.0.1", "localhost")

    def is_connected(self):
        actual_username = "localclient" if (not self.username and self.is_local()) else self.username
        return client.connected() and client.connection_info() == (self.host, self.port, actual_username)

    def is_alive(self):
        return bool(self.version)

    def config_tuple(self):
        return (self.id, self.host, self.port, self.username, self.password)


class ConnectionDialog(QtGui.QDialog, Ui_ConnectionDialog):

    def __init__(self, parent=None):
        super(ConnectionDialog, self).__init__(parent, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)

        self.ui_config = configmanager.ConfigManager("qtui.conf")
        self.host_config = configmanager.ConfigManager("hostlist.conf.1.2")

        try: self.restoreGeometry(QtCore.QByteArray.fromBase64(self.ui_config["connection_dialog_geometry"]))
        except KeyError: pass

        self.button_connect = QtGui.QPushButton(_("&Connect"), self, default=True, clicked=self.on_button_connect_clicked)
        self.button_disconnect = QtGui.QPushButton(_("&Disconnect"), self, clicked=self.on_button_disconnect_clicked)
        self.button_box.addButton(self.button_connect, QtGui.QDialogButtonBox.ActionRole)
        self.button_box.addButton(self.button_disconnect, QtGui.QDialogButtonBox.ActionRole)

        self.check_autoconnect.setChecked(bool(self.ui_config["autoconnect"]))
        self.check_autostart.setChecked(self.ui_config["autostart_localhost"])
        self.check_do_not_show.setChecked(not self.ui_config["show_connection_manager_on_start"])

        HeightFixItemDelegate.install(self.tree_hosts)
        self.tree_hosts.setHeaderLabels([_("Host"), _("Version")])
        self.tree_hosts.addTopLevelItems(map(HostItem, self.host_config["hosts"]))
        self.tree_hosts.itemSelectionChanged.connect(self._update_buttons)
        self.tree_hosts.model().dataChanged.connect(self._update_buttons)
        header = self.tree_hosts.header()
        header.setMinimumSectionSize(header.fontMetrics().width('M') * 8)
        header.setResizeMode(0, QtGui.QHeaderView.Stretch)
        header.setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        header.setMovable(False)
        try:
            self.tree_hosts.setCurrentItem((host for host in self.hosts() if host.is_connected()).next())
        except StopIteration:
            if self.tree_hosts.topLevelItemCount():
                self.tree_hosts.setCurrentItem(self.tree_hosts.topLevelItem(0))

    def hosts(self):
        return map(self.tree_hosts.topLevelItem, xrange(self.tree_hosts.topLevelItemCount()))

    def selectedItem(self):
        try:
            return self.tree_hosts.selectedItems()[0]
        except IndexError:
            return None

    @QtCore.pyqtSlot()
    def _update_buttons(self):
        host = self.selectedItem()

        can_connect = host is not None and not host.is_connected() and (host.is_alive() or host.is_local())
        can_disconnect = host is not None and host.is_connected()
        can_start = host is not None and not host.is_alive() and host.is_local()
        can_stop = host is not None and (host.is_connected() or host.is_alive())
        can_remove = host is not None and not host.is_connected()

        self.button_connect.setEnabled(can_connect)
        self.button_connect.setVisible(not can_disconnect)
        self.button_disconnect.setVisible(can_disconnect)
        self.button_start_daemon.setEnabled(can_start)
        self.button_start_daemon.setVisible(not can_stop)
        self.button_stop_daemon.setVisible(can_stop)
        self.button_remove.setEnabled(can_remove)

    @QtCore.pyqtSlot()
    def on_button_add_clicked(self):
        dialog = AddHostDialog(self)
        if dialog.exec_():
            try:
                i = self.hosts().index(dialog.host)
            except ValueError:
                self.tree_hosts.addTopLevelItem(dialog.host)
            else:
                self.tree_hosts.takeTopLevelItem(i)
                self.tree_hosts.insertTopLevelItem(i, dialog.host)

    @QtCore.pyqtSlot()
    def on_button_remove_clicked(self):
        self.tree_hosts.takeTopLevelItem(self.tree_hosts.currentIndex().row())

    @QtCore.pyqtSlot()
    def on_button_refresh_clicked(self):
        for host in self.hosts():
            host.update()

    @QtCore.pyqtSlot()
    def on_button_start_daemon_clicked(self):
        if not self.tree_hosts.topLevelItemCount():
            # Create localhost entry if no hosts are defined
            host = HostItem()
            self.tree_hosts.addTopLevelItem(host)
            host.setSelected(True)
        else:
            host = self.selectedItem()

        if component.get("ConnectionManager").start_daemon(host.config_tuple()):
            host.update()

    @QtCore.pyqtSlot(bool)
    @defer.inlineCallbacks
    def on_button_stop_daemon_clicked(self, clicked):
        host = self.selectedItem()
        if host.is_connected():
            yield client.daemon.shutdown()
        else:
            c = Client()
            yield c.connect(host.host, host.port, host.username, host.password)
            yield c.daemon.shutdown()
        host.update()

    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def on_tree_hosts_doubleClicked(self, index):
        self.on_button_connect_clicked()

    @QtCore.pyqtSlot(bool)
    @defer.inlineCallbacks
    def on_button_connect_clicked(self, checked=False):
        host = self.selectedItem() # NB: get it before accept closes and deletes the dialog
        self.accept()

        if client.connected():
            yield client.disconnect()

        component.get("ConnectionManager").connect(host.config_tuple(), autostart=not host.is_alive())

    @QtCore.pyqtSlot(bool)
    @defer.inlineCallbacks
    def on_button_disconnect_clicked(self, checked=False):
        host = self.selectedItem()
        if host.is_connected():
            yield client.disconnect()
            yield host.update()

    @QtCore.pyqtSlot(int)
    def done(self, result):
        self.ui_config["autoconnect"] = self.check_autoconnect.isChecked()
        self.ui_config["autostart_localhost"] = self.check_autostart.isChecked()
        self.ui_config["show_connection_manager_on_start"] = not self.check_do_not_show.isChecked()
        self.ui_config["connection_dialog_geometry"] = self.saveGeometry().toBase64().data()
        self.host_config["hosts"] = map(HostItem.config_tuple, self.hosts())

        super(ConnectionDialog, self).done(result)


class AddHostDialog(QtGui.QDialog, Ui_AddHostDialog):

    def __init__(self, parent):
        super(AddHostDialog, self).__init__(parent, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)
        self.setFixedHeight(self.sizeHint().height())

        self.text_host.textChanged.connect(self._update_buttons)
        self.text_port.valueChanged.connect(self._update_buttons)
        self._update_buttons()

        self.host = None

    @QtCore.pyqtSlot()
    def _update_buttons(self):
        self.button_box.button(QtGui.QDialogButtonBox.Ok).setEnabled(bool(self.text_host.text() and self.text_port.value()))

    @QtCore.pyqtSlot()
    def accept(self):
        self.host = HostItem((None, self.text_host.text(), self.text_port.value(), self.text_username.text(), self.text_password.text()))
        super(AddHostDialog, self).accept()
