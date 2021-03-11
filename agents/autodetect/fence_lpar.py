#!/usr/bin/python -tt

#####
##
## The Following Agent Has Been Tested On:
##
##  Version
## +---------------------------------------------+
##  Tested on HMC
##
#####

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_STATUS_HMC

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_power_status(conn, options):
	if options["--hmc-version"] == "3":
		conn.send("lssyscfg -r lpar -m " + options["--managed"] + " -n " + options["--plug"] + " -F name,state\n")
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

		try:
			status = re.compile("^" + options["--plug"] + ",(.*?),.*$",
					re.IGNORECASE | re.MULTILINE).search(conn.before).group(1)
		except AttributeError:
			fail(EC_STATUS_HMC)
	elif options["--hmc-version"] == "4":
		conn.send("lssyscfg -r lpar -m "+ options["--managed"] +
				" --filter 'lpar_names=" + options["--plug"] + "'\n")
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

		try:
			status = re.compile(",state=(.*?),", re.IGNORECASE).search(conn.before).group(1)
		except AttributeError:
			fail(EC_STATUS_HMC)

	##
	## Transformation to standard ON/OFF status if possible
	if status in ["Running", "Open Firmware", "Shutting Down", "Starting"]:
		status = "on"
	else:
		status = "off"

	return status

def set_power_status(conn, options):
	if options["--hmc-version"] == "3":
		conn.send("chsysstate -o " + options["--action"] + " -r lpar -m " + options["--managed"]
			+ " -n " + options["--plug"] + "\n")
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))
	elif options["--hmc-version"] == "4":
		if options["--action"] == "on":
			conn.send("chsysstate -o on -r lpar -m " + options["--managed"] +
				" -n " + options["--plug"] +
				" -f `lssyscfg -r lpar -F curr_profile " +
				" -m " + options["--managed"] +
				" --filter \"lpar_names=" + options["--plug"] + "\"`\n")
		else:
			conn.send("chsysstate -o shutdown -r lpar --immed" +
				" -m " + options["--managed"] + " -n " + options["--plug"] + "\n")
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

def get_lpar_list(conn, options):
	outlets = {}
	if options["--hmc-version"] == "3":
		conn.send("query_partition_names -m " + options["--managed"] + "\n")
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

		## We have to remove first 3 lines (command + header) and last line (part of new prompt)
		####
		res = re.search("^.+?\n(.+?\n){2}(.*)\n.*$", conn.before, re.S)

		if res == None:
			fail_usage("Unable to parse output of list command")

		lines = res.group(2).split("\n")
		for outlet_line in lines:
			outlets[outlet_line.rstrip()] = ("", "")
	elif options["--hmc-version"] == "4":
		conn.send("lssyscfg -r lpar -m " + options["--managed"] +
			" -F name:state\n")
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

		## We have to remove first line (command) and last line (part of new prompt)
		####
		res = re.search("^.+?\n(.*)\n.*$", conn.before, re.S)

		if res == None:
			fail_usage("Unable to parse output of list command")

		lines = res.group(1).split("\n")
		for outlet_line in lines:
			(port, status) = outlet_line.split(":")
			outlets[port] = ("", status)

	return outlets

def define_new_opts():
	all_opt["managed"] = {
		"getopt" : "s:",
		"longopt" : "managed",
		"help" : "-s, --managed=[id]             Name of the managed system",
		"required" : "0",
		"shortdesc" : "Managed system name",
		"order" : 1}
	all_opt["hmc_version"] = {
		"getopt" : "H:",
		"longopt" : "hmc-version",
		"help" : "-H, --hmc-version=[version]    Force HMC version to use: (3|4) (default: 4)",
		"required" : "0",
		"shortdesc" : "Force HMC version to use",
		"default" : "4",
		"choices" : ["3", "4"],
		"order" : 1}

def main():
	device_opt = ["ipaddr", "login", "passwd", "secure", "cmd_prompt", \
	                "port", "managed", "hmc_version"]

	atexit.register(atexit_handler)

	define_new_opts()

	all_opt["login_timeout"]["default"] = "15"
	all_opt["secure"]["default"] = "1"
	all_opt["cmd_prompt"]["default"] = [r":~>", r"]\$", r"\$ "]

	options = check_input(device_opt, process_input(device_opt), other_conditions = True)

	docs = {}
	docs["shortdesc"] = "Fence agent for IBM LPAR"
	docs["longdesc"] = ""
	docs["vendorurl"] = "http://www.ibm.com"
	show_docs(options, docs)

	if not options.has_key("--managed"):
		fail_usage("Failed: You have to enter name of managed system")

	if options["--action"] == "validate-all":
		sys.exit(0)

	##
	## Operate the fencing device
	####
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_lpar_list)
	fence_logout(conn, "quit\r\n")
	sys.exit(result)

if __name__ == "__main__":
	main()
