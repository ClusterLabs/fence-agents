#!@PYTHON@ -tt

# The Following Agent Has Been Tested On:
#
# Virsh 0.3.3 on RHEL 5.2 with xen-3.0.3-51
#

import sys, re
import time
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage

def get_name_or_uuid(options):
	return options["--uuid"] if "--uuid" in options else options["--plug"]

def get_outlets_status(conn, options):
	if "--use-sudo" in options:
		prefix = options["--sudo-path"] + " "
	else:
		prefix = ""

	conn.sendline(prefix + "virsh list --all")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	result = {}

        #This is status of mini finite automata. 0 = we didn't found Id and Name, 1 = we did
	fa_status = 0

	for line in conn.before.splitlines():
		domain = re.search(r"^\s*(\S+)\s+(\S+)\s+(\S+).*$", line)

		if domain != None:
			if fa_status == 0 and domain.group(1).lower() == "id" and domain.group(2).lower() == "name":
				fa_status = 1
			elif fa_status == 1:
				result[domain.group(2)] = ("",
						(domain.group(3).lower() in ["running", "blocked", "idle", "no state", "paused"] and "on" or "off"))
	return result

def get_power_status(conn, options):
	prefix = options["--sudo-path"] + " " if "--use-sudo" in options else ""
	conn.sendline(prefix + "virsh domstate %s" % (get_name_or_uuid(options)))
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	for line in conn.before.splitlines():
		if line.strip() in ["running", "blocked", "idle", "no state", "paused"]:
			return "on"
		if "error: failed to get domain" in line.strip() and "--missing-as-off" in options:
			return "off"
		if "error:" in line.strip():
			fail_usage("Failed: You have to enter existing name/UUID of virtual machine!")

	return "off"

def set_power_status(conn, options):
	prefix = options["--sudo-path"] + " " if "--use-sudo" in options else ""
	conn.sendline(prefix + "virsh %s " %
			(options["--action"] == "on" and "start" or "destroy") + get_name_or_uuid(options))

	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))
	time.sleep(int(options["--power-wait"]))

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", "port", "sudo", "missing_as_off"]

	atexit.register(atexit_handler)

	all_opt["secure"]["default"] = "1"
	all_opt["cmd_prompt"]["default"] = [r"\[EXPECT\]#\ "]
	all_opt["ssh_options"]["default"] = "-t '/bin/bash -c \"" + r"PS1=\\[EXPECT\\]#\  " + "/bin/bash --noprofile --norc\"'"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for virsh"
	docs["longdesc"] = "fence_virsh is an I/O Fencing agent \
which can be used with the virtual machines managed by libvirt. \
It logs via ssh to a dom0 and there run virsh command, which does \
all work. \
\n.P\n\
By default, virsh needs root account to do properly work. So you \
must allow ssh login in your sshd_config."
	docs["vendorurl"] = "http://libvirt.org"
	show_docs(options, docs)

	## Operate the fencing device
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_outlets_status)
	fence_logout(conn, "quit")
	sys.exit(result)

if __name__ == "__main__":
	main()
