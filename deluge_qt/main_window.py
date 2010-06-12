#
# main_window.py
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
from twisted.internet import defer, reactor

import deluge
from deluge import component, configmanager
from deluge.ui.client import client

from .generated.ui import Ui_MainWindow
from ui_tools import IconLoader, WindowStateMixin


class MainWindow(QtGui.QMainWindow, Ui_MainWindow, component.Component, WindowStateMixin):

    _pause_components = ["TorrentView", "TorrentDetails", "PeerView", "FileView", "StatusBar"]

    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        component.Component.__init__(self, "MainWindow", interval=3)

        self.ui_config = configmanager.ConfigManager("qtui.conf")
        self.core_config = {}

        self.setupUi(self)
        WindowStateMixin.__init__(self, "main_window")

        self.tree_filters.filter_changed.connect(self.tree_torrents.set_filter)
        self.tree_torrents.selection_changed.connect(self.set_torrent_ids)
        self.tree_torrents.selection_changed.connect(self.tabs_details.set_torrent_ids)
        self.tree_torrents.selection_changed.connect(self.tabs_details.tree_peers.set_torrent_ids)
        self.tree_torrents.selection_changed.connect(self.tabs_details.tree_files.set_torrent_ids)
        self.tree_torrents.selection_changed.connect(self.tabs_details.tab_options.set_torrent_ids)

        # action groups and states
        self.torrent_actions = QtGui.QActionGroup(self, exclusive=False, enabled=False)
        for name, widget in self.__dict__.iteritems():
            if name.startswith("action_torrent_"):
                self.torrent_actions.addAction(widget)
            elif name.startswith("menu_torrent_"):
                self.torrent_actions.addAction(widget.menuAction())
        self.global_actions = QtGui.QActionGroup(self, exclusive=False, enabled=False)
        for action in (self.action_add_torrent, self.action_quit_daemon):
            self.global_actions.addAction(action)

        self.menu_torrent.menuAction().setVisible(False)

        # notification area icon
        self.popup_menu_tray_mini = QtGui.QMenu()
        self.popup_menu_tray_mini.addActions([self.action_show, self.action_quit])
        self.tray_icon = QtGui.QSystemTrayIcon(QtGui.qApp.windowIcon(),
                                               toolTip=QtGui.qApp.applicationName(),
                                               activated=self.on_tray_icon_activated)
        self.tray_icon.setContextMenu(self.popup_menu_tray_mini)
        self.tray_icon.show()

        # dynamic menus
        self.menu_columns.addActions(self.tree_torrents.header().actions())
        self.menu_tabs.addActions(self.tabs_details.tabBar().actions())

        # action setup (note: some connections are already done in designer)
        self.action_show_toolbar.setChecked(not self.toolbar.isHidden())
        self.action_show_sidebar.setChecked(not self.tree_filters.isHidden())
        self.action_show_statusbar.setChecked(not self.statusbar.isHidden())

        self.upload_speed_actions = ConfigActionList(
            "max_upload_speed", self.ui_config["tray_upload_speed_list"], self, _("KiB/s"), _("Set Maximum Upload Speed"), 60000)
        self.download_speed_actions = ConfigActionList(
            "max_download_speed", self.ui_config["tray_download_speed_list"], self, _("KiB/s"), _("Set Maximum Download Speed"), 60000)
        self.max_connections_actions = ConfigActionList(
            "max_connections_global", self.ui_config["connection_limit_list"], self, "", _("Set Maximum Connections"), 9999)

        self.menu_download_speed.addActions(self.download_speed_actions.actions())
        self.menu_upload_speed.addActions(self.upload_speed_actions.actions())
        self.menu_max_connections.addActions(self.max_connections_actions.actions())

        self.torrent_upload_speed_actions = None
        self.torrent_download_speed_actions = None
        self.torrent_max_connections_actions = None

        # deluge events
        self.ui_config.register_set_function("show_rate_in_title", self.on_showRateInTitle_change, apply_now=False)
        self.ui_config.register_set_function("classic_mode", self.on_classicMode_change, apply_now=True)

        client.register_event_handler("NewVersionAvailableEvent",
                                      lambda: QtCore.QMetaObject.invokeMethod(self, "on_client_newVersionAvailable",
                                                                              QtCore.Qt.AutoConnection))
        client.register_event_handler("TorrentFinishedEvent", self.on_client_torrentFinished)

    @defer.inlineCallbacks
    def start(self):
        self.global_actions.setEnabled(True)
        self.menu_torrent.menuAction().setVisible(True)
        self.tray_icon.setContextMenu(self.popup_menu_tray)

        core_config = yield client.core.get_config_values(["max_connections_global", "max_download_speed", "max_upload_speed"])
        self.upload_speed_actions.setValue(core_config["max_upload_speed"])
        self.download_speed_actions.setValue(core_config["max_download_speed"])
        self.max_connections_actions.setValue(core_config["max_connections_global"])

    def stop(self):
        self.global_actions.setEnabled(False)
        self.torrent_actions.setEnabled(False)
        self.menu_torrent.menuAction().setVisible(False)
        self.tray_icon.setContextMenu(self.popup_menu_tray_mini)

        self.setWindowTitle(QtGui.qApp.applicationName())

    def shutdown(self):
        self.tray_icon.hide()
        self.saveWindowState()

    @defer.inlineCallbacks
    def update(self):
        if self.ui_config["show_rate_in_title"]:
            session_status = yield client.core.get_session_status(["download_rate", "upload_rate"])
            download_rate = deluge.common.fspeed(session_status["download_rate"])
            upload_rate = deluge.common.fspeed(session_status["upload_rate"])
            self.setWindowTitle("%s - %s %s %s %s" % (QtGui.qApp.applicationName(), _("Down:"), download_rate, _("Up:"), upload_rate))

    def closeEvent(self, event):
        reactor.stop()
        event.accept()

    @QtCore.pyqtSlot(object)
    def set_torrent_ids(self, torrent_ids):
        self.torrent_actions.setEnabled(bool(torrent_ids))

    def on_showRateInTitle_change(self, key, value):
        if value:
            self.update()
        else:
            self.setWindowTitle(QtGui.qApp.applicationName())

    def on_classicMode_change(self, key, value):
        self.action_connection_manager.setVisible(not value)

    def on_client_torrentFinished(self):
        pass # TODO: notifications

    @QtCore.pyqtSlot(str)
    def on_tree_torrents_torrentChanged(self, torrent_id):
        self.torrent_actions.setEnabled(torrent_id is not None)

    @QtCore.pyqtSlot(str)
    def on_client_newVersionAvailable(self, new_version):
        if self.ui_config["show_new_releases"]:
            from .new_release_dialog import NewReleaseDialog
            NewReleaseDialog(self, new_version).show()

    @QtCore.pyqtSlot(QtGui.QSystemTrayIcon.ActivationReason)
    def on_tray_icon_activated(self, reason):
        if reason in (QtGui.QSystemTrayIcon.Trigger, QtGui.QSystemTrayIcon.DoubleClick):
            self.action_show.toggle()

    @QtCore.pyqtSlot(bool)
    def on_action_show_toggled(self, checked):
        if self.isActiveWindow():
            self.setVisible(False)
        else:
            self.setVisible(True)
            self.activateWindow()

    @QtCore.pyqtSlot()
    def on_action_about_triggered(self):
        from .about_dialog import AboutDialog
        AboutDialog(self).show()

    @QtCore.pyqtSlot()
    def on_action_add_torrent_triggered(self):
        from .add_torrents_dialog import AddTorrentsDialog
        AddTorrentsDialog(self).show()

    @QtCore.pyqtSlot()
    def on_action_torrent_remove_triggered(self):
        torrent_ids = self.tree_torrents.selected_torrent_ids()
        if torrent_ids:
            mb = QtGui.QMessageBox(QtGui.QMessageBox.Warning, QtGui.qApp.applicationName(), _("Remove the selected torrent?"),
                                   QtGui.QMessageBox.Cancel, self, informativeText=_("If you remove the data, it will be lost permanently."))
            button_remove_all = QtGui.QPushButton(IconLoader.themeIcon("edit-delete"), _("Remove With &Data"), mb)
            button_remove_torrent = QtGui.QPushButton(IconLoader.themeIcon("list-remove"), _("Remove &Torrent"), mb)
            mb.addButton(button_remove_torrent, QtGui.QMessageBox.YesRole)
            mb.addButton(button_remove_all, QtGui.QMessageBox.YesRole)
            mb.setDefaultButton(QtGui.QMessageBox.Cancel)
            if mb.exec_() != QtGui.QMessageBox.Cancel:
                remove_data = (mb.clickedButton() == button_remove_all)
                for torrent_id in torrent_ids:
                    client.core.remove_torrent(torrent_id, remove_data)

    @QtCore.pyqtSlot()
    def on_action_torrent_pause_triggered(self):
        client.core.pause_torrent(self.tree_torrents.selected_torrent_ids())

    @QtCore.pyqtSlot()
    def on_action_torrent_resume_triggered(self):
        client.core.resume_torrent(self.tree_torrents.selected_torrent_ids())

    @QtCore.pyqtSlot()
    def on_action_torrent_queue_top_triggered(self):
        client.core.queue_top(self.tree_torrents.selected_torrent_ids())

    @QtCore.pyqtSlot()
    def on_action_torrent_queue_up_triggered(self):
        client.core.queue_up(self.tree_torrents.selected_torrent_ids())

    @QtCore.pyqtSlot()
    def on_action_torrent_queue_down_triggered(self):
        client.core.queue_down(self.tree_torrents.selected_torrent_ids())

    @QtCore.pyqtSlot()
    def on_action_torrent_queue_bottom_triggered(self):
        client.core.queue_bottom(self.tree_torrents.selected_torrent_ids())

    @QtCore.pyqtSlot()
    @defer.inlineCallbacks
    def on_action_torrent_move_storage_triggered(self):
        if client.is_localhost():
            new_save_path = QtGui.QFileDialog.getExistingDirectory(self, _("Choose a directory to move files to"),
                                                                   self.ui_config["choose_directory_dialog_path"])
            if new_save_path:
                self.ui_config["choose_directory_dialog_path"] = new_save_path
                client.core.move_storage(self.tree_torrents.selected_torrent_ids(), new_save_path)
        else:
            status = yield component.get("SessionProxy").get_torrent_status(self.tree_torrents.selected_torrent_id(), ["save_path"])
            new_save_path = QtGui.QInputDialog.getText(self, _("Move Storage"), _("Destination:"), text=status["save_path"])[0];
            if new_save_path:
                client.core.move_storage(self.tree_torrents.selected_torrent_ids(), new_save_path)

    @QtCore.pyqtSlot()
    def on_action_preferences_triggered(self):
        from .preferences_dialog import PreferencesDialog
        PreferencesDialog(self).show()

    @QtCore.pyqtSlot()
    def on_action_quit_daemon_triggered(self):
        client.daemon.shutdown().addCallback(lambda result: self.close())

    @QtCore.pyqtSlot()
    def on_action_homepage_triggered(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl("http://deluge-torrent.org/"))

    @QtCore.pyqtSlot()
    def on_action_faq_triggered(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl("http://dev.deluge-torrent.org/wiki/Faq"))

    @QtCore.pyqtSlot()
    def on_action_community_triggered(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl("http://forum.deluge-torrent.org/"))

    @QtCore.pyqtSlot()
    def on_action_connection_manager_triggered(self):
        from .connection_dialog import ConnectionDialog
        ConnectionDialog(self).show()

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.WindowStateChange:
            if self.isMinimized():
                component.pause(self._pause_components)
            else:
                component.resume(self._pause_components)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and client.connected():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        if urls:
            from .add_torrents_dialog import AddTorrentsDialog
            dialog = AddTorrentsDialog(self)
            dialog.show()
            dialog.activateWindow()
            dialog.raise_()
            dialog.add_torrents(urls)


class ConfigActionList(QtGui.QActionGroup):
    """List of actions for upload/download speed and max connections menus."""

    def __init__(self, config_key, values, parent=None, suffix="", custom_label=None, custom_max=None):
        super(ConfigActionList, self).__init__(parent)

        self.config_key = config_key
        self.custom_label = custom_label
        self.custom_max = custom_max
        self.value = None

        for value in values:
            self.addAction(QtGui.QAction(unicode(value) + suffix, self,
                                         checkable=True, triggered=self._value_triggered)).setData(value)

        self.addAction(QtGui.QAction(_("Unlimited"), self,
                                     checkable=True, triggered=self._value_triggered)).setData(-1)
        self.addAction(QtGui.QAction(self)).setSeparator(True)
        self.custom_action = self.addAction(QtGui.QAction(_("Other..."), self, triggered=self._custom_triggered))

        client.register_event_handler("ConfigValueChangedEvent", self._client_configvaluechanged)

    def setValue(self, value):
        if self.value != value:
            self.value = value
            for action in self.actions():
                if action.data() == value:
                    action.setChecked(True)
                    self.custom_action.setCheckable(False)
                    break
            else:
                self.custom_action.setData(value)
                self.custom_action.setCheckable(True)
                self.custom_action.setChecked(True)

    def _client_configvaluechanged(self, key, value):
        if key == self.config_key:
            self.setValue(value)

    @QtCore.pyqtSlot()
    def _value_triggered(self):
        value = self.sender().data()
        if value != self.value:
            client.core.set_config({self.config_key: value})

    @QtCore.pyqtSlot()
    def _custom_triggered(self):
        value, result = QtGui.QInputDialog.getInt(QtGui.qApp.activeWindow(), "", self.custom_label, self.value, -1, self.custom_max)
        if result and value != self.value:
            client.core.set_config({self.config_key: value})
