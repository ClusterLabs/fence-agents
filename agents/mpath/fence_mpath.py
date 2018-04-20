#!@PYTHON@ -tt

import sys
import stat
import re
import os
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import fail_usage, run_command, atexit_handler, check_input, process_input, show_docs
from fencing import fence_action, all_opt, run_delay

def get_status(conn, options):
	del conn
	status = "off"
	for dev in options["devices"]:
		is_block_device(dev)
		if options["--key"] in get_registration_keys(options, dev):
			status = "on"
		else:
			logging.debug("No registration for key "\
				+ options["--key"] + " on device " + dev + "\n")

	if options["--action"] == "monitor":
		dev_read(options)

	return status


def set_status(conn, options):
	del conn
	count = 0
	if options["--action"] == "on":
		for dev in options["devices"]:
			is_block_device(dev)

			register_dev(options, dev)
			if options["--key"] not in get_registration_keys(options, dev):
				count += 1
				logging.debug("Failed to register key "\
					+ options["--key"] + "on device " + dev + "\n")
				continue
			dev_write(options, dev)

			if get_reservation_key(options, dev) is None \
			and not reserve_dev(options, dev) \
			and get_reservation_key(options, dev) is None:
				count += 1
				logging.debug("Failed to create reservation (key="\
					+ options["--key"] + ", device=" + dev + ")\n")

	else:
		dev_keys = dev_read(options)

		for dev in options["devices"]:
			is_block_device(dev)

			if options["--key"] in get_registration_keys(options, dev):
				preempt_abort(options, dev_keys[dev], dev)

		for dev in options["devices"]:
			if options["--key"] in get_registration_keys(options, dev):
				count += 1
				logging.debug("Failed to remove key "\
					+ options["--key"] + " on device " + dev + "\n")
				continue

			if not get_reservation_key(options, dev):
				count += 1
				logging.debug("No reservation exists on device " + dev + "\n")
	if count:
		logging.error("Failed to verify " + str(count) + " device(s)")
		sys.exit(1)


#run command, returns dict, ret["err"] = exit code; ret["out"] = output
def run_cmd(options, cmd):
	ret = {}

	if "--use-sudo" in options:
		prefix = options["--sudo-path"] + " "
	else:
		prefix = ""

	(ret["err"], ret["out"], _) = run_command(options, prefix + cmd)
	ret["out"] = "".join([i for i in ret["out"] if i is not None])
	return ret


# check if device exist and is block device
def is_block_device(dev):
	if not os.path.exists(dev):
		fail_usage("Failed: device \"" + dev + "\" does not exist")
	if not stat.S_ISBLK(os.stat(dev).st_mode):
		fail_usage("Failed: device \"" + dev + "\" is not a block device")

# cancel registration
def preempt_abort(options, host, dev):
	cmd = options["--mpathpersist-path"] + " -o --preempt-abort --prout-type=5 --param-rk=" + host +" --param-sark=" + options["--key"] +" -d " + dev
	return not bool(run_cmd(options, cmd)["err"])

def register_dev(options, dev):
	cmd = options["--mpathpersist-path"] + " -o --register --param-sark=" + options["--key"] + " -d " + dev
	#cmd return code != 0 but registration can be successful
	return not bool(run_cmd(options, cmd)["err"])

def reserve_dev(options, dev):
	cmd = options["--mpathpersist-path"] + " -o --reserv --prout-type=5 --param-rk=" + options["--key"] + " -d " + dev
	return not bool(run_cmd(options, cmd)["err"])

def get_reservation_key(options, dev):
	cmd = options["--mpathpersist-path"] + " -i -r -d " + dev
	out = run_cmd(options, cmd)
	if out["err"]:
		fail_usage("Cannot get reservation key")
	match = re.search(r"\s+key\s*=\s*0x(\S+)\s+", out["out"], re.IGNORECASE)
	return match.group(1) if match else None

def get_registration_keys(options, dev):
	keys = []
	cmd = options["--mpathpersist-path"] + " -i -k -d " + dev
	out = run_cmd(options, cmd)
	if out["err"]:
		fail_usage("Cannot get registration keys")
	for line in out["out"].split("\n"):
		match = re.search(r"\s+0x(\S+)\s*", line)
		if match:
			keys.append(match.group(1))
	return keys

def dev_write(options, dev):
	file_path = options["--store-path"] + "/mpath.devices"

	if not os.path.isdir(options["--store-path"]):
		os.makedirs(options["--store-path"])

	try:
		store_fh = open(file_path, "a+")
	except IOError:
		fail_usage("Failed: Cannot open file \""+ file_path + "\"")
	out = store_fh.read()
	if not re.search(r"^" + dev + r"\s+", out):
		store_fh.write(dev + "\t" + options["--key"] + "\n")
	store_fh.close()

def dev_read(options):
	dev_key = {}
	file_path = options["--store-path"] + "/mpath.devices"
	try:
		store_fh = open(file_path, "r")
	except IOError:
		fail_usage("Failed: Cannot open file \"" + file_path + "\"")
	# get not empty lines from file
	for (device, key) in [line.strip().split() for line in store_fh if line.strip()]:
		dev_key[device] = key
	store_fh.close()
	return dev_key

def define_new_opts():
	all_opt["devices"] = {
		"getopt" : "d:",
		"longopt" : "devices",
		"help" : "-d, --devices=[devices]        List of devices to use for current operation",
		"required" : "1",
		"shortdesc" : "List of devices to use for current operation. Devices can \
be comma-separated list of device-mapper multipath devices (eg. /dev/mapper/3600508b400105df70000e00000ac0000 or /dev/mapper/mpath1). \
Each device must support SCSI-3 persistent reservations.",
		"order": 1
	}
	all_opt["key"] = {
		"getopt" : "k:",
		"longopt" : "key",
		"help" : "-k, --key=[key]                Key to use for the current operation",
		"required" : "1",
		"shortdesc" : "Key to use for the current operation. This key should be \
unique to a node and have to be written in /etc/multipath.conf. For the \"on\" action, the key specifies the key use to \
register the local node. For the \"off\" action, this key specifies the key to \
be removed from the device(s).",
		"order": 1
	}
	all_opt["mpathpersist_path"] = {
		"getopt" : ":",
		"longopt" : "mpathpersist-path",
		"help" : "--mpathpersist-path=[path]     Path to mpathpersist binary",
		"required" : "0",
		"shortdesc" : "Path to mpathpersist binary",
		"default" : "@MPATH_PATH@",
		"order": 200
	}
	all_opt["store_path"] = {
		"getopt" : ":",
		"longopt" : "store-path",
		"help" : "--store-path=[path]            Path to directory containing cached keys",
		"required" : "0",
		"shortdesc" : "Path to directory where fence agent can store information",
		"default" : "@STORE_PATH@",
		"order": 200
	}

def main():
	atexit.register(atexit_handler)

	device_opt = ["no_login", "no_password", "devices", "key", "sudo", \
	        "fabric_fencing", "on_target", "store_path", "mpathpersist_path", "force_on"]

	define_new_opts()

	options = check_input(device_opt, process_input(device_opt), other_conditions=True)

	docs = {}
	docs["shortdesc"] = "Fence agent for multipath persistent reservation"
	docs["longdesc"] = "fence_mpath is an I/O fencing agent that uses SCSI-3 \
persistent reservations to control access multipath devices. Underlying \
devices must support SCSI-3 persistent reservations (SPC-3 or greater) as \
well as the \"preempt-and-abort\" subcommand.\nThe fence_mpath agent works by \
having a unique key for each node that has to be set in /etc/multipath.conf. \
Once registered, a single node will become the reservation holder \
by creating a \"write exclusive, registrants only\" reservation on the \
device(s). The result is that only registered nodes may write to the \
device(s). When a node failure occurs, the fence_mpath agent will remove the \
key belonging to the failed node from the device(s). The failed node will no \
longer be able to write to the device(s). A manual reboot is required."
	docs["vendorurl"] = "https://www.sourceware.org/dm/"
	show_docs(options, docs)

	run_delay(options)

	# Input control BEGIN
	if not "--key" in options:
		fail_usage("Failed: key is required")

	if options["--action"] == "validate-all":
		sys.exit(0)

	options["devices"] = options["--devices"].split(",")

	if not options["devices"]:
		fail_usage("Failed: No devices found")
	# Input control END

	result = fence_action(None, options, set_status, get_status)
	sys.exit(result)

if __name__ == "__main__":
	main()
