#!/usr/bin/python -tt

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_STATUS

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Brocade Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 20013"
#END_VERSION_GENERATION

def set_power_status(conn, options):
	action = {
		'on' : "portCfgPersistentEnable",
		'off': "portCfgPersistentDisable"
	}[options["--action"]]

	conn.send_eol(action + " " + options["--plug"])
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

def get_power_status(conn, options):
	line_re = re.compile(r'=========', re.IGNORECASE)
	outlets = {}
	in_index = False

	conn.send_eol("switchshow")
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))
	for line in str(conn.before).split("\n"):
		if line_re.search(line):
			in_index = True
		elif in_index and line.lstrip()[0].isdigit():
			tokens = line.lstrip().split()
			status = "off" if len(tokens) > 7 and tokens[7] == "Disabled" else "on"
			outlets[tokens[0]] = ("", status)

	if ["list", "monitor"].count(options["--action"]) == 0:
		(_, status) = outlets[options["--plug"]]
		return status
	else:
		return outlets

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", \
		"port", "fabric_fencing", "telnet"]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = ["> "]

	options = check_input(device_opt, process_input(device_opt))
	options["eol"] = "\n"

	docs = {}
	docs["shortdesc"] = "Fence agent for HP Brocade over telnet/ssh"
	docs["longdesc"] = "fence_brocade is an I/O Fencing agent which can be used with Brocade FC switches. \
It logs into a Brocade switch via telnet and disables a specified port. Disabling the port which a machine is \
connected to effectively fences that machine. Lengthy telnet connections to the switch should be avoided  while \
a GFS cluster is running because the connection will block any necessary fencing actions. \
\
After  a fence operation has taken place the fenced machine can no longer connect to the Brocade FC switch.  \
When the fenced machine is ready to be brought back into the GFS cluster (after reboot) the port on the Brocade \
FC switch needs to be enabled. This can be done by running fence_brocade and specifying the enable action"
	docs["vendorurl"] = "http://www.brocade.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	####
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_power_status)
	fence_logout(conn, "exit")
	sys.exit(result)

if __name__ == "__main__":
	main()
