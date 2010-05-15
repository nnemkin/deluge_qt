
import sys
import StringIO
from lxml import etree


def fix_tab_order(filename):
	with open('fix_tab_order.xslt', 'rb') as xslt_file:
    	xslt_doc = etree.parse(xslt_file)

    with open(filename, 'rb') as f:
        xml_doc = etree.parse(f)

    xml_doc.xslt(xslt_doc)
    xml_doc.write(sys.stdout, pretty_print=True)


if __name__ == '__main__':
    fix_tab_order(sys.argv[1])
