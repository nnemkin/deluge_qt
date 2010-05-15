#
# preferences_dialog.py
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

import pkg_resources

from PyQt4 import QtGui, QtCore
from twisted.internet import defer

from deluge.log import LOG as log
from deluge.ui.client import client
from deluge import configmanager, component

from .generated.ui import Ui_PreferencesDialog
from .ui_common import WidgetLoader
from .ui_tools import IconLoader


PROXY_NONE, PROXY_SOCKS5_AUTH, PROXY_HTTP_AUTH = 0, 3, 5


class PreferencesDialog(QtGui.QDialog, Ui_PreferencesDialog):

    _small_icon_size = QtGui.qApp.style().pixelMetric(QtGui.QStyle.PM_SmallIconSize)

    def __init__(self, parent, initial_tab=None):
        super(PreferencesDialog, self).__init__(parent, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)

        self.core__label_test_active_port.setFixedWidth(self._small_icon_size)

        self.ui_config = configmanager.ConfigManager("qtui.conf")
        self.core_config = None
        self.plugins = None
        self.enabled_plugins = None

        # load languages
        self.ui__language.addItem(_("Default"), None)
        for locale_name in pkg_resources.resource_listdir("deluge", "i18n"):
            locale_name = locale_name[:-3]
            locale = QtCore.QLocale(locale_name)
            if locale != QtCore.QLocale.c():
                lang_name = locale.languageToString(locale.language())
                if "_" in locale_name:
                    lang_name = "%s (%s)" % (lang_name, locale.countryToString(locale.country()))
                self.ui__language.addItem(lang_name, locale_name)

        # load styles
#        self.ui__style.addItem(_("Default"), None)
#        for style_name in QtGui.QStyleFactory.keys():
#            self.ui__style.addItem(style_name, style_name)

        if initial_tab:
            self.list_categories.setCurrentRow(self.stack_categories.indexOf(getattr(self, "page_" + initial_tab)))

    @defer.inlineCallbacks
    def _load_config(self):
        if client.connected():
            self.core_config = yield client.core.get_config()
            self.plugins = yield client.core.get_available_plugins()
            self.enabled_plugins = yield client.core.get_enabled_plugins()
            listen_port = yield client.core.get_listen_port()
            cache_status = yield client.core.get_cache_status()

            WidgetLoader.to_widgets(self.core_config, self, "core__")
            self.core__label_active_port.setText(str(listen_port))
            self._update_cache_status(cache_status)
            self._update_plugins()

            if not client.is_localhost():
                for key, widget in self.__dict__.iteritems():
                    if key.endswith("_browse"):
                        widget.setVisible(False)
        else:
            for key, widget in self.__dict__.iteritems():
                if key.startswith("core__"):
                    widget.setEnabled(False)

        WidgetLoader.to_widgets(self.ui_config.config, self, "ui__")

    def _save_config(self):
        # ui config
        new_config = WidgetLoader.from_widgets(self, self.ui_config.config, "ui__")
        for key in new_config.keys():
            if self.ui_config[key] != new_config[key]:
                self.ui_config[key] = new_config[key]

        # core config
        if self.core_config and client.connected():
            new_config = WidgetLoader.from_widgets(self, self.core_config, "core__")
            client.core.set_config(dict((key, new_config[key])
                                        for key in new_config.keys() if self.core_config[key] != new_config[key]))
            client.force_call(True)
            self.core_config = new_config

    def _update_cache_status(self, cache_status):
        for key, value in cache_status.items():
            try:
                widget = getattr(self, "label_cache_" + key)
            except AttributeError:
                log.debug("No cache label for %s", key)
            else:
                if isinstance(value, float):
                    value = "%.2f" % value
                else:
                    value = str(value)
                widget.setText(value)

    def _update_plugins(self):
        self.list_plugins.clear()
        for plugin in self.plugins:
            item = QtGui.QListWidgetItem(plugin, self.list_plugins)
            item.setCheckState(QtCore.Qt.Checked if plugin in self.enabled_plugins else QtCore.Qt.Unchecked)

    def showEvent(self, event):
        self._load_config()
        super(PreferencesDialog, self).showEvent(event)

    # NB: connected in designer
    @QtCore.pyqtSlot(int)
    def on_browse_clicked(self):
        widget = getattr(self, self.sender().objectName().replace("_browse", ""))
        selected = widget.text() or None
        if widget in (self.ui__ntf_sound_path, self.core__geoip_db_location):
            selected = QtGui.QFileDialog.getOpenFileName(self, directory=selected)
        else:
            selected = QtGui.QFileDialog.getExistingDirectory(self, directory=selected)
        if selected:
            widget.setText(QtCore.QDir.toNativeSeparators(selected))

    # NB: connected in designer
    @QtCore.pyqtSlot(int)
    def on_proxy_type_currentIndexChanged(self, proxy_type):
        prefix = self.sender().objectName().replace("__type", "")

        needs_auth = proxy_type in (PROXY_SOCKS5_AUTH, PROXY_HTTP_AUTH)
        needs_host = proxy_type != PROXY_NONE

        for suffix in ("__hostname", "__hostname_label", "__port", "__port_label"):
            getattr(self, prefix + suffix).setVisible(needs_host)
        for suffix in ("__username", "__username_label", "__password", "__password_label"):
            getattr(self, prefix + suffix).setVisible(needs_auth)

    @QtCore.pyqtSlot()
    def on_button_box_clicked(self, button):
        if self.button_box.standardButton(button) == QtGui.QDialogButtonBox.Apply:
            self._save_config()
            # XXX: gtkui does self.show() at this point

    @QtCore.pyqtSlot()
    @defer.inlineCallbacks
    def on_core__button_refresh_cache_status_clicked(self):
        self._update_cache_status((yield client.core.get_cache_status()))

    @QtCore.pyqtSlot()
    def on_button_associate_magnet_clicked(self):
        pass # TODO

    @QtCore.pyqtSlot()
    def on_button_plugin_install(self):
        filter = "%s (%s);;%s (%s)" % (_("Plugin Eggs"), "*.egg", _("All files"), "*")
        filename = QtGui.QFileDialog.getOpenFileName(self, _("Select the Plugin"), None, filter)
        if filename:
            import shutil
            import os.path

            filename = QtCore.QDir.toNativeSeparators(filename)
            basename = os.path.basename(filename)
            shutil.copyfile(filename, os.path.join(configmanager.get_config_dir(), "plugins", basename))

            component.get("PluginManager").scan_for_plugins()

            if not client.is_localhost():
                # We need to send this plugin to the daemon
                import base64
                with open(filename, 'rb') as f:
                    filedump = base64.encodestring(f.read())
                client.core.upload_plugin(basename, filedump)

            client.core.rescan_plugins()
            self._update_plugins()

    @QtCore.pyqtSlot()
    def on_button_plugin_rescan(self):
        component.get("PluginManager").scan_for_plugins()
        if client.connected():
            client.core.rescan_plugins()

    @QtCore.pyqtSlot()
    def on_button_find_plugins(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl("http://dev.deluge-torrent.org/wiki/Plugins"))

    @QtCore.pyqtSlot()
    def on_list_plugins_itemSelectionChanged(self):
        try:
            item = self.list_plugins.selectedItems()[0]
        except IndexError:
            pass
        else:
            plugin_info = component.get("PluginManager").get_plugin_info(item.text())
            self.label_plugin_name.setText(plugin_info["Name"])
            self.label_plugin_author.setText(plugin_info["Author"])
            self.label_plugin_version.setText(plugin_info["Version"])
            self.label_plugin_email.setText('<a href="mailto:%s">%s</a>' % (plugin_info["Author-email"], plugin_info["Author-email"]))
            self.label_plugin_homepage.setText('<a href="%s">%s</a>' % (plugin_info["Home-page"], plugin_info["Home-page"]))
            self.label_plugin_details.setText(plugin_info["Description"])

    @QtCore.pyqtSlot(QtGui.QListWidgetItem, QtGui.QListWidgetItem)
    def on_list_plugins_itemChanged(self, item):
        name = item.text()
        if item.checkState() == QtCore.Qt.Checked:
            client.core.enable_plugin(name)
        else:
            client.core.disable_plugin(name)
            component.get("PluginManager").disable_plugin(name)

    @QtCore.pyqtSlot()
    @defer.inlineCallbacks
    def on_core__button_test_active_port_clicked(self):
        status = yield client.core.test_listen_port()
        if status:
            icon = IconLoader.customIcon("gtk-yes.png")
        else:
            icon = IconLoader.themeIcon("dialog-warning")
        self.core__label_test_active_port.setPixmap(icon.pixmap(self._small_icon_size))

    @QtCore.pyqtSlot()
    def accept(self):
        self._save_config()
        super(PreferencesDialog, self).accept()
