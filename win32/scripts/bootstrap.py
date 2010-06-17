
import sys

def _bootstrap_common():
    # prevent linecache (used in tracebacks) from accessing nonexistent files

    import linecache
    linecache.getline = lambda filename, lineno, module_globals = None: ""


def _bootstrap_io():

    import atexit

    # log stderr to appname.exe.log

    class StdErr(object):

        def __init__(self):
            self._file = None
            self._error = None

        def write(self, text, alert=sys._MessageBox, fname=sys.executable + '.log'):
            if self._file is None and self._error is None:
                try:
                    self._file = open(fname, 'wb')
                except Exception, e:
                    self._error = e
                    atexit.register(alert, 0, "The logfile '%s' could not be opened:\n %s" % (fname, e), "Errors occurred")
                else:
                    atexit.register(alert, 0, "See the logfile '%s' for details" % fname, "Errors occurred")

            if self._file is not None:
                self._file.write(text)
                self._file.flush()

        def flush(self):
            if self._file is not None:
                self._file.flush()

    sys.stderr = StdErr()

    # ignore stdout

    class Blackhole(object):

        def write(self, text): pass
        def flush(self): pass

    sys.stdout = Blackhole()


def _bootstrap_eggs():

    import pkg_resources
    import cPickle as pickle
    import zipimport
    import os.path

    # make pkg_resources happy

    class InstalledProvider(pkg_resources.DefaultProvider):

        def __init__(self, name):
            self.module_path = os.path.dirname(sys.executable)


    class StringMetadata(InstalledProvider):

        def __init__(self, metadata):
            self.metadata = metadata

        def has_metadata(self, name):
            return name == "PKG-INFO"

        def get_metadata(self, name):
            if name == "PKG-INFO":
                return self.metadata
            raise KeyError

#        def has_metadata(self, name):
#            return name.lstrip("/") in self.metadata
#
#        def metadata_isdir(self, name):
#            return self.metadata[name.lstrip("/")]["is_dir"]
#
#        def metadata_listdir(self, name):
#            return self.metadata[name.lstrip("/")]["listing"]
#
#        def get_metadata(self, name):
#            return self.metadata[name.lstrip("/")]["contents"]

        def get_metadata_lines(self, name):
            return pkg_resources.yield_lines(self.get_metadata(name))


    def installed_finder(importer, path_item, only=False):
        try:
            packages = pickle.loads(importer.get_data("packages.pickle"))
        except IOError:
            pkg_resources.find_in_zip(path_item, only) # XXX: private function
        else:
            for egg_name, metadata in packages.iteritems():
                yield pkg_resources.Distribution.from_location(path_item, egg_name, metadata=StringMetadata(metadata))


    pkg_resources.register_finder(zipimport.zipimporter, installed_finder)
    pkg_resources.register_loader_type(zipimport.zipimporter, InstalledProvider)


_bootstrap_common()
if sys.frozen == "windows_exe":
    _bootstrap_io()
_bootstrap_eggs()
