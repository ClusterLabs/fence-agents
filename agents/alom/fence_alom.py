#!@PYTHON@ -tt

# The Following Agent Has Been Tested On:
#
# Sun(tm) Advanced Lights Out Manager CMT v1.6.1
# as found on SUN T2000 Niagara

import sys, re, time
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

def get_power_status(conn, options):
	conn.send_eol("showplatform")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	status = re.search("standby", conn.before.lower())
	result = (status != None and "off" or "on")

	return result

def set_power_status(conn, options):
	cmd_line = (options["--action"] == "on" and "poweron" or "poweroff -f -y")
	conn.send_eol(cmd_line)
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))
	# Get the machine some time between poweron and poweroff
	time.sleep(int(options["--power-timeout"]))

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure"]

	atexit.register(atexit_handler)

	all_opt["secure"]["default"] = "1"
	all_opt["cmd_prompt"]["default"] = [r"sc\>\ "]

	options = check_input(device_opt, process_input(device_opt))
	options["telnet_over_ssh"] = 1

	docs = {}
	docs["shortdesc"] = "Fence agent for Sun ALOM"
	docs["longdesc"] = "fence_alom is an I/O Fencing \
agent which can be used with ALOM connected machines."
	docs["vendorurl"] = "http://www.sun.com"
	show_docs(options, docs)

	# Operate the fencing device
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, None)
	fence_logout(conn, "logout")
	sys.exit(result)

if __name__ == "__main__":
	main()
