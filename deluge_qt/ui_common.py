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
import posixpath
import logging

from PyQt4 import QtCore, QtGui

import deluge.common
from deluge import component

from .ui_tools import IconLoader, natsortkey

log = logging.getLogger(__name__)


class Column(object):

    _role_map = {"text": QtCore.Qt.DisplayRole, "icon": QtCore.Qt.DecorationRole, "toolTip": QtCore.Qt.ToolTipRole,
                 "align": QtCore.Qt.TextAlignmentRole, "checkState": QtCore.Qt.CheckStateRole,
                 "edit": QtCore.Qt.EditRole, "user": QtCore.Qt.UserRole, "sort": QtCore.Qt.UserRole + 1}

    def __init__(self, name, width=None, **kwargs):
        self.name = name
        self.width = width
        self.fields = set()
        self.formatters = {}
        self.augment(**kwargs)
        self.sorter = self.formatters.get(QtCore.Qt.UserRole + 1)

    def augment(self, **kwargs):
        for key, arg in kwargs.items():
            self._add_formatter(key, arg)

    def _add_formatter(self, key, arg):
        if isinstance(arg, tuple):
            func, fields = arg[0], arg[1:]
            if fields:
                formatter = lambda item: func(*(item[field] for field in fields))
            else:
                formatter = lambda item: func # func is a constant
            self.fields.update(fields)
        else:
            formatter = operator.itemgetter(arg)
            self.fields.add(arg)
        self.formatters[self._role_map[key]] = formatter


class BaseModel(QtCore.QAbstractItemModel):

    # NOTE: QModelIndex.internalPointer() does not count as a python reference, so care must be taken
    # to keep referenced objects alive.

    INVALID_INDEX = QtCore.QModelIndex()

    def __init__(self, parent):
        super(BaseModel, self).__init__(parent)

        self.columns = self._create_columns()
        self._clear()

        self.sort_column = None
        self.sort_args = None

    def _create_columns(self):
        raise NotImplementedError

    def _sort(self, column, reverse):
        raise NotImplementedError

    def _clear(self):
        raise NotImplementedError

    def fieldsForColumns(self, isColumnHidden=None):
        fields = set()
        for i, column in enumerate(self.columns):
            if not isColumnHidden or not isColumnHidden(i):
                fields.update(column.fields)
        fields.update(self.sort_column.fields)
        return list(fields)

    def columnsForFields(self, fields):
        return [i for i, column in enumerate(self.columns) if bool(column.fields.intersection(fields))]

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return _(self.columns[section].name)

    def columnCount(self, parent):
        return len(self.columns)

    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        self._sort(self.columns[column], (order == QtCore.Qt.DescendingOrder))
        self._updatePersistentIndexes()
        self.layoutChanged.emit()

    def clear(self):
        if QtCore.QT_VERSION >= 0x040600:
            self.beginResetModel()
            self._clear()
            self.endResetModel()
        else:
            self._clear()
            self.reset()

    def resize_header(self, header):
        em = header.fontMetrics().width('M') # not the actual em, but enough for initial sizing
        for i, column in enumerate(self.columns):
            header.resizeSection(i, column.width * em)


class DictModel(BaseModel):
    """Non-hierarchical model with a backing store of the form dict(item_id => dict(item_data))."""

    def _clear(self):
        self.order = []
        self.items = {}

    def _sort(self, column, reverse):
        self.sort_column = column
        self.sort_args = {"key": lambda id: column.sorter(self.items[id]), "reverse": reverse}
        self.order.sort(**self.sort_args)

    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return len(self.order)

    def index(self, row, column, parent=QtCore.QModelIndex()):
        try:
            return self.createIndex(row, column, self.order[row])
        except IndexError:
            return self.INVALID_INDEX

    def parent(self, index):
        return self.INVALID_INDEX

    def data(self, index, role):
        id = index.internalPointer()
        if id:
            try:
                return self.columns[index.column()].formatters[role](self.items[id])
            except (IndexError, KeyError):
                pass

    def _data_change_bounds(self, new_items):
        # NOTE: current (Qt 4.6) QAbstractItemModel implementation repaints the whole viewport regardless
        # of the arguments passed to dataChanged, so calculating precise change bounds is not really necessary
        changed_fields = set()
        top = bottom = None
        for i, id in enumerate(self.items):
            data, new_data = self.items[id], new_items[id]
            if new_data != data:
                changed_fields.update(field for field in new_data if new_data[field] != data.get(field))
                if top is None:
                    top = i
                bottom = i
        changed_columns = self.columnsForFields(changed_fields)
        return top, min(changed_columns), bottom, max(changed_columns)

    def update(self, new_items):
        if self.items != new_items:
            new_order = None
            sort_args = {"key": lambda id: self.sort_column.sorter(new_items[id]), "reverse": self.sort_args["reverse"]}
            if len(self.items) == len(new_items):
                try:
                    new_order = sorted(self.order, **sort_args)
                except KeyError:
                    pass
            if self.order == new_order:
                top, left, bottom, right = self._data_change_bounds(new_items)
                self.items = new_items
                self.dataChanged.emit(self.index(top, left), self.index(bottom, right))
            else:
                self.layoutAboutToBeChanged.emit()
                self.order = new_order or sorted(new_items.iterkeys(), **sort_args)
                self._updatePersistentIndexes()
                self.items = new_items # NB: updated after persistent indexes to keep old ids alive
                self.layoutChanged.emit()

    def _updatePersistentIndexes(self):
        old_indexes, new_indexes = [], []
        row_map = dict((id, i) for i, id in enumerate(self.order))
        for index in self.persistentIndexList():
            try:
                row = row_map[index.internalPointer()]
                if row != index.row():
                    old_indexes.append(index)
                    new_indexes.append(self.createIndex(row, index.column(), id))
            except KeyError:
                old_indexes.append(index)
                new_indexes.append(self.INVALID_INDEX)
        if new_indexes:
            self.changePersistentIndexList(old_indexes, new_indexes)


class FileModel(BaseModel):
    """Model for torrent files list."""

    filesRenamed = QtCore.pyqtSignal(object)
    folderRenamed = QtCore.pyqtSignal(str, str)
    indexesAdded = QtCore.pyqtSignal(object)

    class Item(object):

        def __init__(self, parent=None, name='', model=None, index=None):
            self.parent = parent
            self.model = model
            self.name = name
            self.index = index
            if parent:
                parent.children.append(self)
            self.children = []

        def __getitem__(self, name):
            return getattr(self, name) # assume exception is never thrown

        def is_file(self):
            return self.index is not None

        @property
        def size(self):
            if self.is_file():
                return self.model.files[self.index]["size"]
            return sum(child.size for child in self.children)

        def row(self):
            if self.parent:
                try:
                    return self.parent.children.index(self)
                except ValueError:
                    pass

        def invalidate(self):
            self.parent = None
            for child in self.children:
                child.invalidate()

        def sort(self, **kwargs):
            self.children.sort(**kwargs)
            for child in self.children:
                child.sort(**kwargs)

        def validate(self):
            if self.parent:
                assert self.name
            for child in self.children:
                assert child.parent == self
                child.validate()

    def __init__(self, parent, path=posixpath):
        super(FileModel, self).__init__(parent)
        self.path = path

    def _create_columns(self):
        icon_file = IconLoader.themeIcon("text-x-generic")
        icon_folder = IconLoader.themeIcon("folder")
        ficon = lambda index: icon_folder if index is None else icon_file

        return [Column('Filename', text="name", icon=(ficon, "index"), edit="name", sort=(natsortkey, "name"), width=45),
                Column('Size', text=(deluge.common.fsize, "size"), sort="size", width=10)]

    def _sort(self, column, reverse):
        self.sort_args = {"key": column.sorter, "reverse": reverse}
        self.root.sort(**self.sort_args)

    def _clear(self):
        self.root = self.Item()
        self.files = {}
        self.file_items = []

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0
        return len((parent.internalPointer() or self.root).children)

    def index(self, row, column, parent=QtCore.QModelIndex()):
        try:
            return self.createIndex(row, column, (parent.internalPointer() or self.root).children[row])
        except IndexError:
            return self.INVALID_INDEX

    def parent(self, index):
        item = index.internalPointer()
        if item:
            parent = item.parent
            if parent and parent != self.root:
                return self.createIndex(parent.row(), 0, parent)
        return self.INVALID_INDEX

    def data(self, index, role):
        item = index.internalPointer()
        if item:
            try:
                return self.columns[index.column()].formatters[role](item)
            except (IndexError, KeyError):
                pass

    def update(self, files):
        if self.files == files:
            return

        self.clear()

        items = {"": self.root}
        def _item(path):
            try:
                return items[path]
            except KeyError:
                parent_path, name = self.path.split(path)
                items[path] = new_item = self.Item(_item(parent_path), name)
                return new_item

        for i, file in enumerate(files):
            path, name = self.path.split(file["path"])
            self.file_items.append(self.Item(_item(path), name, self, i))

        self.files = files

    def flags(self, index):
        flags = super(FileModel, self).flags(index) | QtCore.Qt.ItemIsDragEnabled
        if index.column() == 0:
            flags |= QtCore.Qt.ItemIsEditable
        item = index.internalPointer()
        if not item or not item.is_file(): # NB: invalid index (not item) means root
            flags |= QtCore.Qt.ItemIsDropEnabled
        return flags

    def setData(self, index, value, role):
        item = index.internalPointer()
        if item and index.column() == 0 and role == QtCore.Qt.EditRole and item.name != value:
            if item.is_file():
                old_path = self.files[item.index]["path"]
                new_path = self.path.join(self.path.dirname(old_path), value)
                print 'FILE "%s" -> "%s"' % (old_path, new_path)
                self.filesRenamed.emit([(item.index, new_path)])
            else:
                parts = []
                while item.name:
                    parts.append(item.name)
                    item = item.parent
                if parts:
                    parts.reverse()
                    old_path = self.path.join(*parts) + self.path.sep
                    parts[-1] = value
                    new_path = self.path.join(*parts) + self.path.sep
                else:
                    old_path = ""
                    new_path = value
                print 'DIR "%s" -> "%s"' % (old_path, new_path)
                self.folderRenamed.emit(old_path, new_path)
            return True
        return False

    def _updatePersistentIndexes(self):
        old_indexes, new_indexes = [], []
        prev_item = None
        for index in self.persistentIndexList():
            item = index.internalPointer()
            if item != prev_item: # selection indexes often come in rows, save an row() call if possible
                row = item.row()
                prev_item = item
            if row is not None and row != index.row():
                old_indexes.append(index)
                new_indexes.append(self.createIndex(row, index.column(), item))
        if new_indexes:
            self.changePersistentIndexList(old_indexes, new_indexes)

    def _findItem(self, path):
        parent = self.root
        new_items = []
        for part in path.split("/"):
            if not part:
                continue
            for child in parent.children:
                if child.name == part:
                    parent = child
                    break
            else:
                new_item = self.Item(parent, part)
                new_items.append(new_item)
                parent.children.sort(**self.sort_args)
                parent = new_item
        return parent, new_items

    def _reparentItems(self, items, new_parent):
        self.layoutAboutToBeChanged.emit()
        for item in items:
            parent = item.parent
            parent.children.remove(item)
            item.parent = new_parent
            new_parent.children.append(item)
            self.root.validate()
            while parent and not parent.children: # kill empty folders
                next_parent = parent.parent
                next_parent.children.remove(parent)
                parent.invalidate()
                parent = next_parent
                self.root.validate()

        new_parent.children.sort(**self.sort_args)
        self._updatePersistentIndexes()
        self.layoutChanged.emit()

    def _renameItem(self, item, path):
        parent_path, name = self.path.split(path.rstrip(self.path.sep))
        new_parent, new_items = self._findItem(parent_path)

        item.name = name
        if item.parent != new_parent:
            self._reparentItems([item], new_parent)
            if new_items:
                self.indexesAdded.emit([self.createIndex(item.row(), 0, item) for item in new_items])
        else:
            index = self.createIndex(item.row(), 0, item)
            self.dataChanged.emit(index, index)

        self.root.validate()

    def renameFile(self, index, path):
        self.files[index]["path"] = path
        self._renameItem(self.file_items[index], path)

    def renameFolder(self, old_name, new_name):
        for i, file in enumerate(self.files):
            if file["path"].startswith(old_name):
                file["path"] = file["path"].replace(old_name, new_name, 1)
                item = self.file_items[i].parent
        self._renameItem(item, new_name)

    class ItemMimeData(QtCore.QMimeData):

        def __init__(self, items):
            super(FileModel.ItemMimeData, self).__init__()
            self.items = items

    def supportedDropActions(self):
        return QtCore.Qt.MoveAction

    def mimeTypes(self):
        return ["application/x-deluge-item-list"]

    def mimeData(self, indexes):
        items = [index.internalPointer() for index in indexes]
        parents = set()
        for item in items:
            parent = item.parent
            while parent and parent not in parents:
                parents.add(parent)
                parent = parent.parent
        if not parents.intersection(items): # we can't move items and their parents at the same time
            return self.ItemMimeData(items)

    def dropMimeData(self, data, action, row, column, parent):
        if action != QtCore.Qt.IgnoreAction and isinstance(data, self.ItemMimeData):
            items = [item for item in data.items if item.parent is not None]
            self._reparentItems(items, parent.internalIndex() or self.root)


class WidgetLoader(object):
    """Helper to quickly load config dicts into and from form widgets. Requires special widget naming scheme
       (see _sync_widgets)."""

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

    def __init__(self):
        self._icons = {None: QtGui.QIcon()}

    def _create_icon(self, filename):
        try:
            return self._icons[filename]
        except KeyError:
            pix = QtGui.QPixmap(filename)
            if not pix.hasAlpha():
                pix.setMask(pix.createHeuristicMask())
            self._icons[filename] = icon = QtGui.QIcon(pix)
            icon.addPixmap(pix, mode=QtGui.QIcon.Selected)
            return icon

    def get(self, host):
        return component.get("TrackerIcons").get_filename(host).addCallback(self._create_icon)

TrackerIconsCache = _TrackerIconsCache()
