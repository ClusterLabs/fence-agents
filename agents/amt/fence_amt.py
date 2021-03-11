#!@PYTHON@ -tt

import sys, re, os
import atexit
from pipes import quote
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, is_executable, run_command, run_delay

def get_power_status(_, options):
	output = amt_run_command(options, create_command(options, "status"))
	match = re.search('Powerstate:[\\s]*(..)', str(output))
	status = match.group(1) if match else None

	if status == None:
		return "fail"
	elif status == "S0": # SO = on; S3 = sleep; S5 = off
		return "on"
	else:
		return "off"

def set_power_status(_, options):
	amt_run_command(options, create_command(options, options["--action"]))
	return

def reboot_cycle(_, options):
	(status, _, _) = run_command(options, create_command(options, "cycle"))
	return not bool(status)

def amt_run_command(options, command, timeout=None):
	env = os.environ.copy()

	x = quote(options["--password"])
	x = x[:-1] if x.endswith("'") else x
	x = x[1:] if x.startswith("'") else x
	env["AMT_PASSWORD"] = x

	# This is needed because setting the AMT_PASSWORD env
	# variable only works when no pipe is involved. E.g.:
	# - Broken:
	# $ AMT_PASSWORD='foobar' echo 'y' |  /usr/bin/amttool nuc2 powerdown
	# 401 Unauthorized at /usr/bin/amttool line 129.
	# - Working:
	# $ AMT_PASSWORD='foobar' sh -c "(echo 'y' | /usr/bin/amttool nuc2 powerdown)"
	# execute: powerdown
	# result: pt_status: success
	newcommand = "sh -c \"(%s)\"" % command
	return run_command(options, newcommand, timeout, env)

def create_command(options, action):
	cmd = options["--amttool-path"]

	# --ip / -a
	cmd += " " + options["--ip"]

	# --action / -o
	if action == "status":
		cmd += " info"
	elif action == "on":
		cmd = "echo \"y\"|" + cmd
		cmd += " powerup"
	elif action == "off":
		cmd = "echo \"y\"|" + cmd
		cmd += " powerdown"
	elif action == "cycle":
		cmd = "echo \"y\"|" + cmd
		cmd += " powercycle"
	if action in ["on", "off", "cycle"] and "--boot-option" in options:
		cmd += options["--boot-option"]

	# --use-sudo / -d
	if "--use-sudo" in options:
		cmd = options["--sudo-path"] + " " + cmd

	return cmd

def define_new_opts():
	all_opt["boot_option"] = {
		"getopt" : "b:",
		"longopt" : "boot-option",
		"help" : "-b, --boot-option=[option]     "
				"Change the default boot behavior of the machine. (pxe|hd|hdsafe|cd|diag)",
		"required" : "0",
		"shortdesc" : "Change the default boot behavior of the machine.",
		"choices" : ["pxe", "hd", "hdsafe", "cd", "diag"],
		"order" : 1
	}
	all_opt["amttool_path"] = {
		"getopt" : ":",
		"longopt" : "amttool-path",
		"help" : "--amttool-path=[path]          Path to amttool binary",
		"required" : "0",
		"shortdesc" : "Path to amttool binary",
		"default" : "@AMTTOOL_PATH@",
		"order": 200
	}

def main():
	atexit.register(atexit_handler)

	device_opt = ["ipaddr", "no_login", "passwd", "boot_option", "no_port",
		"sudo", "amttool_path", "method"]

	define_new_opts()

	all_opt["ipport"]["default"] = "16994"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for AMT"
	docs["longdesc"] = "fence_amt is an I/O Fencing agent \
which can be used with Intel AMT. This agent calls support software amttool\
(http://www.kraxel.org/cgit/amtterm/)."
	docs["vendorurl"] = "http://www.intel.com/"
	show_docs(options, docs)

	run_delay(options)

	if not is_executable(options["--amttool-path"]):
		fail_usage("Amttool not found or not accessible")

	result = fence_action(None, options, set_power_status, get_power_status, None, reboot_cycle)

	sys.exit(result)

if __name__ == "__main__":
	main()
