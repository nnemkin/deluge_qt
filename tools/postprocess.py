#!/usr/bin/env python

"""Postprocess pyuic generated code."""

import sys, re, tempfile, os
if os.name == 'nt':
    import win32api, win32con


def postprocess_text(text):

    text = text.replace('\r', '')

    # (Required) Replace Qt translation calls with gettext.
    text = re.sub(r'(?s)QtGui\.QApplication\.translate\("[^"]+", "(.*?)", None, QtGui\.QApplication\.UnicodeUTF8\)', r'_("\1")', text)

    # (Required) pyuic4 fails when non-translatable text property contains unicode text. We make three such field "non-translatable" here.
    text = re.sub(r'(?s)(self.text_(authors|translators|artists).setPlainText)\(_\((".+?")\)\)\n', r'\1(u\3)\n', text)

    # (Optional) Remove unnecessary "setObjectName"s.
    text = re.sub(r'(?i)\n *(\w+\.)+setObjectName\("([a-z\d]+_\d+|(horizontal|vertical|form|grid)Layout)"\)', '', text)

    # (Optional) Do not create member variables for layouts
    text = re.sub(r'self\.((horizontal|vertical|form|grid)Layout(_\d+)?)', r'\1', text)

    # (Required) Delay import TorrentDetails and TorrentOptions to avoid circular references.
    text = re.sub(r'\n *from deluge_qt\.torrent_(options|details) import Torrent(Options|Details)', '', text)
    text = re.sub(r'((\n *)MainWindow\.setObjectName)', r'\2from deluge_qt.torrent_details import TorrentDetails\1', text)
    text = re.sub(r'((\n *)TorrentDetails\.setObjectName)', r'\2from deluge_qt.torrent_options import TorrentOptions\1', text)

    # (Required) Prevent overwriting header labels set in constructor.
    text = re.sub(r'\n *self\.\w+\.headerItem\(\)\.setText\(0, "1"\)', '', text)

    # (Required) Disconnect popup-only menus from menu bar.
    text = re.sub(r'\n *self\.menu_?bar\.addAction\(self\.popup_menu_\w+\.menuAction\(\)\)', '', text)

    # (Optional) Fix QFont.setWeight/setBold double
    text = re.sub(r'font\.setWeight\(75\)\s+(?=font\.setBold\(True\))', r'', text)

    # (Optional) Do not create bold QFont object multiple times
    text = re.sub(r'font = QtGui\.QFont\(\)\s+font\.setBold\(True\)\s+([\w\.]+)\.setFont\(font\)', r'\1.setFont(bold_font)', text)
    text = re.sub(r'(def setupUi\(self, \w+\):(\s+))(?=([^\n]+\2)+?[^\n]+setFont\(bold_font\))', r'\1bold_font = QtGui.QFont()\2bold_font.setBold(True)\2', text)

    # (Required) Icon themes / resource loading support.
    text = re.sub(r'(\n\s+(\w+) = )QtGui\.QIcon\(\)\s+\2\.addPixmap\(QtGui\.QPixmap\(":/icons/deluge/\w+/\w+/([\w-]+).png"\).*?\)', r'\1IconLoader.themeIcon("\3")', text)
    text = re.sub(r'(\n\s+(\w+) = )QtGui\.QIcon\(\)\s+\2\.addPixmap\(QtGui\.QPixmap\(":/pixmaps/(.+?)"\).*?\)', r'\1IconLoader.customIcon("\3")', text)
    text = re.sub(r'QtGui\.QPixmap\(":/pixmaps/(.+?)"\)', r'IconLoader.packagePixmap("/data/pixmaps/\1")', text)
    text += '\nfrom deluge_qt.ui_tools import IconLoader\n'

    # (Required) Qt Designer forbids the name "private"
    text = re.sub(r'private_', r'private', text)

    return text


def postprocess_file(filename):

    with open(filename, 'r+b') as f:
        text = f.read()

    text = postprocess_text(text)

    with tempfile.NamedTemporaryFile('wb', dir=os.path.dirname(filename), delete=False) as f:
        f.write(text)
    if os.name == 'nt':
        win32api.MoveFileEx(f.name, filename, win32con.MOVEFILE_REPLACE_EXISTING)
    else:
        os.rename(f.name, filename)


if __name__ == '__main__':
    postprocess_file(sys.argv[1])
