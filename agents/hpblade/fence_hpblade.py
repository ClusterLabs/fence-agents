#!@PYTHON@ -tt

#####
##
## The Following Agent Has Been Tested On:
##  * HP BladeSystem c7000 Enclosure
##  * HP Integrity Superdome X (BL920s)
#####

import sys, re
import pexpect
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_STATUS

def get_enclosure_type(conn, options):
	conn.send_eol("show enclosure info")
	conn.log_expect(options, options["--command-prompt"], int(options["--shell-timeout"]))

	type_re=re.compile(r"^\s*Enclosure Type: (\w+)(.*?)\s*$")
	enclosure="unknown"
	for line in conn.before.splitlines():
		res = type_re.search(line)
		if res != None:
			enclosure=res.group(1)

	if enclosure == "unknown":
		fail(EC_GENERIC_ERROR)

	return enclosure.lower().strip()

def get_power_status(conn, options):
	if options["enc_type"] == "superdome":
		cmd_send = "parstatus -M -p " + options["--plug"]
		powrestr = "^partition:\\d\\s+:\\w+\\s+/(\\w+)\\s.*$"
	else:
		cmd_send = "show server status " + options["--plug"]
		powrestr = "^\\s*Power: (.*?)\\s*$"

	conn.send_eol(cmd_send)
	conn.log_expect(options, options["--command-prompt"], int(options["--shell-timeout"]))

	power_re = re.compile(powrestr)
	status = "unknown"
	for line in conn.before.splitlines():
		res = power_re.search(line)
		if res != None:
			if options["enc_type"] == "superdome":
				if res.group(1) == "DOWN":
					status = "off"
				else:
					status = "on"
			else:
				status = res.group(1)

	if status == "unknown":
		if "--missing-as-off" in options:
			return "off"
		else:
			fail(EC_STATUS)

	return status.lower().strip()

def set_power_status(conn, options):
	if options["enc_type"] == "superdome":
		dev="partition "
	else:
		dev="server "

	if options["--action"] == "on":
		conn.send_eol("poweron " + dev + options["--plug"])
	elif options["--action"] == "off":
		conn.send_eol("poweroff " + dev + options["--plug"] + " force")
	conn.log_expect(options, options["--command-prompt"], int(options["--shell-timeout"]))

def get_instances_list(conn, options):
	outlets = {}
	if options["enc_type"] == "superdome":
		cmd_send = "parstatus -P -M"
		listrestr = "^partition:(\\d+)\\s+:\\w+\\s+/(\\w+)\\s+:OK.*?:(\\w+)\\s*$"
	else:
		cmd_send = "show server list"
		listrestr = "^\\s*(\\d+)\\s+(.*?)\\s+(.*?)\\s+OK\\s+(.*?)\\s+(.*?)\\s*$"

	conn.send_eol(cmd_send)
	conn.log_expect(options, options["--command-prompt"], int(options["--shell-timeout"]))

	list_re = re.compile(listrestr)
	for line in conn.before.splitlines():
		res = list_re.search(line)
		if res != None:
			if options["enc_type"] == "superdome":
				outlets[res.group(1)] = (res.group(3), res.group(2).lower())
			else:
				outlets[res.group(1)] = (res.group(2), res.group(4).lower())

	return outlets

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", \
		"port", "missing_as_off", "telnet"]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = ["c7000oa>"]
	all_opt["login_timeout"]["default"] = "10"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for HP BladeSystem"
	docs["longdesc"] = "fence_hpblade is an I/O Fencing agent \
which can be used with HP BladeSystem and HP Integrity Superdome X. \
It logs into the onboard administrator of an enclosure via telnet or \
ssh and uses the command line interface to power blades or partitions \
on or off."
	docs["vendorurl"] = "http://www.hp.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	######
	options["eol"] = "\n"
	conn = fence_login(options)

	options["enc_type"] = get_enclosure_type(conn, options)

	result = fence_action(conn, options, set_power_status, get_power_status, get_instances_list)
	fence_logout(conn, "exit")
	sys.exit(result)

if __name__ == "__main__":
	main()
