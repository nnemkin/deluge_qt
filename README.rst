
Deluge Qt
~~~~~~~~~

This package provides Qt4-based front-end for Deluge_ BitTorrent client.

It's not officially part of Deluge (despite what file header comments say).

.. _Deluge: http://deluge-torrent.org/


Information for developers
~~~~~~~~~~~~~~~~~~~~~~~~~~

UI Design Workflow
------------------

Most of the UI is built with Qt Designer (``.ui`` files in ``qtui/ui``).
Python code is generated (using PyQt's pyuic) from ``.ui`` files and put into a single file
``qtui/generated/ui.py``.
The generated code doesn't work "as is" and needs postprocessing, which is done by
the ``pyuic_postprocess.py`` script.

Qt resources file (``qtui/data/resources.qrc``) exists only for design time work.
It's generated automatically by the ``tools/regen_dev.py`` script and contains references
to all image files in the ``data/`` folder of packages ``deluge`` and ``qtui``.

Basically, ``regen_dev.py`` needs to be run to make new images available in Qt Designer
and ``regen_ui.py`` rebuilds UI definition code from ``.ui`` files.


Other things to know
--------------------

The code requires at least Qt 4.5 and PyQt 4.6 (for new style signal connections, v2 API,
QObject properties in constructor kwargs and other features). Some work is still required
to make sure that reasonably old distros are supported.

Only QtCore and QtGui modules are used. Networking, XML and other services are provided by python
libraries.

How to integrate with KDE is not decided yet. Options include: conditional declarations,
polymorphic classes and postprocessing.


Code Style Bits
---------------

* PEP-8 is in effect with two exceptions. First, recommended maximum line width is 120 characters.
  Second, methods/variables that are tightly coupled with Qt or defined by Qt follow Qt naming
  practices.
* Be consistent with existing deluge code, in particular: use double quotes for strings literals.
* Imports are split into groups: stdlib modules, infrastructure modules (PyQt, twisted),
  deluge core modules, deluge_qt modules. Groups are separeted with an empty line.
* Recommended class member order is:

   1. Qt signal declarations.
   2. Inner classes, classmethods and staticmethods.
   3. Class variable declarations and class block code.
   4. Constructor, python methods.
   5. deluge Component methods (start, stop, shutdown, update).
   6. Qt class member overrides.
   7. Slots (signal handlers).

* Do not use ``super()``.
* Use ``@defer.inlineCallbacks``.
* Use new-style PyQt signal connections.
* Use ``@QtCore.pyqtSlot`` with pythonic signatures to declare signal handlers.


Packaging and building on Windows
---------------------------------

Building libtorrent
===================

You must run all commands from the same console window. To set up MSVC build environment
launch the _"Visual Studio 2008 Command Prompt"_ shortcut or use ``vcvars32.bat``.

1) Build boost with::

    > set BOOST_HOME=%cd%
    > bootstrap
    > bjam toolset=msvc-9.0 variant=release link=static stage

.. Note::
    ``boost-python`` will link with the Python version found in PATH. To link with another version,
    edit ``tools/build/v2/user-config.jam`` (look for ``using python`` string).

2) Build zlib with::

    > set ZLIB_HOME=%cd%
    > ml /coff /Zi /c contrib\masmx86\inffas32.asm contrib\masmx86\match686.asm
    > nmake -f win32/Makefile.msc LOC="-DASMV -DASMINF" OBJA="match686.obj inffas32.obj"

3) Build OpenSSL with::

    > set OPENSSL_HOME=%cd%\build
    > perl Configure VC-WIN32 --prefix=.\build
    > ms\do_nasm
    > nmake -f ms\ntdll.mak install

4) Set up build environment::

    > set INCLUDE=%INCLUDE%;%ZLIB_HOME%;%OPENSSL_HOME%\include;%BOOST_HOME%;%PYTHONHOME%\include
    > set LIB=%LIB%;%ZLIB_HOME%;%OPENSSL_HOME%\lib;%BOOST_HOME%\stage\lib;%PYTHONHOME%\libs

5) At this point Deluge should be able to build libtorrent for itself when you issue
   ``setup.py build_ext``.


Building PyQt on Windows
========================

To reduce binary size and improve startup time I recommend to link PyQt statically to Qt.
Configuration file for minimal static Qt 4.7 build can be found in ``win32/configure_pyqt.cache``

Build procedure outline:

2) Create a directory for the Qt out-of-source build. Copy ``win32/configure_pyqt.cache`` there,
   then configure and build Qt::

    > set QT_HOME=%cd%
    > set PATH=%QTHOME%\bin;%PATH%
    > configure -loadconfig pyqt
    > nmake

4) Create virtualenv for the custom PyQt binaries, set build envitonment::

     > set INCLUDE=%INCLUDE%;%PYTHONHOME%\include;%QT_HOME%\include
     > set LIB=%LIB%;%PYTHONHOME%\libs;%QT_HOME%\lib

5) Configure and build sip::

     > python configure.py
     > nmake install

6) Configure and built PyQt::

     > python configure.py -c -g -eQtCore -eQtGui -eQtSvg -tqgif -tqjpeg -tqico -tqsvg ^
         --no-docstrings --no-designer-plugin --no-sip-files --confirm-license
     > set CL=/bigobj
     > nmake install

7) Set ``PYTHONPATH`` to virtualenv's ``site-packages`` to make custom binaries available to py2exe.


Packaging Deluge with py2exe
============================

Of all python packagers for windows (py2exe, cx_Freeze, bbfreeze), py2exe produces the neatest
package. Some notes:

* To keep the main setup.py clean, specialized ``win32/setup_exe.py`` is used as a py2exe launcher.
* py2exe won't find ``zope.interface`` if it is installed with pip. You must use
  ``easy_install --always-unzip`` to install ``zope.interface``.
* py2exe cannot be run from a virtualenv, because it will package virtualenv's ``distutils``
  replacement package instead of the the real one.
* py2exe is enhanced with eggs/pkg_resources support (see ``scripts/bootstrap.py`` for details).
  All python code is still packaged into a single ``library.zip``. Egg resources
  are installed in unpackaged form along the executable. (They're listed manually in
  ``setup_exe.py`` using the ``data_files`` option.)


TODO
----

* ``EditTrackersDialog`` is incomplete
* Fix ``FileModel`` bugs, add drag-n-drop
* ditch PIL, QtGui has all we need
* Catch up with gtkui updates for the past year
* Integrate KDE app framework, widgets, globals settings (language, proxy) etc
* Create a Mac OS bungle (py2app?)
* QtUI for plugins
