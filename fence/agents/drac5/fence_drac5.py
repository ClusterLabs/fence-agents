#!@PYTHON@ -tt

#####
##
## The Following Agent Has Been Tested On:
##
##  DRAC Version       Firmware
## +-----------------+---------------------------+
##  DRAC 5             1.0  (Build 06.05.12)
##  DRAC 5             1.21 (Build 07.05.04)
##
## @note: drac_version was removed
#####

import sys, re, time
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage

def get_power_status(conn, options):
	if options["--drac-version"] == "DRAC MC":
		(_, status) = get_list_devices(conn, options)[options["--plug"]]
	else:
		if options["--drac-version"] == "DRAC CMC":
			conn.send_eol("racadm serveraction powerstatus -m " + options["--plug"])
		elif options["--drac-version"] == "DRAC 5":
			conn.send_eol("racadm serveraction powerstatus")

		conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

		status = re.compile(r"(^|: )(ON|OFF|Powering ON|Powering OFF)\s*$",
				re.IGNORECASE | re.MULTILINE).search(conn.before).group(2)

	if status.lower().strip() in ["on", "powering on", "powering off"]:
		return "on"
	else:
		return "off"

def set_power_status(conn, options):
	action = {
		'on' : "powerup",
		'off': "powerdown"
	}[options["--action"]]

	if options["--drac-version"] == "DRAC CMC":
		conn.send_eol("racadm serveraction " + action + " -m " + options["--plug"])
	elif options["--drac-version"] == "DRAC 5":
		conn.send_eol("racadm serveraction " + action)
	elif options["--drac-version"] == "DRAC MC":
		conn.send_eol("racadm serveraction -s " + options["--plug"] + " " + action)

	## Fix issue with double-enter [CR/LF]
	##	We need to read two additional command prompts (one from get + one from set command)
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))
	if len(conn.before.strip()) == 0:
		options["eol"] = options["eol"][:-1]
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

def get_list_devices(conn, options):
	outlets = {}

	if options["--drac-version"] == "DRAC CMC":
		conn.send_eol("getmodinfo")

		list_re = re.compile(r"^([^\s]*?)\s+Present\s*(ON|OFF)\s*.*$")
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))
		for line in conn.before.splitlines():
			if list_re.search(line):
				outlets[list_re.search(line).group(1)] = ("", list_re.search(line).group(2))
	elif options["--drac-version"] == "DRAC MC":
		conn.send_eol("getmodinfo")

		list_re = re.compile(r"^\s*([^\s]*)\s*---->\s*(.*?)\s+Present\s*(ON|OFF)\s*.*$")
		conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))
		for line in conn.before.splitlines():
			if list_re.search(line):
				outlets[list_re.search(line).group(2)] = ("", list_re.search(line).group(3))
	elif options["--drac-version"] == "DRAC 5":
		## DRAC 5 can be used only for one computer
		## standard fence library can't handle correctly situation
		## when some fence devices supported by fence agent
		## works with 'list' and other should returns 'N/A'
		print("N/A")

	return outlets

def define_new_opts():
	all_opt["drac_version"] = {
		"getopt" : "d:",
		"longopt" : "drac-version",
		"help" : "-d, --drac-version=[version]   Force DRAC version to use (DRAC 5|DRAC CMC|DRAC MC)",
		"required" : "0",
		"shortdesc" : "Force DRAC version to use",
		"choices" : ["DRAC CMC", "DRAC MC", "DRAC 5"],
		"order" : 1}

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", \
			"drac_version", "port", "no_port", "telnet"]

	atexit.register(atexit_handler)

	define_new_opts()

	all_opt["cmd_prompt"]["default"] = [r"\$", r"DRAC\/MC:"]

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Dell DRAC CMC/5"
	docs["longdesc"] = "fence_drac5 is an I/O Fencing agent \
which can be used with the Dell Remote Access Card v5 or CMC (DRAC). \
This device provides remote access to controlling  power to a server. \
It logs into the DRAC through the telnet/ssh interface of the card. \
By default, the telnet interface is not  enabled."
	docs["vendorurl"] = "http://www.dell.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	######
	conn = fence_login(options)

	if "--drac-version" not in options:
		## autodetect from text issued by fence device
		if conn.before.find("CMC") >= 0:
			options["--drac-version"] = "DRAC CMC"
		elif conn.before.find("DRAC 5") >= 0:
			options["--drac-version"] = "DRAC 5"
		elif conn.after.find("DRAC/MC") >= 0:
			options["--drac-version"] = "DRAC MC"
		else:
			## Assume this is DRAC 5 by default as we don't want to break anything
			options["--drac-version"] = "DRAC 5"

	if options["--drac-version"] in ["DRAC MC", "DRAC CMC"]:
		if "--plug" not in options and 0 == ["monitor", "list"].count(options["--action"]):
			fail_usage("Failed: You have to enter module name (-n)")

	result = fence_action(conn, options, set_power_status, get_power_status, get_list_devices)
	fence_logout(conn, "exit", 1)
	sys.exit(result)

if __name__ == "__main__":
	main()
