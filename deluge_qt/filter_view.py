#
# filter_view.py
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
from twisted.internet import defer

from deluge import component, configmanager
from deluge.ui.client import client

from .ui_common import TrackerIconsCache
from .ui_tools import HeightFixItemDelegate, IconLoader, treeContextMenuHandler


class FilterValueItem(QtGui.QTreeWidgetItem):

    _state_icons = {"All": IconLoader.customIcon("all16.png"),
                    "Downloading": IconLoader.customIcon("downloading16.png"),
                    "Seeding": IconLoader.customIcon("seeding16.png"),
                    "Paused": IconLoader.customIcon("inactive16.png"),
                    "Checking": IconLoader.customIcon("checking16.png"),
                    "Queued": IconLoader.customIcon("queued16.png"),
                    "Error": IconLoader.customIcon("alert16.png"),
                    "Active": IconLoader.customIcon("active16.png")}
    _default_state_icon = IconLoader.customIcon('dht16.png')

    def __init__(self, cat, value, count):
        super(FilterValueItem, self).__init__()

        self.value = value
        self.count = count
        self.setText(0, "%s (%d)" % (value, count))

        if cat == "state" or value in ("All", "Error"):
            self.setIcon(0, self._state_icons.get(value, self._default_state_icon))
        elif cat == "tracker_host":
            TrackerIconsCache(value).addCallback(lambda icon: self.setIcon(0, icon))

    def update(self, value, count):
        if self.count != count:
            self.count = count
            self.setText(0, '%s (%d)' % (value, count))

    def filter_dict(self):
        if self.parent().cat == "state" and self.value == "All":
            return {}
        return {self.parent().cat: self.value}


class FilterCategoryItem(QtGui.QTreeWidgetItem):

    _cat_names = {"state": "States", "tracker_host": "Trackers", "label": "Labels"}

    _font = QtGui.QFont()
    _font.setBold(True)

    def __init__(self, cat, values):
        super(FilterCategoryItem, self).__init__()
        self.cat = cat
        self.items_by_value = {}
        self.setText(0, _(self._cat_names.get(cat, cat)))
        # self.setBackground(0, QtGui.qApp.palette().alternateBase())
        self.setFlags(QtCore.Qt.ItemIsEnabled) # not selectable
        self.setFont(0, self._font)
        self.update(values)

    def update(self, values):
        new_items = []
        for value, count in values:
            try:
                self.items_by_value[value].update(value, count)
            except KeyError:
                item = FilterValueItem(self.cat, value, count)
                self.items_by_value[value] = item
                new_items.append(item)

        value_set = frozenset(value for (value, count) in values)
        for value, item in self.items_by_value.iteritems():
            item.setHidden(value not in value_set)

        if new_items:
            self.addChildren(new_items)


class FilterView(QtGui.QTreeWidget, component.Component):

    filter_changed = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        component.Component.__init__(self, "FilterView", interval=2)

        HeightFixItemDelegate.install(self)

        self.items_by_cat = {}
        self.filters = {}

        self.ui_config = configmanager.ConfigManager("qtui.conf")

        self.itemSelectionChanged.connect(self.on_itemSelectionChanged)

    def stop(self):
        self.clear()
        self.items_by_cat = {}
        self.filters = {}

    @defer.inlineCallbacks
    def update(self):
        hide_cat = [] if self.ui_config["sidebar_show_trackers"] else ["tracker_host"]
        filters = yield client.core.get_filter_tree(self.ui_config["sidebar_show_zero"], hide_cat)

        if self.filters == filters:
            return

        for cat, values in filters.iteritems():
            try:
                self.items_by_cat[cat].update(values)
            except KeyError:
                item = FilterCategoryItem(cat, values)
                self.items_by_cat[cat] = item
                self.addTopLevelItem(item)
                item.setExpanded(True)

        for cat, item in self.items_by_cat.iteritems():
            item.setHidden(cat not in filters)

        self.filters = filters

        if not self.selectedItems():
            self.setCurrentItem(self.topLevelItem(0).child(0));

    def contextMenuEvent(self, event):
        treeContextMenuHandler(self, event, component.get("MainWindow").popup_menu_filters)

    def selectionCommand(self, index, event):
        # persist selection when category is clicked
        if isinstance(self.itemFromIndex(index), FilterCategoryItem):
            return QtGui.QItemSelectionModel.Current | QtGui.QItemSelectionModel.NoUpdate
        return super(FilterView, self).selectionCommand(index, event)

    def on_itemSelectionChanged(self):
        if self.selectionModel().hasSelection():
            self.filter_changed.emit(self.selectedItems()[0].filter_dict())
