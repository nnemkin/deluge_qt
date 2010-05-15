#
# qtui.py
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

import gettext
import pkg_resources

import sip
sip.setapi("QString", 2)
sip.setapi("QVariant", 2)
from PyQt4 import QtGui

from deluge.ui.ui import _UI


class QtUI(object):

    default_ui_config = {
        "language": "en",
#        "style": None,
        "classic_mode": True,
        "default_load_path": None,
        "interactive_add": True,
        "focus_add_dialog": True,
        "enable_system_tray": True,
        "close_to_tray": True,
        "start_in_tray": False,
        "lock_tray": False,
        "tray_password": "",
        "tray_download_speed_list": [5, 10, 30, 80, 300],
        "tray_upload_speed_list": [5, 10, 30, 80, 300],
        "connection_limit_list": [50, 100, 200, 300, 500],
        "show_connection_manager_on_start": True,
        "autoconnect": False,
        "autoconnect_host_id": None,
        "autostart_localhost": False,
        "show_new_releases": True,
        "ntf_tray_blink": True,
        "ntf_sound": False,
        "ntf_sound_path": "",
        "ntf_popup": False,
        "ntf_email": False,
        "ntf_email_add": "",
        "ntf_username": "",
        "ntf_pass": "",
        "ntf_server": "",
        "ntf_security": None,
        "show_rate_in_title": False,
        "sidebar_show_zero": False,
        "sidebar_show_trackers": True,
        "choose_directory_dialog_path": "",
    }

    def __init__(self, args):
        from deluge import configmanager, component

        ui_config = configmanager.ConfigManager("qtui.conf", self.default_ui_config)

#        if ui_config["style"] and '-style' not in args:
#            QtGui.QApplication.setStyle(ui_config["style"])
        app = QtGui.QApplication(args, applicationName="Deluge", quitOnLastWindowClosed=False)

        import qt4reactor
        qt4reactor.install()
        from twisted.internet import reactor
        reactor.runReturn(installSignalHandlers=False)

        self.locale_dir = pkg_resources.resource_filename("deluge", "i18n")

        from ui_tools import IconLoader
        app.setWindowIcon(IconLoader.themeIcon('deluge'))
        ui_config.register_set_function("language", self.on_language_change, apply_now=True)

        from deluge.ui.tracker_icons import TrackerIcons
        from deluge.ui.sessionproxy import SessionProxy
        from .connection_manager import ConnectionManager
        from .main_window import MainWindow
        from .plugin_manager import PluginManager

        TrackerIcons()
        SessionProxy()
        PluginManager()
        connection_manager = ConnectionManager()
        main_window = MainWindow()
        main_window.show()

        reactor.callLater(0, connection_manager.first_time)
        app.exec_()

        component.stop()
        component.shutdown()

        ui_config.save()

    def on_language_change(self, key, language):
        gettext.bindtextdomain("deluge", self.locale_dir)
        gettext.textdomain("deluge")
        if language:
            t = gettext.translation("deluge", self.locale_dir, languages=[language], class_=QtUITranslations, fallback=True)
            t.install(unicode=True)
            # QtCore.QLocale.setDefault(QtCore.QLocale(language))
        else:
            gettext.NullTranslations().install(unicode=True)


class QtUITranslations(gettext.GNUTranslations):
    """Custom translation class. Compensates for differences between Gtk+ and Qt4 UI strings."""

    def _try_ugettext(self, message):
        try:
            return self._catalog.get(message, u"") # hack
        except AttributeError:
            translated = gettext.GNUTranslations.ugettext(self, message) # NB: GNUTranslations is old-style class 
            return translated if translated != message else u""

    def ugettext(self, message):
        # 0. Try unchanged string
        # 1. Mnemonics: Gtk+ uses _ while Qt uses &
        # 2. Bold labels: gtkui uses markup, qtui uses label font
        # 3. Qt doubles genuine ampersands to distinguish them from mnemonics
        return self._try_ugettext(message) \
            or self._try_ugettext(message.replace("&", "_", 1)).replace(u"_", u"&", 1) \
            or self._try_ugettext("<b>" + message + "</b>")[3:-4] \
            or self._try_ugettext(message.replace("&&", "&")).replace(u"&", u"&&") \
            or unicode(message)


class Qt(_UI):

    help = """Starts the Deluge Qt interface"""

    def __init__(self):
        super(Qt, self).__init__("qt")

    def start(self):
        super(Qt, self).start()
        QtUI(self.args)


def start():
    Qt().start()
