#!/usr/bin/python

import sys, re, pexpect, socket
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
FENCE_RELEASE_NAME=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_power_status(conn, options):
	conn.send("show /system1\n")
	conn.log_expect(options, "EnabledState=(.*)", POWER_TIMEOUT)

	status = conn.match.group(1)

	if status.startswith("Enabled"):
		return "on"
	else:
		return "off"

def set_power_status(conn, options):
	if options["-o"] == "on":
		conn.send("start /system1\n")
	else:
		conn.send("stop -f /system1\n")
	return

def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"secure", "cmd_prompt", "ipport", "login_eol_lf",
			"separator", "inet4_only", "inet6_only" ]

	atexit.register(atexit_handler)
	
	options = check_input(device_opt, process_input(device_opt))
	if 0 == options.has_key("-c"):
		options["-c"] = "MP>"
		
	show_docs(options)
	
	conn = fence_login(options)
	conn.send("SMCLP\n")

	##
	## Fence operations
	####
	fence_action(conn, options, set_power_status, get_power_status)

	try:
		conn.send("exit\n")
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass

if __name__ == "__main__":
	main()
