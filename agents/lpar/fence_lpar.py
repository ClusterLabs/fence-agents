#!@PYTHON@ -tt

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
import logging
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_STATUS_HMC

##
## Transformation to standard ON/OFF status if possible
def _normalize_status(status):
	if status in ["Running", "Open Firmware", "Shutting Down", "Starting"]:
		status = "on"
	else:
		status = "off"

	return status

def get_power_status(conn, options):
	if options["--hmc-version"] == "3":
		command = "lssyscfg -r lpar -m " + options["--managed"] + " -n " + options["--plug"] + " -F name,state\n"
	elif options["--hmc-version"] in ["4", "IVM"]:
		command = "lssyscfg -r lpar -m "+ options["--managed"] + \
			" --filter 'lpar_names=" + options["--plug"] + "'\n"
	else:
		# Bad HMC Version cannot be reached
		fail(EC_STATUS_HMC)

	conn.send(command)
	# First line (command) may cause parsing issues if long
	conn.readline()
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

	try:
		if options["--hmc-version"] == "3":
			status = re.compile(r"^" + options["--plug"] + r",(.*?),.*$",
					    re.IGNORECASE | re.MULTILINE).search(conn.before).group(1)
		elif options["--hmc-version"] in ["4", "IVM"]:
			status = re.compile(r",state=(.*?),", re.IGNORECASE).search(conn.before).group(1)
	except AttributeError as e:
		logging.debug("Command on HMC failed: {}\n{}".format(command, str(e)))
		fail(EC_STATUS_HMC)

	return _normalize_status(status)

def is_comanaged(conn, options):
	conn.send("lscomgmt -m " + options["--managed"] + "\n" )
	conn.readline()
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

	try:
		cm = re.compile(r",curr_master_mtms=(.*?),", re.IGNORECASE).search(conn.before).group(1)
	except AttributeError as e:
		cm = False

	return cm

def set_power_status(conn, options):
	if options["--hmc-version"] == "3":
		conn.send("chsysstate -o " + options["--action"] + " -r lpar -m " + options["--managed"]
			+ " -n " + options["--plug"] + "\n")

		# First line (command) may cause parsing issues if long
		conn.readline()
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))
	elif options["--hmc-version"] in ["4", "IVM"]:
		if options["--action"] == "on":
			if is_comanaged(conn, options):
				profile = ""
			else:
				profile = " -f `lssyscfg -r lpar -F curr_profile " + \
				    " -m " + options["--managed"] + \
				    " --filter \"lpar_names=" + options["--plug"] + "\"`"
			conn.send("chsysstate -o on -r lpar" +
				" -m " + options["--managed"] +
				" -n " + options["--plug"] +
				profile +
				"\n")
		else:
			conn.send("chsysstate -o shutdown -r lpar --immed" +
				" -m " + options["--managed"] + " -n " + options["--plug"] + "\n")

		# First line (command) may cause parsing issues if long
		conn.readline()
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

def get_lpar_list(conn, options):
	outlets = {}
	if options["--hmc-version"] == "3":
		conn.send("query_partition_names -m " + options["--managed"] + "\n")

		## We have to remove first line (command)
		conn.readline()
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

		## We have to remove next 2 lines (header) and last line (part of new prompt)
		####
		res = re.search(r"^(.+?\n){2}(.*)\n.*$", conn.before, re.S)

		if res == None:
			fail_usage("Unable to parse output of list command")

		lines = res.group(2).split("\n")
		for outlet_line in lines:
			outlets[outlet_line.rstrip()] = ("", "")
	elif options["--hmc-version"] in ["4", "IVM"]:
		sep = ":" if options["--hmc-version"] == "4" else ","

		conn.send("lssyscfg -r lpar -m " + options["--managed"] +
			" -F name" + sep + "state\n")

		## We have to remove first line (command)
		conn.readline()
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

		## We have to remove last line (part of new prompt)
		####
		res = re.search(r"^(.*)\n.*$", conn.before, re.S)

		if res == None:
			fail_usage("Unable to parse output of list command")

		lines = res.group(1).split("\n")
		for outlet_line in lines:
			try:
				(port, status) = outlet_line.rstrip().split(sep)
			except ValueError:
				fail_usage('Output does not match expected HMC version, try different one');
			outlets[port] = ("", _normalize_status(status))

	return outlets

def define_new_opts():
	all_opt["managed"] = {
		"getopt" : "s:",
		"longopt" : "managed",
		"help" : "-s, --managed=[id]             Name of the managed system",
		"required" : "1",
		"shortdesc" : "Managed system name",
		"order" : 1}
	all_opt["hmc_version"] = {
		"getopt" : "H:",
		"longopt" : "hmc-version",
		"help" : "-H, --hmc-version=[version]    Force HMC version to use: (3|4|ivm) (default: 4)",
		"required" : "0",
		"shortdesc" : "Force HMC version to use",
		"default" : "4",
		"choices" : ["3", "4", "ivm"],
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
	docs["longdesc"] = "fence_lpar is a Power Fencing agent for IBM LPAR."
	docs["vendorurl"] = "http://www.ibm.com"
	show_docs(options, docs)

	if "--managed" not in options:
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
