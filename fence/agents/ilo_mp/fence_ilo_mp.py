#!/usr/bin/python

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_power_status(conn, options):
	try:
		conn.send_eol("show /system1")
		
		re_state = re.compile('EnabledState=(.*)', re.IGNORECASE)
		conn.log_expect(options, re_state, int(options["-Y"]))

		status = conn.match.group(1).lower()

		if status.startswith("enabled"):
			return "on"
		else:
			return "off"
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

def set_power_status(conn, options):
	try:
		if options["-o"] == "on":
			conn.send_eol("start /system1")
		else:
			conn.send_eol("stop -f /system1")

		conn.log_expect(options, options["-c"], int(options["-g"]))

		return
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

def main():
	device_opt = [  "ipaddr", "login", "passwd", "passwd_script",
			"secure", "identity_file", "cmd_prompt", "ipport",
			"separator", "inet4_only", "inet6_only" ]

	atexit.register(atexit_handler)
	
	all_opt["cmd_prompt"]["default"] = [ "MP>", "hpiLO->" ]
	all_opt["power_wait"]["default"] = 5
	
	options = check_input(device_opt, process_input(device_opt))
		
	docs = { }
	docs["shortdesc"] = "Fence agent for HP iLO MP"
	docs["longdesc"] = ""
	docs["vendorurl"] = "http://www.hp.com"
	show_docs(options, docs)
	
	conn = fence_login(options)
	conn.send_eol("SMCLP")

	##
	## Fence operations
	####
	result = fence_action(conn, options, set_power_status, get_power_status)

	try:
		conn.send_eol("exit")
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass
	
	sys.exit(result)

if __name__ == "__main__":
	main()
