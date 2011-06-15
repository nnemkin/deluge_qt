#
# new_release_dialog.py
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

import deluge.common
from deluge import configmanager

from .generated.ui import Ui_NewReleaseDialog


class NewReleaseDialog(QtGui.QDialog, Ui_NewReleaseDialog):

    def __init__(self, parent, new_version):
        QtGui.QDialog.__init__(self, parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)

        self.ui_config = configmanager.ConfigManager("qtui.conf")

        self.buttonBox.addButton(_("&Goto Website"), QtGui.QDialogButtonBox.AcceptRole)
        self.labelCurrentVersion.setText(deluge.common.get_version())
        self.labelAvailableVersion.setText(new_version)

    @QtCore.pyqtSlot(int)
    def done(self, result):
        self.ui_config["show_new_releases"] = not self.checkDoNotShow.isChecked()
        if result:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl("http://deluge-torrent.org"))
        QtGui.QDialog.done(self, result)
