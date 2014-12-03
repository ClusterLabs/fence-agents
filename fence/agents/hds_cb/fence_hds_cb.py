#!/usr/bin/python -tt

#####
##
## The Following Agent Has Been Tested On:
##
##  Model                 Modle/Firmware
## +--------------------+---------------------------+
## (1) Main application	  CB2000/A0300-E-6617
##
#####

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Compute Blade 2000 Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="November, 2012"
#END_VERSION_GENERATION

RE_STATUS_LINE = r"^([0-9]+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+).*$"

def get_power_status(conn, options):
	#### Maybe should put a conn.log_expect here to make sure
	#### we have properly entered into the main menu
	conn.sendline("S")	# Enter System Command Mode
	conn.log_expect("SVP>", int(options["--shell-timeout"]))
	conn.sendline("PC")	# Enter partition control
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	result = {}
	# Status can now be obtained from the output of the PC
	# command. Line looks like the following:
	# "P Power        Condition     LID lamp Mode  Auto power on"
	# "0 On           Normal        Off      Basic Synchronized"
	# "1 On           Normal        Off      Basic Synchronized"
	for line in conn.before.splitlines():
		# populate the relevant fields based on regex
		partition = re.search(RE_STATUS_LINE, line)
		if partition != None:
			# find the blade number defined in args
			if partition.group(1) == options["--plug"]:
				result = partition.group(2).lower()
	# We must make sure we go back to the main menu as the
	# status is checked before any fencing operations are
	# executed. We could in theory save some time by staying in
	# the partition control, but the logic is a little cleaner
	# this way.
	conn.sendline("Q")	# Back to system command mode
	conn.log_expect("SVP>", int(options["--shell-timeout"]))
	conn.sendline("EX")	# Back to system console main menu
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	return result

def set_power_status(conn, options):
	action = {
		'on' : "P",
		'off': "F",
		'reboot' : "H",
	}[options["--action"]]

	conn.sendline("S")	# Enter System Command Mode
	conn.log_expect("SVP>", int(options["--shell-timeout"]))
	conn.sendline("PC")	# Enter partition control
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.sendline("P")	# Enter power control menu
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.sendline(action)	# Execute action from array above
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.sendline(options["--plug"]) # Select blade number from args
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.sendline("Y")	# Confirm action
	conn.log_expect("Hit enter key.", int(options["--shell-timeout"]))
	conn.sendline("")	# Press the any key
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.sendline("Q")	# Quit back to partition control
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.sendline("Q")	# Quit back to system command mode
	conn.log_expect("SVP>", int(options["--shell-timeout"]))
	conn.sendline("EX")	# Quit back to system console menu
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

def get_blades_list(conn, options):
	outlets = {}

	conn.sendline("S")	# Enter System Command Mode
	conn.log_expect("SVP>", int(options["--shell-timeout"]))
	conn.sendline("PC")	# Enter partition control
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	# Status can now be obtained from the output of the PC
	# command. Line looks like the following:
	# "P Power        Condition     LID lamp Mode  Auto power on"
	# "0 On           Normal        Off      Basic Synchronized"
	# "1 On           Normal        Off      Basic Synchronized"
	for line in conn.before.splitlines():
		partition = re.search(RE_STATUS_LINE, line)
		if partition != None:
			outlets[partition.group(1)] = (partition.group(2), "")
	conn.sendline("Q")	# Quit back to system command mode
	conn.log_expect("SVP>", int(options["--shell-timeout"]))
	conn.sendline("EX")	# Quit back to system console menu
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	return outlets

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", \
			"port", "missing_as_off", "telnet"]

	atexit.register(atexit_handler)

	all_opt["power_wait"]["default"] = "5"
	all_opt["cmd_prompt"]["default"] = [r"\) :"]

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Hitachi Compute Blade systems"
	docs["longdesc"] = "fence_hds_cb is an I/O Fencing agent \
which can be used with Hitachi Compute Blades with recent enough firmware that \
includes telnet support."
	docs["vendorurl"] = "http://www.hds.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	######
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_blades_list)

	fence_logout(conn, "X")
	sys.exit(result)

if __name__ == "__main__":
	main()
