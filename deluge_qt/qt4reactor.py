#
# qt4reactor.py
#
# Copyright (c) 2001-2011 Twisted Matrix Laboratories.
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

import sys

from zope.interface import implements

from twisted.python import log
from twisted.internet.error import ConnectionFdescWentAway
from twisted.internet.interfaces import IReactorFDSet
from twisted.internet.posixbase import PosixReactorBase

from PyQt4.QtCore import (Qt, QObject, QMetaObject, SIGNAL, QCoreApplication, QEventLoop,
                          QTimer, QSocketNotifier, pyqtSignature)


class Qt4Reactor(QObject, PosixReactorBase):
    implements(IReactorFDSet)

    # Note: @pyqtSignature is necessary for QMetaObject.invokeMethod() to work.
    # @pyqtSlot is not used for compatibility with PyQt versions before 4.5.
    # Note: Twisted 10.0 and earlier is unable to wake up Qt event loop on SIGCHLD.
    # This does not pose a problem for GUI apps and was fixed in Twisted 10.1 so no workaround here.

    def __init__(self):
        QObject.__init__(self)

        self._readers = {}
        self._writers = {}
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self.connect(self._timer, SIGNAL("timeout()"), self._timerSlot)

        self._eventLoop = QCoreApplication.instance()
        if self._eventLoop is None:
            # create dummy application for testing
            self._eventLoop = QCoreApplication([])

        PosixReactorBase.__init__(self)  # goes last, because it calls addReader

    def _scheduleSimulation(self, timeout=0):
        if timeout is None:
            self._timer.stop()
        else:
            self._timer.start(timeout * 1000)

    @pyqtSignature("")
    def _timerSlot(self):
        self.runUntilCurrent()
        self._scheduleSimulation(self.timeout())

    def _addNotifier(self, descriptor, descmap, type):
        if descriptor not in descmap:
            fd = descriptor.fileno()
            if fd == -1:
                raise RuntimeError("Invalid file descriptor")
            notifier = QSocketNotifier(fd, type)
            descmap[descriptor] = notifier
            notifier._descriptor = descriptor
            self.connect(notifier, SIGNAL("activated(int)"), self._notifierSlot)
            notifier.setEnabled(True)

    def _removeNotifier(self, descriptor, descmap):
        notifier = descmap.pop(descriptor, None)
        if notifier is not None:
            notifier.setEnabled(False)
            self.disconnect(notifier, SIGNAL("activated(int)"), self._notifierSlot)
            notifier._descriptor = None
            notifier.deleteLater()

    @pyqtSignature("")
    def _notifierSlot(self):
        # Note: in some tests on Ubuntu 10.4 (PyQt 4.7.2) new-style signal connections result
        # in NULL QObject.sender() here. Old style signal connections do not have this problem.
        notifier = self.sender()
        notifier.setEnabled(False)
        descriptor = notifier._descriptor
        if descriptor is None:
            return
        isRead = (notifier.type() == notifier.Read)
        try:
            if isRead:
                why = descriptor.doRead()
            else:
                why = descriptor.doWrite()
        except:
            log.err()
            why = sys.exc_info()[1]
        if descriptor.fileno() != notifier.socket():
            why = ConnectionFdescWentAway('Filedescriptor went away')
        if why:
            self._disconnectSelectable(descriptor, why, isRead)
        elif notifier._descriptor:  # check if not disconnected in doRead/doWrite
            notifier.setEnabled(True)

        # Twisted (FTP) expects due timed events to be delivered after each IO event,
        # so that invoking callLater(0, fn) from IO callback results in fn() being called before
        # the next IO callback.
        self.runUntilCurrent()

    def addReader(self, reader):
        self._addNotifier(reader, self._readers, QSocketNotifier.Read)

    def addWriter(self, writer):
        self._addNotifier(writer, self._writers, QSocketNotifier.Write)

    def removeReader(self, reader):
        self._removeNotifier(reader, self._readers)

    def removeWriter(self, writer):
        self._removeNotifier(writer, self._writers)

    def removeAll(self):
        return self._removeAll(self._readers, self._writers)

    def getReaders(self):
        return self._readers.keys()

    def getWriters(self):
        return self._writers.keys()

    def callLater(self, *args, **kwargs):
        result = PosixReactorBase.callLater(self, *args, **kwargs)
        self._scheduleSimulation()
        return result

    def _moveCallLaterSooner(self, tple):
        result = PosixReactorBase._moveCallLaterSooner(self, tple)
        self._scheduleSimulate()
        return result

    def doIteration(self, delay):
        # Note: some tests fail on Ubuntu 10.4 when processEvents is called with zero delay.
        # Setting the minimal delay to something > 0 or or calling processEvents() twice
        # fixes the problem.
        self._eventLoop.processEvents(QEventLoop.AllEvents, max(1, delay) * 1000)

    def mainLoop(self):
        self._eventLoop.exec_()

    def stop(self):
        PosixReactorBase.stop(self)
        self._scheduleSimulation()

    def crash(self):
        PosixReactorBase.crash(self)
        self._eventLoop.quit()

    if sys.platform == "win32":
        # On Windows, we can wake up by simply posting a message to the main loop.
        # Other systems call wakeUp() from unix signal handlers (which are forbidden from making
        # any Qt calls) and have to use the default pipe based waker.

        def installWaker(self):
            pass

        def wakeUp(self):
            QMetaObject.invokeMethod(self, "_timerSlot", Qt.QueuedConnection)


def install():
    from twisted.internet.main import installReactor
    reactor = Qt4Reactor()
    installReactor(reactor)
    return reactor


__all__ = ["install"]
