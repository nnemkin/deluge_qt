
import sys


def _bootstrap_common():
    # prevent linecache (used in tracebacks) from accessing nonexistent source files

    import linecache

    def getline(filename, lineno, module_globals = None):
        return ""

    linecache.getline = getline


def _bootstrap_io():
    # Ignore output to stdout and stderr, log unhandled exceptions.

    import io
    import logging

    class NullWriter(io.TextIOBase):

        def write(self, text):
            pass

    def excepthook(*exc_info):
        logging.error(exc_info[1], exc_info=exc_info)

    sys.excepthook = excepthook
    sys.stdout = sys.stderr = NullWriter()


def _bootstrap_eggs():
    # Install customized resource provider and distribution finder so that pkg_resources
    # can work with py2exe packaged application.

    import pkg_resources
    import cPickle as pickle
    import zipimport
    import os.path

    class InstalledProvider(pkg_resources.DefaultProvider):
        # Make resource paths for all packages to be relative to executable

        def __init__(self, module):
            self.module_path = os.path.dirname(sys.executable)


    class StringMetadata(pkg_resources.EmptyProvider):

        def __init__(self, metadata):
            self._metadata = metadata

        def has_metadata(self, name):
            return name in self._metadata

        def get_metadata(self, name):
            return self._metadata[name]


    def installed_finder(importer, path_item, only=False):
        # with py2exe we will ever have one path_item (library.zip) that contains all distributions
        try:
            packages = pickle.loads(importer.get_data("packages.pickle"))
        except IOError:
            pass  # file not found
        else:
            for egg_name, metadata in packages.iteritems():
                yield pkg_resources.Distribution.from_location(
                    path_item, egg_name, metadata=StringMetadata(metadata))


    pkg_resources.register_finder(zipimport.zipimporter, installed_finder)
    pkg_resources.register_loader_type(zipimport.zipimporter, InstalledProvider)


_bootstrap_common()
if sys.frozen == "windows_exe":  # Win32 GUI application
    _bootstrap_io()
_bootstrap_eggs()
