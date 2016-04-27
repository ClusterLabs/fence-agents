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


#BEGIN_VERSION_GENERATION
RELEASE_VERSION = "VirtualBox fence agent"
REDHAT_COPYRIGHT = ""
BUILD_DATE = ""
#END_VERSION_GENERATION


def get_name_or_uuid(options):
    return options.get("--uuid") or options.get("--plug")

_domain_re = re.compile(r'^\"(.*)\" \{(.*)\}$')


def _invoke(conn, options, *cmd):
    prefix = options["--sudo-path"] + " " if "--use-sudo" in options else ""
    conn.sendline(prefix + "VBoxManage " + " ".join(cmd))
    conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))


def get_outlets_status(conn, options):
    result = {}

    _invoke(conn, options, "list", "vms")
    for line in conn.before.splitlines():
        # format: "<domain>" {<uuid>}
        domain = _domain_re.search(line.strip())
        if domain is not None:
            result[domain.group(1)] = ("", "off")

    _invoke(conn, options, "list", "runningvms")
    for line in conn.before.splitlines():
        # format: "<domain>" {<uuid>}
        domain = _domain_re.search(line.strip())
        if domain is not None:
            result[domain.group(1)] = ("", "on")

    return result


def get_power_status(conn, options):
    name = get_name_or_uuid(options)
    _invoke(conn, options, "list", "runningvms")
    for line in conn.before.splitlines():
        domain = _domain_re.search(line.strip())
        if domain is not None and name in domain.groups():
            return "on"
    if "--missing-as-off" in options:
        return "off"
    _invoke(conn, options, "list", "vms")
    for line in conn.before.splitlines():
        domain = _domain_re.search(line.strip())
        if domain is not None and name in domain.groups():
            return "off"
    fail_usage("Failed: You have to enter existing name/UUID of virtual machine!")


def set_power_status(conn, options):
    name = get_name_or_uuid(options)
    if options["--action"] == "on":
        _invoke(conn, options, "startvm", '"%s"' % name, "--type", "headless")
    else:
        _invoke(conn, options, "controlvm", '"%s"' % name, "poweroff")


def main():
    device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", "port", "sudo", "missing_as_off"]

    atexit.register(atexit_handler)

    all_opt["secure"]["default"] = "1"

    all_opt["cmd_prompt"]["default"] = [r"\[EXPECT\]#\ "]
    all_opt["ssh_options"]["default"] = "-t '/bin/bash -c \"" + r"PS1=\\[EXPECT\\]#\  " + "/bin/bash --noprofile --norc\"'"

    options = check_input(device_opt, process_input(device_opt))

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
    fence_logout(conn, "quit")
    sys.exit(result)

if __name__ == "__main__":
    main()
