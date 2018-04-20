#!@PYTHON@ -tt

# The Following Agent Has Been Tested On:
#
# VirtualBox 5.0.4 x64 on openSUSE 13.2
#

import sys
import re
import time
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")

from fencing import *
from fencing import fail_usage

def _invoke(conn, options, *cmd):
    prefix = options["--sudo-path"] + " " if "--use-sudo" in options else ""
    conn.send_eol(prefix + options["--vboxmanage-path"] + " " + " ".join(cmd))
    conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

def get_outlets_status(conn, options):
    _domain_re = re.compile(r'^\"(.*)\" \{(.*)\}$')
    result = {}

    _invoke(conn, options, "list", "vms")
    for line in conn.before.splitlines():
        # format: "<domain>" {<uuid>}
        domain = _domain_re.search(line.strip())
        if domain is not None:
            result[domain.group(1)] = (domain.group(2), "off")

    _invoke(conn, options, "list", "runningvms")
    for line in conn.before.splitlines():
        # format: "<domain>" {<uuid>}
        domain = _domain_re.search(line.strip())
        if domain is not None:
            result[domain.group(1)] = (domain.group(2), "on")

    return result


def get_power_status(conn, options):
    outlets = get_outlets_status(conn, options)

    if options["--plug"] in outlets:
        return outlets[options["--plug"]][1]

    right_uuid_line = [outlets[o] for o in outlets.keys() if outlets[o][0] == options["--plug"]]

    if len(right_uuid_line):
        return right_uuid_line[0][1]

    if "--missing-as-off" in options:
        return "off"

    fail_usage("Failed: You have to enter existing name/UUID of virtual machine!")


def set_power_status(conn, options):
    if options["--action"] == "on":
        _invoke(conn, options, "startvm", '"%s"' % options["--plug"], "--type", "headless")
    else:
        _invoke(conn, options, "controlvm", '"%s"' % options["--plug"], "poweroff")

def define_new_opts():
    all_opt["vboxmanage_path"] = {
        "getopt" : ":",
        "longopt" : "vboxmanage-path",
        "help" : "--vboxmanage-path=[path]  Path to VBoxManage on the host",
        "required" : "0",
        "shortdesc" : "Path to VBoxManage on the host",
        "default" : "VBoxManage",
        "order" : 200
    }
    all_opt["host_os"] = {
        "getopt" : ":",
        "longopt" : "host-os",
        "help" : "--host-os=[os]  Operating system of the host",
        "required" : "0",
        "shortdesc" : "Operating system of the host",
        "choices" : ["linux", "macos", "windows"],
        "default" : "linux",
        "order" : 200
    }

def main():
    device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", "port", "sudo",
        "missing_as_off", "vboxmanage_path", "host_os"]
    define_new_opts()

    atexit.register(atexit_handler)

    all_opt["secure"]["default"] = "1"

    all_opt["cmd_prompt"]["default"] = [r"\[EXPECT\]#\ "]
    all_opt["ssh_options"]["default"] = "-t '/bin/bash -c \"" + r"PS1=\\[EXPECT\\]#\  " + "/bin/bash --noprofile --norc\"'"

    opt = process_input(device_opt)

    opt["logout_string"] = "quit"
    if "--host-os" in opt and "--vboxmanage-path" not in opt:
        if opt["--host-os"] == "linux":
            opt["--vboxmanage-path"] = "VBoxManage"
        elif opt["--host-os"] == "macos":
            opt["--vboxmanage-path"] = "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
            opt["logout_string"] = "exit"
        elif opt["--host-os"] == "windows":
            opt["--vboxmanage-path"] = "\"/Program Files/Oracle/VirtualBox/VBoxManage.exe"
            opt["--command-prompt"] = ""
            opt["--ssh-options"] = ""

    options = check_input(device_opt, opt)
    options["eol"] = "\n"

    docs = {}
    docs["shortdesc"] = "Fence agent for VirtualBox"
    docs["longdesc"] = "fence_vbox is an I/O Fencing agent \
which can be used with the virtual machines managed by VirtualBox. \
It logs via ssh to a dom0 where it runs VBoxManage to do all of \
the work. \
\n.P\n\
By default, vbox needs to log in as a user that is a member of the \
vboxusers group. Also, you must allow ssh login in your sshd_config."
    docs["vendorurl"] = "https://www.virtualbox.org/"
    show_docs(options, docs)

    # Operate the fencing device
    conn = fence_login(options)
    result = fence_action(conn, options, set_power_status, get_power_status, get_outlets_status)
    fence_logout(conn, opt["logout_string"])
    sys.exit(result)

if __name__ == "__main__":
    main()
