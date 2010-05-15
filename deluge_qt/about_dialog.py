#
# about_dialog.py
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
#
from PyQt4 import QtGui, QtCore
from twisted.internet import defer

from deluge.ui.client import client
import deluge.common

from .generated.ui import Ui_AboutDialog, Ui_AboutLicenseDialog, Ui_AboutCreditsDialog


class AboutDialog(QtGui.QDialog, Ui_AboutDialog):

    def __init__(self, parent):
        super(AboutDialog, self).__init__(parent, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)

        self.label_about.setText(self.label_about.text().replace('?', deluge.common.get_version(), 1))

        if client.connected():
            self._get_versions()

    @defer.inlineCallbacks
    def _get_versions(self):
        text = self.label_about.text().replace('?', (yield client.daemon.info()), 1) \
                                      .replace('?', (yield client.core.get_libtorrent_version()), 1) \
                                      .replace('?', QtCore.QT_VERSION_STR, 1) \
                                      .replace('?', QtCore.PYQT_VERSION_STR, 1)
        self.label_about.setText(text)

    @QtCore.pyqtSlot()
    def on_button_credits_clicked(self):
        credits_dialog = QtGui.QDialog(self, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        Ui_AboutCreditsDialog().setupUi(credits_dialog)
        credits_dialog.show()

    @QtCore.pyqtSlot()
    def on_button_license_clicked(self):
        license_dialog = QtGui.QDialog(self, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        Ui_AboutLicenseDialog().setupUi(license_dialog)
        license_dialog.show()
