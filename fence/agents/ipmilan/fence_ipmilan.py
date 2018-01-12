#!@PYTHON@ -tt

import sys, re, os
import atexit
from pipes import quote
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, is_executable, run_command, run_delay

def get_power_status(_, options):
	output = _run_command(options, "status")
	match = re.search('[Cc]hassis [Pp]ower is [\\s]*([a-zA-Z]{2,3})', str(output))
	status = match.group(1) if match else None
	return status

def set_power_status(_, options):
	_run_command(options, options["--action"])
	return

def reboot_cycle(_, options):
	output = _run_command(options, "cycle")
	return bool(re.search('chassis power control: cycle', str(output).lower()))

def reboot_diag(_, options):
	output = _run_command(options, "diag")
	return bool(re.search('chassis power control: diag', str(output).lower()))

def _run_command(options, action):
	cmd, log_cmd = create_command(options, action)
	return run_command(options, cmd, log_command=log_cmd)

def create_command(options, action):
	class Cmd:
		cmd = ""
		log = ""

		@classmethod
		def append(cls, cmd, log=None):
			cls.cmd += cmd
			cls.log += (cmd if log is None else log)

	# --use-sudo / -d
	if "--use-sudo" in options:
		Cmd.append(options["--sudo-path"] + " ")

	Cmd.append(options["--ipmitool-path"])

	# --lanplus / -L
	if "--lanplus" in options and options["--lanplus"] in ["", "1"]:
		Cmd.append(" -I lanplus")
	else:
		Cmd.append(" -I lan")

	# --ip / -a
	Cmd.append(" -H " + options["--ip"])

	# --port / -n
	if "--ipport" in options:
		Cmd.append(" -p " + options["--ipport"])

	# --target
	if "--target" in options:
		Cmd.append(" -t " + options["--target"])

	# --username / -l
	if "--username" in options and len(options["--username"]) != 0:
		Cmd.append(" -U " + quote(options["--username"]))

	# --auth / -A
	if "--auth" in options:
		Cmd.append(" -A " + options["--auth"])

	# --password / -p
	if "--password" in options:
		Cmd.append(" -P " + quote(options["--password"]), " -P [set]")
	else:
		Cmd.append(" -P ''", " -P [set]")

	# --cipher / -C
	if "--cipher" in options:
		Cmd.append(" -C " + options["--cipher"])

	if "--privlvl" in options:
		Cmd.append(" -L " + options["--privlvl"])

	if "--hexadecimal-kg" in options:
		Cmd.append(" -y " + options["--hexadecimal-kg"])

	# --action / -o
	Cmd.append(" chassis power " + action)

	return (Cmd.cmd, Cmd.log)

def define_new_opts():
	all_opt["lanplus"] = {
		"getopt" : "P",
		"longopt" : "lanplus",
		"help" : "-P, --lanplus                  Use Lanplus to improve security of connection",
		"required" : "0",
		"default" : "0",
		"shortdesc" : "Use Lanplus to improve security of connection",
		"order": 1
	}
	all_opt["auth"] = {
		"getopt" : "A:",
		"longopt" : "auth",
		"help" : "-A, --auth=[auth]              IPMI Lan Auth type (md5|password|none)",
		"required" : "0",
		"shortdesc" : "IPMI Lan Auth type.",
		"choices" : ["md5", "password", "none"],
		"order": 1
	}
	all_opt["cipher"] = {
		"getopt" : "C:",
		"longopt" : "cipher",
		"help" : "-C, --cipher=[cipher]          Ciphersuite to use (same as ipmitool -C parameter)",
		"required" : "0",
		"shortdesc" : "Ciphersuite to use (same as ipmitool -C parameter)",
		"order": 1
	}
	all_opt["privlvl"] = {
		"getopt" : "L:",
		"longopt" : "privlvl",
		"help" : "-L, --privlvl=[level]          "
				"Privilege level on IPMI device (callback|user|operator|administrator)",
		"required" : "0",
		"shortdesc" : "Privilege level on IPMI device",
		"default" : "administrator",
		"choices" : ["callback", "user", "operator", "administrator"],
		"order": 1
	}
	all_opt["ipmitool_path"] = {
		"getopt" : ":",
		"longopt" : "ipmitool-path",
		"help" : "--ipmitool-path=[path]         Path to ipmitool binary",
		"required" : "0",
		"shortdesc" : "Path to ipmitool binary",
		"default" : "@IPMITOOL_PATH@",
		"order": 200
	}
	all_opt["target"] = {
		"getopt" : ":",
		"longopt" : "target",
		"help" : "--target=[targetaddress]       Bridge IPMI requests to the remote target address",
		"required" : "0",
		"shortdesc" : "Bridge IPMI requests to the remote target address",
		"order": 1
	}
	all_opt["hexadecimal_kg"] = {
		"getopt" : ":",
		"longopt" : "hexadecimal-kg",
		"help" : "--hexadecimal-kg=[key]         Hexadecimal-encoded Kg key for IPMIv2 authentication",
		"required" : "0",
		"shortdesc" : "Hexadecimal-encoded Kg key for IPMIv2 authentication",
		"order": 1
	}

def main():
	atexit.register(atexit_handler)

	device_opt = ["ipaddr", "login", "no_login", "no_password", "passwd",
		"diag", "lanplus", "auth", "cipher", "privlvl", "sudo",
		"ipmitool_path", "method", "target", "hexadecimal_kg"]
	define_new_opts()

	all_opt["power_wait"]["default"] = 2
	if os.path.basename(sys.argv[0]) == "fence_ilo3":
		all_opt["power_wait"]["default"] = "4"
		all_opt["lanplus"]["default"] = "1"
	elif os.path.basename(sys.argv[0]) == "fence_ilo4":
		all_opt["lanplus"]["default"] = "1"

	all_opt["ipport"]["default"] = "623"
	all_opt["method"]["help"] = "-m, --method=[method]          Method to fence (onoff|cycle) (Default: cycle)\n" \
				    "WARNING! This fence agent might report success before the node is powered off. " \
				    "You should use -m/method onoff if your fence device works correctly with that option."

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for IPMI"
	docs["longdesc"] = "fence_ipmilan is an I/O Fencing agent\
which can be used with machines controlled by IPMI.\
This agent calls support software ipmitool (http://ipmitool.sf.net/). \
WARNING! This fence agent might report success before the node is powered off. \
You should use -m/method onoff if your fence device works correctly with that option."
	docs["vendorurl"] = ""
	docs["symlink"] = [("fence_ilo3", "Fence agent for HP iLO3"),
		("fence_ilo4", "Fence agent for HP iLO4"),
		("fence_imm", "Fence agent for IBM Integrated Management Module"),
		("fence_idrac", "Fence agent for Dell iDRAC")]
	show_docs(options, docs)

	run_delay(options)

	if not is_executable(options["--ipmitool-path"]):
		fail_usage("Ipmitool not found or not accessible")

	reboot_fn = reboot_cycle
	if options["--action"] == "diag":
		# Diag is a special action that can't be verified so we will reuse reboot functionality
		# to minimize impact on generic library
		options["--action"] = "reboot"
		options["--method"] = "cycle"
		reboot_fn = reboot_diag

	result = fence_action(None, options, set_power_status, get_power_status, None, reboot_fn)
	sys.exit(result)

if __name__ == "__main__":
	main()
