#
# setup_exe.py
#
# Copyright (C) 2010 Nikita Nemkin <nikita@nemkin.ru>
#
# This file is part of Deluge.
#

import sys
import os.path
import glob
from collections import defaultdict
from setuptools import setup
from py2exe.build_exe import py2exe as py2exe_cmd
import pkg_resources


def find_data_files(mapping):
    data_files = defaultdict(list)
    for package, masks in mapping.items():
        package_root = pkg_resources.resource_filename(package, "/")
        for mask in masks:
            files = glob.glob(os.path.join(package_root, mask))
            if files:
                for file in files:
                    data_files[os.path.dirname(file.replace(package_root, '', 1).lstrip("\\/"))].append(file)
            else:
                print "WARNING: no files found for %s in package %s" % (mask, package)
    return data_files.items()


class py2exe_deluge(py2exe_cmd):

    def usable_distributions(self):
        location_uniqness = defaultdict(int)
        for dist in pkg_resources.working_set:
            location_uniqness[dist.location] += 1
        return [dist for dist in pkg_resources.working_set
                if location_uniqness[dist.location] == 1 and dist.has_metadata("top_level.txt")]

    def find_distribution(self, m):
        filename = m.__file__.lower()
        if filename:
            for dist in self.candidate_eggs:
                if filename.startswith(dist.location.lower()):
                    return dist

    def collect_metadata(self, dist):
        return dist.get_metadata("PKG-INFO")

#    def collect_metadata(self, dist):
#        metadata = {}
#
#        def _collect(path):
#            if dist.metadata_isdir(path):
#                names = dist.metadata_listdir(path)
#                metadata[path] = {"is_dir": True, "names": names}
#                for name in names:
#                    _collect("%s/%s" % (path, name) if path else name)
#            else:
#                metadata[path] = {"is_dir": False, "contents": dist.get_metadata(path)}
#
#        _collect("")
#        return metadata

    def create_binaries(self, py_files, extensions, dlls):
        self.candidate_eggs = self.usable_distributions()
        self.eggs = set(self.find_distribution(fn) for fn in py_files)
        self.eggs.remove(None)

        py2exe_cmd.create_binaries(self, py_files, extensions, dlls)

    def copy_extensions(self, extensions):
        py2exe_cmd.copy_extensions(self, extensions)

        # package egg metadata to be read by bootstrap script
        packages = {}
        for dist in self.eggs:
            packages[dist.egg_name() + ".egg"] = self.collect_metadata(dist)
        print "*** packaging egg metadata ***"
        print "\n".join(packages.keys())

        import cPickle as pickle
        with open(os.path.join(self.collect_dir, "packages.pickle"), "wb") as f:
            pickle.dump(packages, f)
        self.compiled_files.append("packages.pickle")

    def get_boot_script(self, boot_type):
        if boot_type == "common":
            return "scripts/bootstrap.py"
        else:
            return py2exe_cmd.get_boot_script(self, boot_type)

    def copy_w9xpopen(self, modules, dlls):
        pass # do not copy w9xpopen.exe


class Target(object):

    common = {"name": "Deluge",
              "version": "1.3.0",
              "description": "Deluge Bittorrent Client",
              "company_name": "Deluge Team",
              "copyright": u"Copyright \u00A9 2007-2010 Deluge Team",
              "product_name": "Deluge",
              "icon_resources": [(0, "files/deluge.ico")]}

    def __init__(self, script):
        self.script = script
        self.__dict__.update(self.common)


try:
    import PyQt4._qt
    consolidated_qt = ["PyQt4._qt"]
except:
    consolidated_qt = []

sys.argv.append("py2exe")


setup(cmdclass={"py2exe": py2exe_deluge},
      data_files=find_data_files({"deluge_qt": ["data/pixmaps/*",
                                                "data/icons/deluge/index.theme",
                                                "data/icons/deluge/*/*/*"],
                                  "deluge": ["data/pixmaps/*.png",
                                             "data/pixmaps/flags/*.png",
                                             "data/GeoIP.dat",
                                             "plugins/*.egg",
                                             "i18n/*/LC_MESSAGES/*.mo",
                                             "ui/web/gettext.js",
                                             "ui/web/index.html",
                                             "ui/web/css/*.css",
                                             "ui/web/icons/*.png",
                                             "ui/web/images/*.gif",
                                             "ui/web/images/*.png",
                                             "ui/web/js/*.js",
                                             "ui/web/render/*.html",
                                             "ui/web/themes/*/*/*/*"]}),
      windows=[Target("scripts/deluge.py"), Target("scripts/deluged.py"), Target("scripts/deluge-webui.py")],
      console=[Target("scripts/deluge-consoleui.py")],
      zipfile="lib/modules.zip",
      options={"py2exe": {#"compressed": True,
                          "optimize": 2,
                          "includes": ["PyQt4.QtCore", "PyQt4.QtGui", "sip", "twisted.web.resource"] + consolidated_qt,
                          "excludes": ["pyreadline", "_ssl", "compiler", "doctest",
                                       "deluge.ui.gtkui",
                                       "win32ui", "win32wnet", "win32security", "pyexpat", "psyco", "twisted.spread"],
                          "dll_excludes": ["POWRPROF.dll", "MSWSOCK.dll", "MPR.dll"]}})
