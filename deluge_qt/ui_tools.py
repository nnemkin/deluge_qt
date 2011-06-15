#
# ui_tools.py
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

import os
import re
import pkg_resources

from PyQt4 import QtGui, QtCore
from xdg import IconTheme

import deluge.common
from deluge import configmanager

from .lang_tools import memoize


class TextProgressBar(QtGui.QProgressBar):
    """QProgressBar variant with the ability to set arbitrary label text."""

    def __init__(self, parent=None):
        QtGui.QProgressBar.__init__(self, parent)
        self._text = None

    def text(self):
        if self._text is not None:
            return self._text
        return QtGui.QProgressBar.text(self)

    def setText(self, value):
        if self._text != value:
            self._text = value
            self.repaint()


class ProgressBarDelegate(QtGui.QStyledItemDelegate):
    """Paint progress bar with the label given by DisplayRole and progress given by UserRole (float in [0;1] range)."""

    def __init__(self, parent=None):
        QtGui.QItemDelegate.__init__(self, parent)

        self.pb_option = QtGui.QStyleOptionProgressBar()
        self.pb_option.state = QtGui.QStyle.State_Enabled;
        self.pb_option.direction = QtGui.QApplication.layoutDirection();
        self.pb_option.fontMetrics = QtGui.QApplication.fontMetrics();
        self.pb_option.minimum = 0
        self.pb_option.maximum = 1000
        self.pb_option.textVisible = True
        self.pb_option.textAlignment = QtCore.Qt.AlignCenter

    def paint(self, painter, option, index):
        data = index.data(QtCore.Qt.UserRole)
        if data is not None:
            self.pb_option.rect = option.rect
            self.pb_option.progress = int(self.pb_option.maximum * data)
            self.pb_option.text = index.data(QtCore.Qt.DisplayRole)

            QtGui.QApplication.style().drawControl(QtGui.QStyle.CE_ProgressBar, self.pb_option, painter)
        else:
            QtGui.QStyledItemDelegate.paint(self, painter, option, index)


class HeightFixItemDelegate(QtGui.QStyledItemDelegate):
    """Crude fix row itemviews' row heights on Windows."""

    @classmethod
    def install(cls, widget):
        if deluge.common.windows_check():
            widget.setItemDelegate(cls(widget))

    def __init__(self, widget):
        QtGui.QStyledItemDelegate.__init__(self, widget)
        self._sizeHint = QtCore.QSize(1, widget.fontMetrics().height() * 1.5)

    def sizeHint(self, option, index):
        return self._sizeHint


class _IconLoader(object):

    def __init__(self):
        if not QtGui.QIcon.themeName(): # native theme support not available
            self.setThemeSearchPaths([pkg_resources.resource_filename("deluge_qt", "data/icons"),
                                      pkg_resources.resource_filename("deluge", "data/icons")])
            self.setThemeName("deluge")

    def setThemeName(self, name):
        QtGui.QIcon.setThemeName(name)

    def setThemeSearchPaths(self, paths):
        return QtGui.QIcon.setThemeSearchPaths(paths)

    def themeIcon(self, name, fallback=None):
        return QtGui.QIcon.fromTheme(name, fallback or QtGui.QIcon())

    def packageIcon(self, *paths):
        icon = QtGui.QIcon()
        for package in ("deluge", "deluge_qt"): # XXX: transient package name
            for path in paths:
                icon_file = pkg_resources.resource_filename(package, path)
                if os.path.isfile(icon_file):
                    icon.addFile(icon_file)
        return icon

    def packagePixmap(self, path):
        for package in ("deluge", "deluge_qt"): # XXX: transient package name
            filename = pkg_resources.resource_filename(package, path)
            if os.path.isfile(filename):
                return QtGui.QPixmap(filename)
        return QtGui.QPixmap()

    @memoize
    def customIcon(self, name):
        return self.packageIcon("data/pixmaps/" + name) # note: this is resource path, not FS path


class _CompatIconLoader(_IconLoader):

    def __init__(self):
        self.theme_name = None
        self.theme_paths = []
        self._theme_dirs = []

        _IconLoader.__init__(self)

    def themeName(self):
        return self.theme_name

    def setThemeName(self, name):
        self.theme_name = name
        self._theme_dirs = []
        self._add_theme(name)

    def setThemeSearchPaths(self, paths):
        self.theme_paths = paths

    def _add_theme(self, name):
        for theme_path in self.theme_paths:
            theme_file = os.path.join(theme_path, name, "index.theme")
            if os.path.isfile(theme_file):
                theme = IconTheme.IconTheme()
                theme.parse(theme_file)
                theme_dirs = []
                for dir in theme.getDirectories():
                    abs_dir = os.path.join(theme_path, theme.name, dir)
                    if os.path.isdir(abs_dir):
                        theme_dirs.append((abs_dir, theme.getType(dir) == "Scalable"))
                if theme_dirs:
                    self._theme_dirs.append(theme_dirs)

                for subtheme in theme.getInherits():
                    self._add_theme(subtheme)

    @memoize
    def themeIcon(self, name, fallback=None):
        # poor man's icon loader
        icon = QtGui.QIcon()
        for theme_dirs in self._theme_dirs:
            for dir, scalable in theme_dirs:
                icon_file = "%s/%s.%s" % (dir, name, 'svg' if scalable else 'png')
                if os.path.isfile(icon_file):
                    icon.addFile(icon_file)
            if not icon.isNull():
                return icon

        return fallback or QtGui.QIcon()


if QtCore.QT_VERSION >= 0x040600:
    IconLoader = _IconLoader()
else:
    IconLoader = _CompatIconLoader()


def context_menu_pos(view, event):
    """Calculate global popup menu position from QAbstractItmView's QContextMenuEvent"""
    current_index = view.currentIndex()
    if current_index.isValid():
        if event.reason() == QtGui.QContextMenuEvent.Keyboard:
            if view.allColumnsShowFocus():
                current_index = current_index.sibling(current_index.row(), 0)
            item_rect = view.visualRect(current_index)
            x, y = item_rect.left() + 8, (item_rect.top() + item_rect.bottom()) / 2
            pos = view.viewport().mapToGlobal(QtCore.QPoint(x, y))
        else:
            pos = event.globalPos()
        return pos


class HeaderActionList(QtGui.QActionGroup):

    def __init__(self, view):
        QtGui.QActionGroup.__init__(self, view)
        self.setExclusive(False)

        model = view.model()
        for i in xrange(model.columnCount(QtCore.QModelIndex())):
            self.addAction(QtGui.QAction(model.headerData(i, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole),
                                         self, checked=not view.isColumnHidden(i), checkable=True)).setData(i)
        view.header().setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        view.header().addActions(self.actions())

        self.triggered.connect(self._triggered)

    @QtCore.pyqtSlot(QtGui.QAction)
    def _triggered(self, action):
        self.parent().setColumnHidden(action.data(), not action.isChecked())


class WindowStateMixin(object):

    def __init__(self, window_state_variable=None):
        self.__ui_config = configmanager.ConfigManager("qtui.conf")
        self.window_state_variable = window_state_variable or self.objectName()
        try:
            state = self.__ui_config[self.window_state_variable]
        except KeyError:
            pass
        else:
            if "geometry" in state:
                self.restoreGeometry(QtCore.QByteArray.fromBase64(state["geometry"]))
            for key, widget in self._widgetsWithState():
                if key in state:
                    widget.restoreState(QtCore.QByteArray.fromBase64(state[key]))

    def saveWindowState(self):
        state = {"geometry": str(self.saveGeometry().toBase64())}
        for key, widget in self._widgetsWithState():
            state[key] = str(widget.saveState().toBase64())
        self.__ui_config[self.window_state_variable] = state

    def _widgetsWithState(self):
        from .torrent_details import TorrentDetails # TorrentDetails is a special QTabWidget with a state
        if isinstance(self, QtGui.QMainWindow):
            yield "state", self
        for child in sum((self.findChildren(cls) for cls in (QtGui.QSplitter, QtGui.QHeaderView, TorrentDetails)), []):
            yield (child.objectName() or child.parent().objectName()), child


def natsortkey(s):
    key = []
    for part in re.split(r"(\d+)", s.lower()):
        try:
            part = int(part)
        except:
            pass
        key.append(part)
    return key
