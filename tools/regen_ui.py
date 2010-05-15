#!/usr/bin/env python

"""Build user interface from ui files."""

import os.path
import subprocess
import postprocess


def regenerate(src_dir):
    ui_dir = os.path.join(src_dir, "deluge_qt", "ui")
    generated_dir = os.path.join(src_dir, "deluge_qt", "generated")

    for dir in (ui_dir, generated_dir):
        if not os.path.exists(ui_dir) or not os.path.exists(generated_dir):
            raise Exception("invalid src_dir: directory %s does not exist." % dir)

    print "Delete previous generated filed"
    for name in os.listdir(generated_dir):
        os.unlink(os.path.join(generated_dir, name))

    print "Make generated folder a package"
    open(os.path.join(generated_dir, "__init__.py"), "wb").close()

    print "Generate python code with pyuic4"
    py_ui_file = os.path.join(generated_dir, "ui.py")

    with open(py_ui_file, "wb") as f:
        for name in os.listdir(ui_dir):
            print "   ", name
            subprocess.check_call(["pyuic4", os.path.join(ui_dir, name)], shell=True, stdout=f)

    print "Postprocess ui.py"
    postprocess.postprocess_file(py_ui_file)

#    qrc_file = os.path.join(src_dir, "deluge_qt", "data", "resources.qrc")
#    rcc_file = os.path.join(generated_dir, "resources.rcc")
#    print "Pack resources to binary resources.rcc"
#    subprocess.check_call(["rcc", "-binary", "-o", rcc_file, qrc_file])

    print "Create stub resource module"
    open(os.path.join(generated_dir, "resources_rc.py"), "wb").close()

    print "All done (ui.py %.2f KB)" % (os.path.getsize(py_ui_file) / 1024.,)

if __name__ == "__main__":
    import sys
    regenerate(sys.argv[1] if len(sys.argv) > 1 else "..")
