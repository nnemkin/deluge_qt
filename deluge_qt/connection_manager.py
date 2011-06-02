#
# connection_manager.py
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

from PyQt4 import QtGui
from twisted.internet import defer, reactor

from deluge import configmanager, component
from deluge.ui.client import client
from deluge.log import LOG as log


class ConnectionManager(component.Component):
    """Used by startup code and connection dialog."""

    default_host_config = {"hosts": [(uuid.uuid1().hex, "127.0.0.1", 58846, "", "")]}

    def __init__(self):
        super(ConnectionManager, self).__init__("ConnectionManager")

        self._started_classic = False
        self.ui_config = configmanager.ConfigManager("qtui.conf")

    def first_time(self):
        client.set_disconnect_callback(component.stop)

        if self.ui_config["classic_mode"]:
            self._start_classic()
        else:
            self._start_thin()

    def _start_classic(self):
        try:
            client.start_classic_mode()
        except Exception, e:
            from deluge.error import DaemonRunningError

            mb = QtGui.QMessageBox(standardButtons=QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
            mb.setDefaultButton(QtGui.QMessageBox.No)
            if isinstance(e, DaemonRunningError):
                mb.setWindowTitle(_("Turn off Classic Mode?"))
                mb.setText(_("It appears that a Deluge daemon process (deluged) is already running.\n\nYou will either need to stop the daemon or turn off Classic Mode to continue."))
                mb.setIcon(QtGui.QMessageBox.Question)
            else:
                mb.setWindowTitle(_("Error Starting Core"))
                mb.setText(_("There was an error starting the core component which is required to run Deluge in Classic Mode.\n\nPlease see the details below for more information."))
                mb.setInformativeText(_("Since there was an error starting in Classic Mode would you like to continue by turning it off?"))
                mb.setIcon(QtGui.QMessageBox.Warning)
                import traceback
                mb.setDetailedText(traceback.format_exc())
            if mb.exec_() == QtGui.QMessageBox.Yes:
                self._start_thin()
            else:
                reactor.stop()
        else:
            self.started_classic = True
            component.start()

    def _start_thin(self):
        host_config = configmanager.ConfigManager("hostlist.conf.1.2", self.default_host_config)

        if self.ui_config["autoconnect"]:
            for host in host_config["hosts"]:
                if host[0] == self.ui_config["autoconnect_host_id"]:
                    self.connect(host, autostart=self.ui_config["autostart_localhost"])

        if self.ui_config["show_connection_manager_on_start"]:
            from .connection_dialog import ConnectionDialog
            ConnectionDialog(component.get("MainWindow")).show()

    @defer.inlineCallbacks
    def connect(self, host, autostart=False):
        if autostart and host[1] in ("127.0.0.1", "localhost"):
            if self.start_daemon(host):
                for try_counter in range(6, -1, -1):
                    try:
                        yield client.connect(*host[1:])
                        component.start()
                    except Exception:
                        log.exception("Connection to host failed.")
                        import time
                        time.sleep(0.5) # XXX: twisted timers anyone?
                        if try_counter:
                            log.info("Retrying connection.. Retries left: %s", try_counter)
        else:
            yield client.connect(*host[1:])
            component.start()

    def start_daemon(self, host):
        try:
            if client.start_daemon(host[2], configmanager.get_config_dir()):
                return True
            else:
                QtGui.QMessageBox.critical(None,
                                           _("Error Starting Daemon"),
                                           _("There was an error starting the daemon process.  Try running it from a console to see if there is an error."))
        except Exception, e:
            if isinstance(e, OSError) and e.errno == 2:
                QtGui.QMessageBox.critical(None,
                                           _("Unable to start daemon!"),
                                           _("Deluge cannot find the 'deluged' executable, it is likely that you forgot to install the deluged package or it's not in your PATH."))
            else:
                import traceback
                QtGui.QMessageBox(QtGui.QMessageBox.Critical,
                                  _("Unable to start daemon!"),
                                  _("Please examine the details for more information."),
                                  QtGui.QMessageBox.Ok,
                                  None,
                                  detailedText=traceback.format_exc()).exec_()
        return False

    def shutdown(self):
        if self._started_classic:
            try:
                client.daemon.shutdown()
            except Exception:
                log.exception("Daemon shutdown.")
