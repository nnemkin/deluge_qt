#
# plugin_manager.py
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

from twisted.internet import defer

from deluge import component
from deluge.pluginmanagerbase import PluginManagerBase
from deluge.ui.client import client


class PluginManager(PluginManagerBase, component.Component):

    def __init__(self):
        component.Component.__init__(self, "PluginManager")
        PluginManagerBase.__init__(self, "qtui.conf", "deluge.plugin.qtui")

        client.register_event_handler("PluginEnabledEvent", self.enable_plugin)
        client.register_event_handler("PluginDisabledEvent", self.disable_plugin)

    @defer.inlineCallbacks
    def start(self):
        plugins = yield client.core.get_enabled_plugins()
        for plugin in plugins:
            self.enable_plugin(plugin)

    def stop(self):
        self.disable_plugins()
