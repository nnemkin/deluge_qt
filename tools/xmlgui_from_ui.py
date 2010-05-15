#!/usr/bin/env python

"""Build KDE XMLGUI definition from main window's ui file."""

from lxml import etree as ET


def xmlgui_from_ui(filename):
    ui = ET.ElementTree(file=filename)

    def process_container(parent, src):
        if src.get("class") == "QMenu":
            tag = "Menu"
            text = src.findtext("property[@name='title']/string")
        else:
            tag = "ToolBar"
            text = src.findtext("property[@name='windowTitle']/string")

        container = ET.SubElement(parent, tag, {"name": src.get("name")})
        ET.SubElement(container, "Text").text = text

        for action in src.findall("addaction"):
            if action.get("name") == "separator":
                ET.SubElement(container, "Separator")
            else:
                ET.SubElement(container, "Action", {"name": action.get("name")})

    gui = ET.Element("gui",
                     {"name": "deluge", "version": "1", "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation":
                      "http://www.kde.org/standards/kxmlgui/1.0 http://www.kde.org/standards/kxmlgui/1.0/kxmlgui.xsd"},
                     {None: "http://www.kde.org/standards/kxmlgui/1.0", "xsi": "http://www.w3.org/2001/XMLSchema-instance"})

    menubar = ET.SubElement(gui, "MenuBar")
    for menu in ui.findall("//widget[@class='QMenu']"):
        if menu.get("name").startswith("popup_"):
            process_container(gui, menu)
        else:
            process_container(menubar, menu)

    for toolbar in ui.findall("//widget[@class='QToolBar']"):
        process_container(gui, toolbar)

    ET.ElementTree(gui).write(sys.stdout, pretty_print=True)


if __name__ == '__main__':
    import sys

    xmlgui_from_ui(sys.argv[1])
