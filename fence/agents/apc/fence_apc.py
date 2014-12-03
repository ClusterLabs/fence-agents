#!/usr/bin/python -tt

#####
##
## The Following Agent Has Been Tested On:
##
##  Model       Firmware
## +---------------------------------------------+
##  AP7951	AOS v2.7.0, PDU APP v2.7.3
##  AP7941      AOS v3.5.7, PDU APP v3.5.6
##  AP9606	AOS v2.5.4, PDU APP v2.7.3
##
## @note: ssh is very slow on AP79XX devices protocol (1) and
##        cipher (des/blowfish) have to be defined
#####

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_STATUS

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New APC Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

def get_power_status(conn, options):
	exp_result = 0
	outlets = {}

	conn.send_eol("1")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	version = 0
	admin = 0
	switch = 0

	if None != re.compile('.* MasterSwitch plus.*', re.IGNORECASE | re.S).match(conn.before):
		switch = 1
		if None != re.compile('.* MasterSwitch plus 2', re.IGNORECASE | re.S).match(conn.before):
			if not options.has_key("--switch"):
				fail_usage("Failed: You have to enter physical switch number")
		else:
			if not options.has_key("--switch"):
				options["--switch"] = "1"

	if None == re.compile('.*Outlet Management.*', re.IGNORECASE | re.S).match(conn.before):
		version = 2
	else:
		version = 3

	if None == re.compile('.*Outlet Control/Configuration.*', re.IGNORECASE | re.S).match(conn.before):
		admin = 0
	else:
		admin = 1

	if switch == 0:
		if version == 2:
			if admin == 0:
				conn.send_eol("2")
			else:
				conn.send_eol("3")
		else:
			conn.send_eol("2")
			conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
			conn.send_eol("1")
	else:
		conn.send_eol(options["--switch"])

	while True:
		exp_result = conn.log_expect(
				["Press <ENTER>"] + options["--command-prompt"], int(options["--shell-timeout"]))
		lines = conn.before.split("\n")
		show_re = re.compile(r'(^|\x0D)\s*(\d+)- (.*?)\s+(ON|OFF)\s*')
		for line in lines:
			res = show_re.search(line)
			if res != None:
				outlets[res.group(2)] = (res.group(3), res.group(4))
		conn.send_eol("")
		if exp_result != 0:
			break
	conn.send(chr(03))
	conn.log_expect("- Logout", int(options["--shell-timeout"]))
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	if ["list", "monitor"].count(options["--action"]) == 1:
		return outlets
	else:
		try:
			(_, status) = outlets[options["--plug"]]
			return status.lower().strip()
		except KeyError:
			fail(EC_STATUS)

def set_power_status(conn, options):
	action = {
		'on' : "1",
		'off': "2"
	}[options["--action"]]

	conn.send_eol("1")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	version = 0
	admin2 = 0
	admin3 = 0
	switch = 0

	if None != re.compile('.* MasterSwitch plus.*', re.IGNORECASE | re.S).match(conn.before):
		switch = 1
		## MasterSwitch has different schema for on/off actions
		action = {
			'on' : "1",
			'off': "3"
		}[options["--action"]]
		if None != re.compile('.* MasterSwitch plus 2', re.IGNORECASE | re.S).match(conn.before):
			if not options.has_key("--switch"):
				fail_usage("Failed: You have to enter physical switch number")
		else:
			if not options.has_key("--switch"):
				options["--switch"] = 1

	if None == re.compile('.*Outlet Management.*', re.IGNORECASE | re.S).match(conn.before):
		version = 2
	else:
		version = 3

	if None == re.compile('.*Outlet Control/Configuration.*', re.IGNORECASE | re.S).match(conn.before):
		admin2 = 0
	else:
		admin2 = 1

	if switch == 0:
		if version == 2:
			if admin2 == 0:
				conn.send_eol("2")
			else:
				conn.send_eol("3")
		else:
			conn.send_eol("2")
			conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
			if None == re.compile('.*2- Outlet Restriction.*', re.IGNORECASE | re.S).match(conn.before):
				admin3 = 0
			else:
				admin3 = 1
			conn.send_eol("1")
	else:
		conn.send_eol(options["--switch"])

	while 0 == conn.log_expect(
			["Press <ENTER>"] + options["--command-prompt"], int(options["--shell-timeout"])):
		conn.send_eol("")

	conn.send_eol(options["--plug"]+"")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	if switch == 0:
		if admin2 == 1:
			conn.send_eol("1")
			conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
		if admin3 == 1:
			conn.send_eol("1")
			conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	else:
		conn.send_eol("1")
		conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	conn.send_eol(action)
	conn.log_expect("Enter 'YES' to continue or <ENTER> to cancel :", int(options["--shell-timeout"]))
	conn.send_eol("YES")
	conn.log_expect("Press <ENTER> to continue...", int(options["--power-timeout"]))
	conn.send_eol("")
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))
	conn.send(chr(03))
	conn.log_expect("- Logout", int(options["--shell-timeout"]))
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

def get_power_status5(conn, options):
	outlets = {}

	conn.send_eol("olStatus all")

	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	lines = conn.before.split("\n")

	show_re = re.compile(r'^\s*(\d+): (.*): (On|Off)\s*$', re.IGNORECASE)

	for line in lines:
		res = show_re.search(line)
		if res != None:
			outlets[res.group(1)] = (res.group(2), res.group(3))

	if ["list", "monitor"].count(options["--action"]) == 1:
		return outlets
	else:
		try:
			(_, status) = outlets[options["--plug"]]
			return status.lower().strip()
		except KeyError:
			fail(EC_STATUS)

def set_power_status5(conn, options):
	action = {
		'on' : "olOn",
		'off': "olOff"
	}[options["--action"]]

	conn.send_eol(action + " " + options["--plug"])
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", \
			"port", "switch", "telnet"]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = ["\n>", "\napc>"]
	all_opt["ssh_options"]["default"] = "-1 -c blowfish"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for APC over telnet/ssh"
	docs["longdesc"] = "fence_apc is an I/O Fencing agent \
which can be used with the APC network power switch. It logs into device \
via telnet/ssh  and reboots a specified outlet. Lengthy telnet/ssh connections \
should be avoided while a GFS cluster  is  running  because  the  connection \
will block any necessary fencing actions."
	docs["vendorurl"] = "http://www.apc.com"
	show_docs(options, docs)

	## Support for --plug [switch]:[plug] notation that was used before
	if (options.has_key("--plug") == 1) and (-1 != options["--plug"].find(":")):
		(switch, plug) = options["--plug"].split(":", 1)
		options["--switch"] = switch
		options["--plug"] = plug

	##
	## Operate the fencing device
	####
	conn = fence_login(options)

	## Detect firmware version (ASCII menu vs command-line interface)
	## and continue with proper action
	####
	result = -1
	firmware_version = re.compile(r'\s*v(\d)*\.').search(conn.before)
	if (firmware_version != None) and (firmware_version.group(1) == "5"):
		result = fence_action(conn, options, set_power_status5, get_power_status5, get_power_status5)
	else:
		result = fence_action(conn, options, set_power_status, get_power_status, get_power_status)

	fence_logout(conn, "4")
	sys.exit(result)

if __name__ == "__main__":
	main()
