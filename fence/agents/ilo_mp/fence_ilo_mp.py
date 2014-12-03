#!/usr/bin/python -tt

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_power_status(conn, options):
	conn.send_eol("show /system1")

	re_state = re.compile('EnabledState=(.*)', re.IGNORECASE)
	conn.log_expect(re_state, int(options["--shell-timeout"]))

	status = conn.match.group(1).lower()

	if status.startswith("enabled"):
		return "on"
	else:
		return "off"

def set_power_status(conn, options):
	if options["--action"] == "on":
		conn.send_eol("start /system1")
	else:
		conn.send_eol("stop -f /system1")

	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

	return

def main():
	device_opt = ["ipaddr", "login", "passwd", "secure", "cmd_prompt", "telnet"]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = ["MP>", "hpiLO->"]
	all_opt["power_wait"]["default"] = 5

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
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
	fence_logout(conn, "exit")
	sys.exit(result)

if __name__ == "__main__":
	main()
