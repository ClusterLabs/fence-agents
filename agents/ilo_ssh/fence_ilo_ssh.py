#!@PYTHON@ -tt

import sys, re
import atexit
import logging
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

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
		conn.send_eol("power off hard")

	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

	return

def reboot_cycle(conn, options):
	conn.send_eol("reset /system1 hard")
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

	if get_power_status(conn, options) == "off":
		logging.error("Timed out waiting to power ON\n")

	return True

def main():
	device_opt = ["ipaddr", "login", "passwd", "secure", "cmd_prompt", "method", "telnet"]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = ["MP>", "hpiLO->"]
	all_opt["power_wait"]["default"] = 5

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for HP iLO over SSH"
	docs["longdesc"] = "fence_ilo_ssh is a fence agent that connects to iLO device. It logs into \
device via ssh and reboot a specified outlet. "
	docs["vendorurl"] = "http://www.hp.com"
	docs["symlink"] = [("fence_ilo3_ssh", "Fence agent for HP iLO3 over SSH"),
		("fence_ilo4_ssh", "Fence agent for HP iLO4 over SSH")]
	show_docs(options, docs)

	options["eol"] = "\r"

	conn = fence_login(options)
	conn.send_eol("SMCLP")

	##
	## Fence operations
	####
	result = fence_action(conn, options, set_power_status, get_power_status, None, reboot_cycle)
	fence_logout(conn, "exit")
	sys.exit(result)

if __name__ == "__main__":
	main()
