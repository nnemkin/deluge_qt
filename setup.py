#
# setup.py
#
# Copyright (C) 2010 Nikita Nemkin <nikita@nemkin.ru>
#
# This file is part of Deluge.
#

from setuptools import setup, find_packages

setup(name="deluge-qt",
      version="1.3.0",
      description="Qt4 user interface for Deluge Bittorrent Client.",
      author="Nikita Nemkin",
      author_email="nikita@nemkin.ru",
      license="GPLv3",
      url="http://nemkin.ru/projects/deluge-qt/",
      packages=find_packages(),
      package_data={"deluge_qt": ["data/pixmaps/*.*",
                                  "data/icons/deluge/index.theme",
                                  "data/icons/deluge/*/*/*"]},
      install_requires=["deluge", "twisted"],
      zip_safe=True,
      entry_points={"gui_scripts": ["deluge-qt = deluge_qt.qtui:start"],
                    "deluge.ui": ["qt = deluge_qt.qtui.QtUI"]})
