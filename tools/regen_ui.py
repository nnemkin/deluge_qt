#!/usr/bin/env python

"""Build user interface from ui files."""

import re
import os.path
import subprocess
import optparse


def postprocess(text):
    # Fix problems in the code produced by pyuic4.

    sub_args = [
        # (Required) Remove resources_rc imports. Deluge uses python's pkg_resources.
        (r'import resources_rc\n', ''),

        # (Required) Remove fromUtf8 calls. With v2 API they're no-op anyway.
        (r'(?s)try:\s+_fromUtf8.+?\n\n', ''),
        (r'(?s)_fromUtf8\((?:"((?:[^"]|\\.)*)"\s*)+\)', r'"\1"'),

        # (Required) Replace Qt translation calls with gettext (pyuic4 doesn't have a -tr option).
        (r'(?s)QtGui\.QApplication\.translate\("[^"]+", "(.*?)", None, QtGui\.QApplication\.UnicodeUTF8\)',
         r'_("\1")'),

        # (Required) pyuic4 fails when non-translatable text property contains unicode text.
        # We make three such fields "non-translatable" here.
        (r'(?s)(self.text_(authors|translators|artists).setPlainText)\(_\((".+?")\)\)\n', r'\1(u\3)\n'),
        (r'("(?:\\"|[^"])*[\x80-\xff](?:\\"|[^"])*")', r'u\1'),

        # (Optional) Remove setObjectName calls for layouts.
        (r'(?i)\n *(\w+\.)+setObjectName\("([a-z\d]+_\d+|(horizontal|vertical|form|grid)Layout)"\)', ''),

        # (Optional) Do not create member variables for layouts.
        (r'self\.((horizontal|vertical|form|grid)Layout(_\d+)?)', r'\1'),

        # (Required) Delay import TorrentDetails and TorrentOptions to avoid circular references.
        (r'\n *from deluge_qt\.torrent_(options|details) import Torrent(Options|Details)', ''),
        (r'((\n *)MainWindow\.setObjectName)', r'\2from deluge_qt.torrent_details import TorrentDetails\1'),
        (r'((\n *)TorrentDetails\.setObjectName)', r'\2from deluge_qt.torrent_options import TorrentOptions\1'),

        # (Required) Prevent overwriting header labels set in constructor.
        (r'\n *self\.\w+\.headerItem\(\)\.setText\(0, "1"\)', ''),

        # (Required) Disconnect popup-only menus from menu bar.
        (r'\n *self\.menu_?bar\.addAction\(self\.popup_menu_\w+\.menuAction\(\)\)', ''),

        # (Optional) QFont.setWeight(75) and QFont.setBold(True) are synonyms. No need to call both.
        (r'font\.setWeight\(75\)\s+(?=font\.setBold\(True\))', r''),

        # (Optional) Use single bool QFont instance for all labels.
        (r'font = QtGui\.QFont\(\)\s+font\.setBold\(True\)\s+([\w\.]+)\.setFont\(font\)', r'\1.setFont(bold_font)'),
        (r'(def setupUi\(self, \w+\):(\s+))(?=([^\n]+\2)+?[^\n]+setFont\(bold_font\))',
         r'\1bold_font = QtGui.QFont()\2bold_font.setBold(True)\2'),

        # (Required) Icon themes / resource loading support.
        # Use of icons from the resource file created by regen_dev.py is converted to IconLoader.
        (r'(\n\s+(\w+) = )QtGui\.QIcon\(\)\s+\2\.addPixmap\(QtGui\.QPixmap\(":/icons/deluge/\w+/\w+/([\w-]+).png"\).*?\)',
         r'\1IconLoader.themeIcon("\3")'),
        (r'(\n\s+(\w+) = )QtGui\.QIcon\(\)\s+\2\.addPixmap\(QtGui\.QPixmap\(":/pixmaps/(.+?)"\).*?\)',
         r'\1IconLoader.customIcon("\3")'),
        (r'QtGui\.QPixmap\(":/pixmaps/(.+?)"\)', r'IconLoader.packagePixmap("/data/pixmaps/\1")'),
        (r'(?s)\s*$', '\n\nfrom deluge_qt.ui_tools import IconLoader'),

        # (Required) Qt Designer forbids the name "private"
        (r'private_', r'private'),
    ]

    text = text.replace('\r', '')
    for pattern, repl in sub_args:
        text = re.sub(pattern, repl, text)
    return text


def regenerate(options):
    # Regenerate python code from .ui files.

    src_dir = options.src_dir
    ui_dir = os.path.join(src_dir, "deluge_qt", "ui")
    generated_dir = os.path.join(src_dir, "deluge_qt", "generated")

    for dir in (ui_dir, generated_dir):
        if not os.path.exists(ui_dir) or not os.path.exists(generated_dir):
            raise RuntimeError("invalid src_dir: directory '%s' does not exist." % dir)

    print "Delete previously generated files"
    for name in os.listdir(generated_dir):
        os.unlink(os.path.join(generated_dir, name))

    print "Make generated folder a package"
    open(os.path.join(generated_dir, "__init__.py"), "wb").close()

    print "Generate python code with pyuic4"
    pyui_data = ""
    for name in os.listdir(ui_dir):
        print "   ", name
        pyuic = subprocess.Popen(["pyuic4", os.path.join(ui_dir, name)], shell=True, stdout=subprocess.PIPE)
        pyui_data += pyuic.communicate()[0]

    if options.keep_raw:
        pyui_file = os.path.join(generated_dir, "ui_raw.py")
        with open(pyui_file, 'wb') as f:
            f.write(pyui_data)

    print "Postprocess and write ui.py"
    pyui_data = postprocess(pyui_data)
    pyui_file = os.path.join(generated_dir, "ui.py")
    with open(pyui_file, "wb") as f:
        f.write(pyui_data)

    print "All done (ui.py is %.2f KB)" % (os.path.getsize(pyui_file) / 1024.)


def main():
    parser = optparse.OptionParser()
    parser.add_option("-s", "--source-dir", dest="src_dir", metavar="DIR", default="..")
    parser.add_option("--keep-raw", dest="keep_raw", action="store_true")
    options, args = parser.parse_args()

    regenerate(options)


if __name__ == "__main__":
    main()
