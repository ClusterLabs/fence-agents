#!/usr/bin/python

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

def get_power_status(conn, options):
	conn.send_eol("portCfgShow " + options["--plug"])

	conn.log_expect(options, options["--command-prompt"], int(options["--shell-timeout"]))

	show_re = re.compile(r'^\s*Persistent Disable\s*(ON|OFF)\s*$', re.IGNORECASE)
	lines = conn.before.split("\n")

	for x in lines:
		res = show_re.search(x)
		if (res != None):
			# We queried if it is disabled, so we have to negate answer
			if res.group(1) == "ON":
				return "off"
			else:
				return "on"

	fail(EC_STATUS)
def set_power_status(conn, options):
	action = {
		'on' : "portCfgPersistentEnable",
		'off': "portCfgPersistentDisable"
	}[options["--action"]]

	conn.send_eol(action + " " + options["--plug"])
	conn.log_expect(options, options["--command-prompt"], int(options["--power-timeout"]))

def main():
	device_opt = [  "ipaddr", "login", "passwd", "cmd_prompt", "secure", "port", "fabric_fencing" ]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = [ "> " ]

	options = check_input(device_opt, process_input(device_opt))
	options["eol"] = "\n"

	docs = { }
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

	result = fence_action(conn, options, set_power_status, get_power_status, None)

	##
	## Logout from system
	##
	## In some special unspecified cases it is possible that
	## connection will be closed before we run close(). This is not
	## a problem because everything is checked before.
	######
	try:
		conn.send_eol("exit")
		conn.close()
	except:
		pass

	sys.exit(result)

if __name__ == "__main__":
	main()
