
import sys
import os
import pkg_resources


def collect_icons(filename):
    # Collect icons and create resource file for use in QtDesigner.

    with open(filename, "wb") as f:
        f.write("<!-- WARNING! This file is auto-generated, do not edit. -->\n<RCC>\n <qresource>\n")

        data_dirs = [
            pkg_resources.resource_filename("deluge", "ui/data"),
            pkg_resources.resource_filename("deluge_qt", "data")]

        for data_dir in data_dirs:
            for dirpath, _, filenames in os.walk(data_dir):
                if os.path.basename(dirpath) == "flags":
                    continue

                print "Adding %d file(s) from %s" % (len(filenames), dirpath)
                for filename in filenames:
                    if os.path.splitext(filename)[1] in ('.png', '.svg'):
                        filename = os.path.join(dirpath, filename).replace("\\", "/")
                        alias = filename[len(data_dir) + 1:]
                        f.write('  <file alias="%s">%s</file>\n' % (alias, filename))
        f.write(" </qresource>\n</RCC>\n")
    print "All done"


if __name__ == "__main__":
    collect_icons(sys.argv[1] if len(sys.argv) > 1 else "../deluge_qt/data/resources.qrc")
