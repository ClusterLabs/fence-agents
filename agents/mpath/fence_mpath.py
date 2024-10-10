#!@PYTHON@ -tt

import sys
import stat
import re
import os
import time
import logging
import atexit
import ctypes
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import fail_usage, run_command, atexit_handler, check_input, process_input, show_docs
from fencing import fence_action, all_opt, run_delay

def get_status(conn, options):
	del conn
	status = "off"
	for dev in options["devices"]:
		is_block_device(dev)
		if options["--plug"] in get_registration_keys(options, dev):
			status = "on"
		else:
			logging.debug("No registration for key "\
				+ options["--plug"] + " on device " + dev + "\n")

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
			if options["--plug"] not in get_registration_keys(options, dev):
				count += 1
				logging.debug("Failed to register key "\
					+ options["--plug"] + " on device " + dev + "\n")
				continue
			dev_write(options, dev)

			if get_reservation_key(options, dev) is None \
			and not reserve_dev(options, dev) \
			and get_reservation_key(options, dev) is None:
				count += 1
				logging.debug("Failed to create reservation (key="\
					+ options["--plug"] + ", device=" + dev + ")\n")

	else:
		dev_keys = dev_read(options)

		for dev in options["devices"]:
			is_block_device(dev)

			if options["--plug"] in get_registration_keys(options, dev):
				preempt_abort(options, dev_keys[dev], dev)

		for dev in options["devices"]:
			if options["--plug"] in get_registration_keys(options, dev):
				count += 1
				logging.debug("Failed to remove key "\
					+ options["--plug"] + " on device " + dev + "\n")
				continue

			if not get_reservation_key(options, dev):
				count += 1
				logging.debug("No reservation exists on device " + dev + "\n")
	if count:
		logging.error("Failed to verify " + str(count) + " device(s)")
		sys.exit(1)


# run command, returns dict, ret["rc"] = exit code; ret["out"] = output;
# ret["err"] = error
def run_cmd(options, cmd):
	ret = {}

	if "--use-sudo" in options:
		prefix = options["--sudo-path"] + " "
	else:
		prefix = ""

	(ret["rc"], ret["out"], ret["err"]) = run_command(options,
							    prefix + cmd)
	ret["out"] = "".join([i for i in ret["out"] if i is not None])
	ret["err"] = "".join([i for i in ret["err"] if i is not None])
	return ret


# check if device exist and is block device
def is_block_device(dev):
	if not os.path.exists(dev):
		fail_usage("Failed: device \"" + dev + "\" does not exist")
	if not stat.S_ISBLK(os.stat(dev).st_mode):
		fail_usage("Failed: device \"" + dev + "\" is not a block device")

# cancel registration
def preempt_abort(options, host, dev):
	cmd = options["--mpathpersist-path"] + " -o --preempt-abort --prout-type=5 --param-rk=" + host +" --param-sark=" + options["--plug"] +" -d " + dev
	return not bool(run_cmd(options, cmd)["rc"])

def register_dev(options, dev):
	cmd = options["--mpathpersist-path"] + " -o --register --param-sark=" + options["--plug"] + " -d " + dev
	#cmd return code != 0 but registration can be successful
	return not bool(run_cmd(options, cmd)["rc"])

def reserve_dev(options, dev):
	cmd = options["--mpathpersist-path"] + " -o --reserve --prout-type=5 --param-rk=" + options["--plug"] + " -d " + dev
	return not bool(run_cmd(options, cmd)["rc"])

def get_reservation_key(options, dev):
	cmd = options["--mpathpersist-path"] + " -i -r -d " + dev
	out = run_cmd(options, cmd)
	if out["rc"]:
		fail_usage('Cannot get reservation key on device "' + dev
                        + '": ' + out["err"])
	match = re.search(r"\s+key\s*=\s*0x(\S+)\s+", out["out"], re.IGNORECASE)
	return match.group(1) if match else None

def get_registration_keys(options, dev, fail=True):
	keys = []
	cmd = options["--mpathpersist-path"] + " -i -k -d " + dev
	out = run_cmd(options, cmd)
	if out["rc"]:
		fail_usage('Cannot get registration keys on device "' + dev
                        + '": ' + out["err"], fail)
		if not fail:
			return []
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
	store_fh.seek(0)
	out = store_fh.read()
	if not re.search(r"^{}\s+{}$".format(dev, options["--plug"]), out, flags=re.MULTILINE):
		store_fh.write(dev + "\t" + options["--plug"] + "\n")
	store_fh.close()

def dev_read(options, fail=True):
	dev_key = {}
	file_path = options["--store-path"] + "/mpath.devices"
	try:
		store_fh = open(file_path, "r")
	except IOError:
		if fail:
			fail_usage("Failed: Cannot open file \"" + file_path + "\"")
		else:
			return None
	# get not empty lines from file
	for (device, key) in [line.strip().split() for line in store_fh if line.strip()]:
		dev_key[device] = key
	store_fh.close()
	return dev_key

def mpath_check_get_options(options):
	try:
		f = open("/etc/sysconfig/stonith", "r")
	except IOError:
		return options

	match = re.findall(r"^\s*(\S*)\s*=\s*(\S*)\s*", "".join(f.readlines()), re.MULTILINE)

	for m in match:
		options[m[0].lower()] = m[1].lower()

	f.close()

	return options

def mpath_check(hardreboot=False):
	if len(sys.argv) >= 3 and sys.argv[1] == "repair":
		return int(sys.argv[2])
	options = {}
	options["--mpathpersist-path"] = "/usr/sbin/mpathpersist"
	options["--store-path"] = "@STORE_PATH@"
	options["--power-timeout"] = "5"
	options["retry"] = "0"
	options["retry-sleep"] = "1"
	options = mpath_check_get_options(options)
	if "verbose" in options and options["verbose"] == "yes":
		logging.getLogger().setLevel(logging.DEBUG)
	devs = dev_read(options, fail=False)
	if not devs:
		if "--suppress-errors" not in options:
			logging.error("No devices found")
		return 0
	for dev, key in list(devs.items()):
		for n in range(int(options["retry"]) + 1):
			if n > 0:
				logging.debug("retry: " + str(n) + " of " + options["retry"])
			if key in get_registration_keys(options, dev, fail=False):
				logging.debug("key " + key + " registered with device " + dev)
				return 0
			else:
				logging.debug("key " + key + " not registered with device " + dev)

			if n < int(options["retry"]):
				time.sleep(float(options["retry-sleep"]))
	logging.debug("key " + key + " registered with any devices")

	if hardreboot == True:
		libc = ctypes.cdll['libc.so.6']
		libc.reboot(0x1234567)
	return 2

def define_new_opts():
	all_opt["devices"] = {
		"getopt" : "d:",
		"longopt" : "devices",
		"help" : "-d, --devices=[devices]        List of devices to use for current operation",
		"required" : "0",
		"shortdesc" : "List of devices to use for current operation. Devices can \
be comma or space separated list of device-mapper multipath devices (eg. /dev/mapper/3600508b400105df70000e00000ac0000 or /dev/mapper/mpath1). \
Each device must support SCSI-3 persistent reservations.",
		"order": 1
	}
	all_opt["key"] = {
		"getopt" : "k:",
		"longopt" : "key",
		"help" : "-k, --key=[key]                Replaced by -n, --plug",
		"required" : "0",
		"shortdesc" : "Replaced by port/-n/--plug",
		"order": 1
	}
	all_opt["suppress-errors"] = {
		"getopt" : "",
		"longopt" : "suppress-errors",
		"help" : "--suppress-errors              Suppress error log. Suppresses error logging when run from the watchdog service before pacemaker starts.",
		"required" : "0",
		"shortdesc" : "Error log suppression.",
		"order": 4
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
	        "fabric_fencing", "on_target", "store_path", \
		"suppress-errors", "mpathpersist_path", "force_on", "port", "no_port"]

	define_new_opts()

	all_opt["port"]["required"] = "0"
	all_opt["port"]["help"] = "-n, --plug=[key]               Key to use for the current operation"
	all_opt["port"]["shortdesc"] = "Key to use for the current operation. \
This key should be unique to a node and have to be written in \
/etc/multipath.conf. For the \"on\" action, the key specifies the key use to \
register the local node. For the \"off\" action, this key specifies the key to \
be removed from the device(s)."

	# fence_mpath_check
	if os.path.basename(sys.argv[0]) == "fence_mpath_check":
		sys.exit(mpath_check())
	elif os.path.basename(sys.argv[0]) == "fence_mpath_check_hardreboot":
		sys.exit(mpath_check(hardreboot=True))

	options = check_input(device_opt, process_input(device_opt), other_conditions=True)

	# hack to remove list/list-status actions which are not supported
	options["device_opt"] = [ o for o in options["device_opt"] if o != "separator" ]

	# workaround to avoid regressions
	if "--key" in options:
		options["--plug"] = options["--key"]
		del options["--key"]
	elif "--help" not in options and options["--action"] in ["off", "on", \
	     "reboot", "status", "validate-all"] and "--plug" not in options:
		stop_after_error = False if options["--action"] == "validate-all" else True
		fail_usage("Failed: You have to enter plug number or machine identification", stop_after_error)

	docs = {}
	docs["shortdesc"] = "Fence agent for multipath persistent reservation"
	docs["longdesc"] = "fence_mpath is an I/O Fencing agent that uses SCSI-3 \
persistent reservations to control access multipath devices. Underlying \
devices must support SCSI-3 persistent reservations (SPC-3 or greater) as \
well as the \"preempt-and-abort\" subcommand.\nThe fence_mpath agent works by \
having a unique key for each node that has to be set in /etc/multipath.conf. \
Once registered, a single node will become the reservation holder \
by creating a \"write exclusive, registrants only\" reservation on the \
device(s). The result is that only registered nodes may write to the \
device(s). When a node failure occurs, the fence_mpath agent will remove the \
key belonging to the failed node from the device(s). The failed node will no \
longer be able to write to the device(s). A manual reboot is required.\
\n.P\n\
When used as a watchdog device you can define e.g. retry=1, retry-sleep=2 and \
verbose=yes parameters in /etc/sysconfig/stonith if you have issues with it \
failing."
	docs["vendorurl"] = "https://www.sourceware.org/dm/"
	show_docs(options, docs)

	run_delay(options)

	# Input control BEGIN
	if options["--action"] == "validate-all":
		sys.exit(0)

	if not ("--devices" in options and options["--devices"]):
		fail_usage("Failed: No devices found")

	options["devices"] = [d for d in re.split(r"\s*,\s*|\s+", options["--devices"].strip()) if d]
	options["--plug"] = re.sub(r"^0x0*|^0+", "", options.get("--plug", ""))
	# Input control END

	result = fence_action(None, options, set_status, get_status)
	sys.exit(result)

if __name__ == "__main__":
	main()
