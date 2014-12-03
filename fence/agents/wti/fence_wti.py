#!/usr/bin/python -tt

#####
##
## The Following Agent Has Been Tested On:
##
##  Version            Firmware
## +-----------------+---------------------------+
##  WTI RSM-8R4         ?? unable to find out ??
##  WTI MPC-??? 	?? unable to find out ??
##  WTI IPS-800-CE     v1.40h		(no username) ('list' tested)
#####

import sys, re, pexpect
import atexit
import time
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fspawn, fail, fail_usage, EC_LOGIN_DENIED

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New WTI Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

def get_listing(conn, options, listing_command):
	listing = ""

	conn.send_eol(listing_command)

	if isinstance(options["--command-prompt"], list):
		re_all = list(options["--command-prompt"])
	else:
		re_all = [options["--command-prompt"]]
	re_next = re.compile("Enter: ", re.IGNORECASE)
	re_all.append(re_next)

	result = conn.log_expect(re_all, int(options["--shell-timeout"]))
	listing = conn.before
	if result == (len(re_all) - 1):
		conn.send_eol("")
		conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
		listing += conn.before

	return listing

def get_plug_status(conn, options):
	listing = get_listing(conn, options, "/S")

	plug_section = 0
	plug_index = -1
	name_index = -1
	status_index = -1
	plug_header = list()
	outlets = {}

	for line in listing.splitlines():
		if (plug_section == 2) and line.find("|") >= 0 and line.startswith("PLUG") == False:
			plug_line = [x.strip().lower() for x in line.split("|")]
			if len(plug_line) < len(plug_header):
				plug_section = -1
			if ["list", "monitor"].count(options["--action"]) == 0 and \
					options["--plug"].lower() == plug_line[plug_index]:
				return plug_line[status_index]
			else:
				## We already believe that first column contains plug number
				if len(plug_line[0]) != 0:
					outlets[plug_line[0]] = (plug_line[name_index], plug_line[status_index])
		elif plug_section == 1:
			plug_section = 2
		elif line.upper().startswith("PLUG"):
			plug_section = 1
			plug_header = [x.strip().lower() for x in line.split("|")]
			plug_index = plug_header.index("plug")
			name_index = plug_header.index("name")
			status_index = plug_header.index("status")

	if ["list", "monitor"].count(options["--action"]) == 1:
		return outlets
	else:
		return "PROBLEM"

def get_plug_group_status_from_list(status_list):
	for status in status_list:
		if status == "on":
			return status
	return "off"

def get_plug_group_status(conn, options):
	listing = get_listing(conn, options, "/SG")

	outlets = {}
	line_index = 0
	status_index = -1
	plug_index = -1
	name_index = -1

	lines = listing.splitlines()
	while line_index < len(lines) and line_index >= 0:
		line = lines[line_index]
		if line.find("|") >= 0 and line.lstrip().startswith("GROUP NAME") == False:
			plug_line = [x.strip().lower() for x in line.split("|")]
			if ["list", "monitor"].count(options["--action"]) == 0 and \
					options["--plug"].lower() == plug_line[name_index]:
				plug_status = []
				while line_index < len(lines) and line_index >= 0:
					plug_line = [x.strip().lower() for x in lines[line_index].split("|")]
					if len(plug_line) >= max(name_index, status_index) and \
							len(plug_line[plug_index]) > 0 and \
							(len(plug_line[name_index]) == 0 or options["--plug"].lower() == plug_line[name_index]):
						## Firmware 1.43 does not have a valid value of plug on first line as only name is defined on that line
						if not "---" in plug_line[status_index]:
							plug_status.append(plug_line[status_index])
						line_index += 1
					else:
						line_index = -1

				return get_plug_group_status_from_list(plug_status)

			else:
				## We already believe that first column contains plug number
				if len(plug_line[0]) != 0:
					group_name = plug_line[0]
					plug_line_index = line_index + 1
					plug_status = []
					while plug_line_index < len(lines) and plug_line_index >= 0:
						plug_line = [x.strip().lower() for x in lines[plug_line_index].split("|")]
						if len(plug_line[name_index]) > 0:
							plug_line_index = -1
							break
						if len(plug_line[plug_index]) > 0:
							plug_status.append(plug_line[status_index])
							plug_line_index += 1
						else:
							plug_line_index = -1
					outlets[group_name] = (group_name, get_plug_group_status_from_list(plug_status))
				line_index += 1

		elif line.upper().lstrip().startswith("GROUP NAME"):
			plug_header = [x.strip().lower() for x in line.split("|")]
			name_index = plug_header.index("group name")
			plug_index = plug_header.index("plug")
			status_index = plug_header.index("status")
			line_index += 2
		else:
			line_index += 1


	if ["list", "monitor"].count(options["--action"]) == 1:
		results = {}
		for group, status in outlets.items():
			results[group] = (group, status[0])

		return results
	else:
		return "PROBLEM"

def get_power_status(conn, options):
	if ["list"].count(options["--action"]) == 0:
		ret = get_plug_status(conn, options)

		if ret == "PROBLEM":
			ret = get_plug_group_status(conn, options)
	else:
		ret = dict(get_plug_status(conn, options).items() + \
			get_plug_group_status(conn, options).items())

	return ret

def set_power_status(conn, options):
	action = {
		'on' : "/on",
		'off': "/off"
	}[options["--action"]]

	conn.send_eol(action + " " + options["--plug"] + ",y")
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

def main():
	device_opt = ["ipaddr", "login", "passwd", "no_login", "no_password", \
			"cmd_prompt", "secure", "port", "telnet"]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = ["RSM>", "MPC>", "IPS>", "TPS>", "NBB>", "NPS>", "VMR>"]

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for WTI"
	docs["longdesc"] = "fence_wti is an I/O Fencing agent \
which can be used with the WTI Network Power Switch (NPS). It logs \
into an NPS via telnet or ssh and boots a specified plug. \
Lengthy telnet connections to the NPS should be avoided while a GFS cluster \
is running because the connection will block any necessary fencing actions."
	docs["vendorurl"] = "http://www.wti.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	##
	## @note: if it possible that this device does not need either login, password or both of them
	#####
	if not options.has_key("--ssh"):
		try:
			if options["--action"] in ["off", "reboot"]:
				time.sleep(int(options["--delay"]))

			options["eol"] = "\r\n"

			conn = fspawn(options, options["--telnet-path"])
			conn.send("set binary\n")
			conn.send("open %s -%s\n"%(options["--ip"], options["--ipport"]))

			re_login = re.compile("(login: )|(Login Name:  )|(username: )|(User Name :)", re.IGNORECASE)
			re_prompt = re.compile("|".join(["(" + x + ")" for x in options["--command-prompt"]]), re.IGNORECASE)

			result = conn.log_expect([re_login, "Password: ", re_prompt], int(options["--shell-timeout"]))
			if result == 0:
				if options.has_key("--username"):
					conn.send_eol(options["--username"])
					result = conn.log_expect([re_login, "Password: ", re_prompt], int(options["--shell-timeout"]))
				else:
					fail_usage("Failed: You have to set login name")

			if result == 1:
				if options.has_key("--password"):
					conn.send_eol(options["--password"])
					conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
				else:
					fail_usage("Failed: You have to enter password or password script")
		except pexpect.EOF:
			fail(EC_LOGIN_DENIED)
		except pexpect.TIMEOUT:
			fail(EC_LOGIN_DENIED)
	else:
		conn = fence_login(options)

	result = fence_action(conn, options, set_power_status, get_power_status, get_power_status)
	fence_logout(conn, "/X")
	sys.exit(result)

if __name__ == "__main__":
	main()
