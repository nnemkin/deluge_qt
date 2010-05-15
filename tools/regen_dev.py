
import os
import pkg_resources


def collect_icons(filename):
    with open(filename, "wb") as f:
        f.write("<!-- WARNING! This file is auto-generated, do not edit. -->\n<RCC>\n <qresource>\n")
        for package in ("deluge_qt", "deluge"):
            data_dir = pkg_resources.resource_filename(package, "data")
            for dirpath, _, filenames in os.walk(data_dir):
                if os.path.basename(dirpath) == 'flags':
                    continue
                print "Adding %d files in %s" % (len(filenames), dirpath)
                for filename in filenames:
                    if os.path.splitext(filename)[1] not in ('.png', '.svg'):
                        continue
                    filename = os.path.join(dirpath, filename).replace("\\", "/")
                    alias = filename[len(data_dir) + 1:]
                    f.write('  <file alias="%s">%s</file>\n' % (alias, filename))
        f.write(" </qresource>\n</RCC>\n")
    print "All done"


if __name__ == '__main__':
    import sys
    collect_icons(sys.argv[1] if len(sys.argv) > 1 else '../deluge_qt/data/resources.qrc')
