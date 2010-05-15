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
import pkg_resources

from PyQt4 import QtGui, QtCore
from xdg import IconTheme

from deluge.log import LOG as log
import deluge.common

from .lang_tools import memoize


def header_view_actions(widget):
    def section_action_triggered():
        pass

    model = widget.model()
    return [QtGui.QAction(model.headerData(i, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole), widget.header(),
                          checked=True,
                          checkable=True,
                          triggered=section_action_triggered) for i in xrange(model.columnCount())]


class TextProgressBar(QtGui.QProgressBar):

    def __init__(self, parent=None):
        super(TextProgressBar, self).__init__(parent)
        self._text = None

    def text(self):
        return self._text if self._text is not None else super(TextProgressBar, self).text()

    def setText(self, value):
        if self._text != value:
            self._text = value
            self.repaint()


class ProgressBarDelegate(QtGui.QStyledItemDelegate):

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
            super(ProgressBarDelegate, self).paint(painter, option, index)


class HeightFixItemDelegate(QtGui.QStyledItemDelegate):
    """Crude fix row itemviews' row heights on Windows."""

    @classmethod
    def install(cls, widget):
        if deluge.common.windows_check():
            widget.setItemDelegate(cls(widget))

    def __init__(self, widget):
        super(HeightFixItemDelegate, self).__init__(widget)
        self._sizeHint = QtCore.QSize(1, widget.fontMetrics().height() * 1.5)

    def sizeHint(self, option, index):
        return self._sizeHint


class QtBug7674ItemDelegate(HeightFixItemDelegate):
    """QTBUG-7674 workaround (incorrect tristate behavior of item checkboxes), affected versions are 4.6.0-4.6.2."""

    @classmethod
    def install(cls, widget):
        if QtCore.QT_VERSION >= 0x040600 and QtCore.QT_VERSION <= 0x040602:
            log.debug("QTBUG-7674 workaround in effect")
            widget.setItemDelegate(cls(widget))

    class Proxy(QtGui.QAbstractProxyModel):

        def mapFromSource(self, arg): return arg
        def mapToSource(self, arg): return arg
        def flags(self, index): return self.sourceModel().flags(index) & ~QtCore.Qt.ItemIsTristate

    def __init__(self, parent=None):
        super(QtBug7674ItemDelegate, self).__init__(parent)
        self._proxy = self.Proxy(self)

    def editorEvent(self, event, model, option, index):
        if self._proxy.sourceModel() != model:
            self._proxy.setSourceModel(model)
        return super(QtBug7674ItemDelegate, self).editorEvent(event, self._proxy, option, index)


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

    def packageIcon(self, path):
        icon = QtGui.QIcon()
        paths = (path,) if isinstance(path, basestring) else path
        for package in ("deluge", "deluge_qt"): # XXX: transient package name
            for path in paths:
                icon_file = pkg_resources.resource_filename(package, path)
                if os.path.isfile(icon_file):
                    icon.addFile(icon_file)
        return icon

    @memoize
    def customIcon(self, name):
        return self.packageIcon("data/pixmaps/" + name) # note: this is resource path, not FS path


class _CompatIconLoader(_IconLoader):

    def __init__(self):
        self.theme_name = None
        self.theme_paths = []
        self._theme_dirs = []

        super(_CompatIconLoader, self).__init__()

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
            if not icon.isNull(): # XXX: use availableSizes() in PyQt 4.5+
                return icon

        return fallback or QtGui.QIcon()


if QtCore.QT_VERSION >= 0x040600:
    IconLoader = _IconLoader()
else:
    IconLoader = _CompatIconLoader()


def treeContextMenuHandler(widget, event, menu):
    """Calculate global popup menu position from QTreeWidget's QContextMenuEvent"""
    items = widget.selectedItems()
    if items:
        if event.reason() == QtGui.QContextMenuEvent.Keyboard:
            item_rect = widget.visualItemRect(items[0])
            pos = widget.viewport().mapToGlobal(QtCore.QPoint(widget.width() / 5, item_rect.bottom()))
        else:
            pos = event.globalPos()
        menu.popup(pos)
