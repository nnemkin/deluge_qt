#
# ui_common.py
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

import operator
from collections import defaultdict

import sip
from PyQt4 import QtCore, QtGui
from twisted.internet import defer

import deluge.common
from deluge import component
from deluge.log import LOG as log

from .ui_tools import IconLoader


class TreeColumns(object):
    """QTreeView columns metadata collector."""

    def __init__(self):
        self.names = []
        self.widths = []
        self.sorters = []
        self.updaters = []
        self.updaters_by_field = defaultdict(list)

    def _add_sorter(self, arg):
        if isinstance(arg, tuple):
            formatter, fields = arg[0], arg[1:]
            sorter = lambda status: formatter(*(status[field] for field in fields))
        else:
            sorter = operator.itemgetter(arg)
        self.sorters.append(sorter)

    def _add_updater(self, column, role, const, arg):
        if isinstance(arg, tuple):
            formatter, fields = arg[0], arg[1:]
            def updater(item, status):
                value = formatter(*(status[field] for field in fields))
                if isinstance(value, defer.Deferred):
                    def set_data_cb(value):
                        if not sip.isdeleted(item):
                            item.setData(column, role, value)
                    value.addCallback(set_data_cb)
                else:
                    item.setData(column, role, value)
        else:
            fields = (arg,)
            def updater(item, status):
                item.setData(column, role, status[arg])
        updater.column = column
        updater.fields = fields

        self.updaters.append(updater)
        if not const:
            for field in fields:
                self.updaters_by_field[field].append(updater)

    def add(self, name, sort=None, width=10, const=False, **kwargs):
        column = len(self.names)
        for role, args in kwargs.items():
            role = {"text": QtCore.Qt.DisplayRole, "icon": QtCore.Qt.DecorationRole,
                    "user": QtCore.Qt.UserRole, "toolTip": QtCore.Qt.ToolTipRole}[role]
            self._add_updater(column, role, const, args)

        if sort:
            self._add_sorter(sort)
        self.names.append(name)
        self.widths.append(width)


class TreeItem(QtGui.QTreeWidgetItem):
    """TreeItem that uses TreeColumns metadata to initialize and update itself."""

    @classmethod
    def fields(cls, columns=None):
        fields = set()
        for updater in cls.columns.updaters:
            if not columns or columns[updater.column]:
                fields.update(updater.fields)
        return list(fields)

    def __init__(self, status, sort_column):
        super(TreeItem, self).__init__()

        self.status = status
        for updater in self.columns.updaters:
            updater(self, status)
        self.sort_column = None

    def update(self, new_status):
        if self.status != new_status:
            for field in new_status:
                if new_status[field] != self.status.get(field):
                    for updater in self.columns.updaters_by_field[field]:
                        updater(self, new_status)
            self.status = new_status
        self.sort_column = None

    def sort_key(self):
        if self.sort_column is None:
            self.sort_column = self.treeWidget().sortColumn() # NB: self.treeWidget() is abysmally slow
        return self.columns.sorters[self.sort_column](self.status)

    def __lt__(self, other):
        return self.sort_key() < other.sort_key()


class FileItem(QtGui.QTreeWidgetItem):
    """Generic file item for file trees. Provides name and size columns."""

    _icon_folder = IconLoader.themeIcon("folder")
    _icon_file = IconLoader.themeIcon("text-x-generic")

    def __init__(self, parent=None, name="", file=None):
        if isinstance(parent, list):
            parent.append(self)
            parent = None
        super(FileItem, self).__init__(parent)
        self.setText(0, name)
        self.setIcon(0, self._icon_file if file else self._icon_folder)
        self.file = file

    def _update_size(self):
        total_size = self.file["size"] if self.file else 0
        for item in self.children():
            total_size += item._update_size()
        self.setText(1, deluge.common.fsize(total_size))
        return total_size

    def setData(self, column, role, value):
        if column == 0 and role == QtCore.Qt.DisplayRole:
            # TODO: advanced renaming
            if "\\" in value or "/" in value:
                return

        super(FileItem, self).setData(column, role, value)

    def children(self):
        return (self.child(i) for i in xrange(self.childCount()))


class FileItemRoot(object):
    """Fake root item used to collect top level items for batch insertion in QTreeWidget."""

    item_type = FileItem
    name_sep = "/"

    def __init__(self, files):
        level = 0
        self._top_items = item = []
        self._file_items = [None] * len(files)
        prev_names = []
        for file in sorted(files, key=operator.itemgetter("path")):
            names = file["path"].split(self.name_sep)
            while names[:level] != prev_names[:level]: # XXX
                item = item.parent()
                level -= 1
            while len(names) - 1 > level:
                item = self.item_type(item, names[level])
                level += 1
            prev_names = names
            self._file_items[file["index"]] = self.item_type(item, names[-1], file)

        for item in self._top_items:
            item._update_size()

        self.files = files
        self.file = None

    def children(self):
        return self._top_items

    def text(self, column):
        return ""

    def addTo(self, widget):
        widget.clear()
        widget.addTopLevelItems(self._top_items)
        for item in self._top_items:
            item.setExpanded(True)

    def takeFrom(self, widget):
        self._top_items = widget.invisibleRootItem().takeChildren()


class WidgetLoader(object):
    """Helper to quickly load config dicts from and to form widgets. Requires special widget naming scheme."""

    @staticmethod
    def _set_value(widget, value):
        if isinstance(widget, QtGui.QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QtGui.QDoubleSpinBox):
            widget.setValue(float(value))
        elif isinstance(widget, QtGui.QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QtGui.QLineEdit):
            widget.setText(value)
        elif isinstance(widget, QtGui.QComboBox):
            if widget.property("userData"):
                widget.setCurrentIndex(widget.findData(value))
            else:
                widget.setCurrentIndex(int(value))
        elif isinstance(widget, QtGui.QRadioButton):
            if widget.group():
                (button for button in widget.group().buttons() if button.property("value") == value).next().setChecked(True)
            else:
                widget.setChecked(value)
        else:
            log.debug("__set_value: can\"t use widget %s", widget)

    @staticmethod
    def _get_value(widget):
        if isinstance(widget, QtGui.QSpinBox):
            return widget.value()
        if isinstance(widget, QtGui.QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QtGui.QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QtGui.QLineEdit):
            return widget.text()
        if isinstance(widget, QtGui.QComboBox):
            if widget.property("userData"):
                return widget.itemData(widget.currentIndex())
            return widget.currentIndex()
        if isinstance(widget, QtGui.QRadioButton):
            if widget.group():
                return widget.group().checkedButton().property("value")
            return widget.isChecked()
        log.debug("__get_value: can\"t use widget %s", widget)

    @classmethod
    def _sync_widgets(cls, parent, config, prefix, new_config=None):
        """Sync form widgets with config values. Mapping is recursive and uses special widget naming:
           config["key"]["subkey"][0] is synchronized with self.key__subkey__0"""
        for key, value in (enumerate(config) if isinstance(config, list) else config.items()):
            pkey = prefix + str(key)
            if isinstance(value, (list, dict)):
                if new_config:
                    new_config[key] = new_subconfig = type(value)()
                else:
                    new_subconfig = None
                cls._sync_widgets(parent, value, pkey + "__", new_subconfig)
            else:
                try:
                    widget = getattr(parent, pkey)
                except AttributeError:
                    log.debug("__sync_widgets: no widget for %s", pkey)
                else:
                    if new_config is not None: # save
                        new_config[key] = cls._get_value(widget)
                    else: # load
                        cls._set_value(widget, value)
        return new_config

    @classmethod
    def from_widgets(cls, parent, model, prefix=""):
        return cls._sync_widgets(parent, model, prefix, {})

    @classmethod
    def to_widgets(cls, data, parent, prefix=""):
        cls._sync_widgets(parent, data, prefix)


class _TrackerIconsCache(object):

    EMPTY_ICON = QtGui.QIcon()

    def __init__(self):
        self._icons = {}

    @defer.inlineCallbacks
    def __call__(self, host):
        try:
            defer.returnValue(self._icons[host])
        except KeyError:
            filename = yield component.get("TrackerIcons").get(host)
            self._icons[host] = icon = QtGui.QIcon(filename) if filename else self.EMPTY_ICON
            defer.returnValue(icon)

TrackerIconsCache = _TrackerIconsCache()
