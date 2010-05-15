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

from setuptools import setup, find_packages
try:
    import py2exe
except ImportError:
    print "Warning: py2exe not found."


from py2exe.build_exe import py2exe as build_exe

class deluge_py2exe(build_exe):

    def copy_extensions(self, extensions):
        build_exe.copy_extensions(self, extensions)

#        media = os.path.join('foo', 'media')
#        full = os.path.join(self.collect_dir, media)
#        if not os.path.exists(full):
#            self.mkpath(full)
#
#        for f in glob.glob('foo/media/*'):
#            name = os.path.basename(f)
#            self.copy_file(f, os.path.join(full, name))
#            self.compiled_files.append(os.path.join(media, name))


setup(name="deluge-qt",
      version="1.2.3",
      description="Qt4 user interface for Deluge Bittorrent Client.",
      author="Nikita Nemkin",
      author_email="nikita@nemkin.ru",
      url="http://nemkin.ru/projects/deluge-qt/",
      packages=find_packages(),
      include_package_data=True,
      package_data={"deluge_qt": ["data/pixmaps/*.png", "data/pixmaps/*.svg"]},
      install_requires=["deluge>=1.2.3", "PyQt>=4.5"],
      entry_points={"gui_scripts": ["deluge-qt = deluge_qt.qtui:start"], "deluge.ui": ["qt = deluge_qt.qtui.QtUI"]},
      windows=['deluge-qt.py'],
      zipfile='lib/modules.zip',
      cmdclass={"py2exe": deluge_py2exe},
      options={'py2exe': {'compressed': True,
                          'optimize': 2,
                          'excludes': ['deluge.ui.console', 'deluge.ui.gtkui', 'psyco', 'win32ui',
                                       'win32wnet', 'win32security', 'unicodedata', 'pyexpat', 'pyreadline', '_ssl', 'OpenSSL.rand'],
                          'includes': ['sip', 'PyQt4._qt', 'zope.interface'],
                          'dll_excludes': ['POWRPROF.dll', 'MSWSOCK.dll', 'MPR.dll']}})
