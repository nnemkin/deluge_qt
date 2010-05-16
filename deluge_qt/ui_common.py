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

from PyQt4 import QtCore, QtGui
from twisted.internet import defer

import deluge.common
from deluge import component
from deluge.log import LOG as log

from .ui_tools import IconLoader


class ColumnModel(QtCore.QAbstractTableModel):

    # NOTE: QModelIndex.internalPointer() does not count as a python reference, so care must be taken
    # to keep referenced objects (item IDs) alive.

    INVALID_INDEX = QtCore.QModelIndex()

    class Column(object):

        def __init__(self, name, width=None, **kwargs):
            self.name = name
            self.width = width
            self.fields = set()
            self.formatters = {}
            for key, arg in kwargs.items():
                self._add_formatter(key, arg)
            self.sorter = self.formatters[QtCore.Qt.UserRole + 1]

        def _add_formatter(self, key, arg):
            role = {"text": QtCore.Qt.DisplayRole,
                    "icon": QtCore.Qt.DecorationRole,
                    "toolTip": QtCore.Qt.ToolTipRole,
                    "user": QtCore.Qt.UserRole,
                    "sort": QtCore.Qt.UserRole + 1}[key]
            if isinstance(arg, tuple):
                func, fields = arg[0], arg[1:]
                self.formatters[role] = lambda status: func(*(status[field] for field in fields))
                self.fields.update(fields)
            else:
                self.formatters[role] = operator.itemgetter(arg)
                self.fields.add(arg)

    def __init__(self, parent):
        super(ColumnModel, self).__init__(parent)

        self.items = {} # dict id -> data
        self.visual_order = [] # list of ids
        self.columns = self._create_columns() # subclass method
        self.sort_column = self.columns[0]
        self.sort_reverse = False

    def _create_columns(self):
        raise NotImplementedError

    def ids_from_indices(self, indices):
        return [index.internalPointer() for index in indices]

    def index_from_id(self):
        pass

    def fields(self, isColumnHidden=None):
        fields = set()
        for i, column in enumerate(self.columns):
            if not isColumnHidden or not isColumnHidden(i):
                fields.update(column.fields)
        fields.update(self.sort_column.fields)
        return list(fields)

    def clear(self):
        self.layoutAboutToBeChanged.emit()
        self.items = {}
        self.visual_order = []
        self.layoutChanged.emit()

    def rowCount(self, parent):
        return len(self.visual_order)

    def columnCount(self, parent):
        return len(self.columns)

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            return _(self.columns[section].name)

    def data(self, index, role):
        try:
            formatter = self.columns[index.column()].formatters[role]
            item = self.items[index.internalPointer()]
        except (IndexError, KeyError):
            pass
        else:
            return formatter(item)

    def index(self, row, column, parent=INVALID_INDEX):
        try:
            id = self.visual_order[row]
        except IndexError:
            return self.INVALID_INDEX
        else:
            return super(ColumnModel, self).createIndex(row, column, id)

    def _emit_changes(self, mask, stat_row, end_row):
        self.dataChanged.emit()

    def update(self, new_items):
        if self.items == new_items:
            return

        sort_args = {"key": lambda id: self.sort_column.sorter(new_items[id]), "reverse": self.sort_reverse}
        if len(self.items) == len(new_items):
            try:
                self.visual_order.sort(**sort_args)
            except KeyError:
                pass # new items are present
            else:
                # items are the same (and sorted properly), send dataChanged
                changed_fields = set()
                for id, data in self.items:
                    new_data = new_items[id]
                    changed_fields.update(field for field in new_data if new_data[field] != data.get(field))
                changed_columns = [i for i, column in enumerate(self.columns) if column.fields.issubset(changed_fields)]

                self.items = new_items
                self.dataChanged.emit(self.index(0, min(changed_columns)),
                                      self.index(len(self.items), max(changed_columns)))
                return

        # items are different, sort anew and send layoutChanged
        self.layoutAboutToBeChanged.emit()
        self.visual_order = sorted(new_items.iterkeys(), **sort_args)
        self._update_persistent_indices()
        self.items = new_items
        self.layoutChanged.emit()

    def sort(self, column, order):
        self.sort_column = self.columns[column]
        self.sort_reverse = (order == QtCore.Qt.DescendingOrder)
        self.layoutAboutToBeChanged.emit()
        self.visual_order.sort(key=lambda id: self.sort_column.sorter(self.items[id]), reverse=self.sort_reverse)
        self._update_persistent_indices()
        self.layoutChanged.emit()

    def _update_persistent_indices(self):
        indices = self.persistentIndexList()
        row_map = dict((id, row) for row, id in enumerate(self.visual_order))
        new_indices = []
        for index in indices:
            id = index.internalPointer()
            try:
                new_index = self.createIndex(row_map[id], index.column(), id)
            except KeyError:
                new_index = self.INVALID_INDEX
            new_indices.append(new_index)
        self.changePersistentIndexList(indices, new_indices)


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
        self._icons = {"": None}

    @defer.inlineCallbacks
    def __call__(self, host):
        try:
            defer.returnValue(self._icons[host])
        except KeyError:
            filename = yield component.get("TrackerIcons").get(host)
            self._icons[host] = icon = QtGui.QIcon(filename) if filename else self.EMPTY_ICON
            defer.returnValue(icon)

TrackerIconsCache = _TrackerIconsCache()
