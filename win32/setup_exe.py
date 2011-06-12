#
# setup_exe.py
#
# Copyright (C) 2010 Nikita Nemkin <nikita@nemkin.ru>
#
# This file is part of Deluge.
#

import sys
import os.path
import re
import glob
import fnmatch
import email
import cPickle as pickle
from collections import defaultdict
import win32api
from setuptools import setup
from py2exe.build_exe import py2exe as py2exe_cmd
import pkg_resources


def find_data_files(mapping, exclude=()):
    """Collect data files from specified packages by mask."""

    data_files = defaultdict(list)
    for package, masks in mapping.items():
        package_root = pkg_resources.resource_filename(package, "/")
        for mask in masks:
            files = glob.glob(os.path.join(package_root, mask))
            for file in files:
                if any(fnmatch.fnmatch(file, mask) for mask in exclude):
                    continue
                data_files[os.path.dirname(file.replace(package_root, "", 1).lstrip("\\/"))].append(file)
            if not files:
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
        # information collected here is interpreted by bootstrap.py
        metadata = {}
        for name in ("PKG-INFO", "entry_points.txt"):
            if dist.has_metadata(name):
                metadata[name] = dist.get_metadata(name)
        return metadata

    def create_binaries(self, py_files, extensions, dlls):
        self.candidate_eggs = self.usable_distributions()
        self.eggs = set(self.find_distribution(fn) for fn in py_files)
        self.eggs.discard(None)

        py2exe_cmd.create_binaries(self, py_files, extensions, dlls)

    def copy_extensions(self, extensions):
        py2exe_cmd.copy_extensions(self, extensions)

        # package egg metadata to be read by bootstrap script
        packages = {}
        for dist in self.eggs:
            packages[dist.egg_name() + ".egg"] = self.collect_metadata(dist)
        print "*** packaging egg metadata ***"
        print "\n".join(packages.keys())

        with open(os.path.join(self.collect_dir, "packages.pickle"), "wb") as f:
            pickle.dump(packages, f, pickle.HIGHEST_PROTOCOL)
        self.compiled_files.append("packages.pickle")

    def get_boot_script(self, boot_type):
        if boot_type == "common":
            return "scripts/bootstrap.py"
        else:
            return py2exe_cmd.get_boot_script(self, boot_type)

    def copy_w9xpopen(self, modules, dlls):
        pass  # do not copy w9xpopen.exe

    def plat_finalize(self, modules, py_files, extensions, dlls):
        py2exe_cmd.plat_finalize(self, modules, py_files, extensions, dlls)

        # Filter out system DLLs based on VersionInfo resource

        def get_version_string(filename, key):
            try:
                translations = win32api.GetFileVersionInfo(filename, "\\VarFileInfo\\Translation")
            except Exception:
                return u""
            else:
                # use the first available language
                language, codepage = translations[0]
                return win32api.GetFileVersionInfo(
                    filename, "\\StringFileInfo\\%04x%04x\\%s" % (language, codepage, key))

        for dll in dlls.copy():
            product_name = get_version_string(dll, "ProductName")
            if u"Microsoft" in product_name:
                dlls.remove(dll)


class Target(object):

    # Fetch deluge metadata
    metadata = email.message_from_string(
        pkg_resources.get_distribution("deluge").get_metadata("PKG-INFO"))

    # Properties common to all targets (executables). These will be put into VersionInfo.
    common = {"name": "Deluge",
              "version": re.sub(r"[^\d\.]", "", metadata["Version"]),  # strip non-numeric parts
              "description": "Deluge Bittorrent Client",
              "company_name": "Deluge Team",
              "copyright": u"Copyright \u00A9 2007-2011 Deluge Team",
              "product_name": "Deluge",
              "icon_resources": [(0, "files/deluge.ico")]}

    del metadata

    def __init__(self, script):
        self.script = script
        self.__dict__.update(self.common)


try:
    import PyQt4._qt
    consolidated_qt = ["PyQt4._qt"]
except Exception:
    print "WARNING: consolidated PyQt build is not found"
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
                                             "ui/web/themes/*/*/*/*"]},
                                 exclude=["*-debug.css", "*-debug.js"]),
      windows=[Target("scripts/deluge.py"),
               Target("scripts/deluged.py"),
               Target("scripts/deluge-web.py")],
      console=[Target("scripts/deluge-console.py")],
      zipfile="lib/library.zip",
      options={"py2exe": {"compressed": False,
                          "optimize": 2,
                          "includes": ["PyQt4.QtCore", "PyQt4.QtGui",
                                       "sip", "twisted.web.resource"] + consolidated_qt,
                          "excludes": ["deluge.ui.gtkui", "gtk",
                                       "pyreadline", "_ssl", "compiler", "doctest",
                                       "win32ui",
                                       "win32security", "win32event", "win32evtlog", "win32wnet",  # XXX
                                       "_win32sysloader",  # not used in frozen exes
                                       "pyexpat", "psyco",
                                       "PySide.QtCore", "PySide.QtGui",
                                       "twisted.spread", "twisted.python._initgroups",
                                       "simplejson"]}})
