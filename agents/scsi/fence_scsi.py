#!@PYTHON@ -tt

import sys
import stat
import re
import os
import time
import logging
import atexit
import hashlib
import ctypes
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import fail_usage, run_command, atexit_handler, check_input, process_input, show_docs, fence_action, all_opt
from fencing import run_delay

STORE_PATH = "@STORE_PATH@"


def get_status(conn, options):
	del conn
	status = "off"
	for dev in options["devices"]:
		is_block_device(dev)
		reset_dev(options, dev)
		if options["--key"] in get_registration_keys(options, dev):
			status = "on"
		else:
			logging.debug("No registration for key "\
				+ options["--key"] + " on device " + dev + "\n")
			if options["--action"] == "on":
				status = "off"
				break
	return status


def set_status(conn, options):
	del conn
	count = 0
	if options["--action"] == "on":
		set_key(options)
		for dev in options["devices"]:
			is_block_device(dev)

			register_dev(options, dev, options["--key"])
			if options["--key"] not in get_registration_keys(options, dev):
				count += 1
				logging.debug("Failed to register key "\
					+ options["--key"] + "on device " + dev + "\n")
				continue
			dev_write(dev, options)

			if get_reservation_key(options, dev) is None \
			and not reserve_dev(options, dev) \
			and get_reservation_key(options, dev) is None:
				count += 1
				logging.debug("Failed to create reservation (key="\
					+ options["--key"] + ", device=" + dev + ")\n")

	else:
		host_key = get_key()
		if host_key == options["--key"].lower():
			fail_usage("Failed: keys cannot be same. You can not fence yourself.")
		for dev in options["devices"]:
			is_block_device(dev)
			register_dev(options, dev, host_key)
			if options["--key"] in get_registration_keys(options, dev):
				preempt_abort(options, host_key, dev)

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


# check if host is ready to execute actions
def do_action_monitor(options):
	# Check if required binaries are installed
	if bool(run_cmd(options, options["--sg_persist-path"] + " -V")["rc"]):
		logging.error("Unable to run " + options["--sg_persist-path"])
		return 1
	elif bool(run_cmd(options, options["--sg_turs-path"] + " -V")["rc"]):
		logging.error("Unable to run " + options["--sg_turs-path"])
		return 1
	elif ("--devices" not in options and 
			bool(run_cmd(options, options["--vgs-path"] + " --version")["rc"])):
		logging.error("Unable to run " + options["--vgs-path"])
		return 1

	# Keys have to be present in order to fence/unfence
	get_key()
	dev_read()

	return 0


# run command, returns dict, ret["rc"] = exit code; ret["out"] = output;
# ret["err"] = error
def run_cmd(options, cmd):
	ret = {}
	(ret["rc"], ret["out"], ret["err"]) = run_command(options, cmd)
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
	reset_dev(options,dev)
	cmd = options["--sg_persist-path"] + " -n -o -A -T 5 -K " + host + " -S " + options["--key"] + " -d " + dev
	return not bool(run_cmd(options, cmd)["rc"])


def reset_dev(options, dev):
	return run_cmd(options, options["--sg_turs-path"] + " " + dev)["rc"]


def register_dev(options, dev, key, do_preempt=True):
	dev = os.path.realpath(dev)
	if re.search(r"^dm", dev[5:]):
		devices = get_mpath_slaves(dev)
		register_dev(options, devices[0], key)
		for device in devices[1:]:
			register_dev(options, device, key, False)
		return True

	# Check if any registration exists for the key already. We track this in
	# order to decide whether the existing registration needs to be cleared.
	# This is needed since the previous registration could be for a
	# different I_T nexus (different ISID).
	registration_key_exists = False
	if key in get_registration_keys(options, dev):
		logging.debug("Registration key exists for device " + dev)
		registration_key_exists = True
	if not register_helper(options, dev, key):
		return False

	if registration_key_exists:
		# If key matches, make sure it matches with the connection that
		# exists right now. To do this, we can issue a preempt with same key
		# which should replace the old invalid entries from the target.
		if do_preempt and not preempt(options, key, dev, key):
			return False

		# If there was no reservation, we need to issue another registration
		# since the previous preempt would clear registration made above.
		if get_reservation_key(options, dev, False) != key:
			return register_helper(options, dev, key)
	return True

# helper function to preempt host with 'key' using 'host_key' without aborting tasks
def preempt(options, host_key, dev, key):
	reset_dev(options,dev)
	cmd = options["--sg_persist-path"] + " -n -o -P -T 5 -K " + host_key + " -S " + key + " -d " + dev
	return not bool(run_cmd(options, cmd)["rc"])

# helper function to send the register command
def register_helper(options, dev, key):
	reset_dev(options, dev)
	cmd = options["--sg_persist-path"] + " -n -o -I -S " + key + " -d " + dev
	cmd += " -Z" if "--aptpl" in options else ""
	return not bool(run_cmd(options, cmd)["rc"])


def reserve_dev(options, dev):
	reset_dev(options,dev)
	cmd = options["--sg_persist-path"] + " -n -o -R -T 5 -K " + options["--key"] + " -d " + dev
	return not bool(run_cmd(options, cmd)["rc"])


def get_reservation_key(options, dev, fail=True):
	reset_dev(options,dev)
	opts = ""
	if "--readonly" in options:
		opts = "-y "
	cmd = options["--sg_persist-path"] + " -n -i " + opts + "-r -d " + dev
	out = run_cmd(options, cmd)
	if out["rc"] and fail:
		fail_usage('Cannot get reservation key on device "' + dev
                        + '": ' + out["err"])
	match = re.search(r"\s+key=0x(\S+)\s+", out["out"], re.IGNORECASE)
	return match.group(1) if match else None


def get_registration_keys(options, dev, fail=True):
	reset_dev(options,dev)
	keys = []
	opts = ""
	if "--readonly" in options:
		opts = "-y "
	cmd = options["--sg_persist-path"] + " -n -i " + opts + "-k -d " + dev
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


def get_cluster_id(options):
	cmd = options["--corosync-cmap-path"] + " totem.cluster_name"

	match = re.search(r"\(str\) = (\S+)\n", run_cmd(options, cmd)["out"])

	if not match:
		fail_usage("Failed: cannot get cluster name")

	try:
		return hashlib.md5(match.group(1).encode('ascii')).hexdigest()
	except ValueError:
		# FIPS requires usedforsecurity=False and might not be
		# available on all distros: https://bugs.python.org/issue9216
		return hashlib.md5(match.group(1).encode('ascii'), usedforsecurity=False).hexdigest()


def get_node_id(options):
	cmd = options["--corosync-cmap-path"] + " nodelist"
	out = run_cmd(options, cmd)["out"]

	match = re.search(r".(\d+).name \(str\) = " + options["--plug"] + r"\n", out)

	# try old format before failing
	if not match:
		match = re.search(r".(\d+).ring._addr \(str\) = " + options["--plug"] + r"\n", out)

	return match.group(1) if match else fail_usage("Failed: unable to parse output of corosync-cmapctl or node does not exist")

def get_node_hash(options):
	try:
		return hashlib.md5(options["--plug"].encode('ascii')).hexdigest()
	except ValueError:
		# FIPS requires usedforsecurity=False and might not be
		# available on all distros: https://bugs.python.org/issue9216
		return hashlib.md5(options["--plug"].encode('ascii'), usedforsecurity=False).hexdigest()


def generate_key(options):
	if options["--key-value"] == "hash":
		return "%.4s%.4s" % (get_cluster_id(options), get_node_hash(options))
	else:
		return "%.4s%.4d" % (get_cluster_id(options), int(get_node_id(options)))


# save node key to file
def set_key(options):
	file_path = options["store_path"] + ".key"
	if not os.path.isdir(os.path.dirname(options["store_path"])):
		os.makedirs(os.path.dirname(options["store_path"]))
	try:
		f = open(file_path, "w")
	except IOError:
		fail_usage("Failed: Cannot open file \""+ file_path + "\"")
	f.write(options["--key"].lower() + "\n")
	f.close()


# read node key from file
def get_key(fail=True):
	file_path = STORE_PATH + ".key"
	try:
		f = open(file_path, "r")
	except IOError:
		fail_usage("Failed: Cannot open file \""+ file_path + "\"", fail)
		if not fail:
			return None
	return f.readline().strip().lower()


def dev_write(dev, options):
	file_path = options["store_path"] + ".dev"
	if not os.path.isdir(os.path.dirname(options["store_path"])):
		os.makedirs(os.path.dirname(options["store_path"]))
	try:
		f = open(file_path, "a+")
	except IOError:
		fail_usage("Failed: Cannot open file \""+ file_path + "\"")
	f.seek(0)
	out = f.read()
	if not re.search(r"^" + dev + r"\s+", out, flags=re.MULTILINE):
		f.write(dev + "\n")
	f.close()


def dev_read(fail=True, opt=None):
	file_path = STORE_PATH + ".dev"
	try:
		f = open(file_path, "r")
	except IOError:
		if "--suppress-errors" not in opt:
			fail_usage("Failed: Cannot open file \"" + file_path + "\"", fail)
		if not fail:
			return None
	# get not empty lines from file
	devs = [line.strip() for line in f if line.strip()]
	f.close()
	return devs


def get_shared_devices(options):
	devs = []
	cmd = options["--vgs-path"] + " " +\
	"--noheadings " +\
	"--separator : " +\
	"--sort pv_uuid " +\
	"--options vg_attr,pv_name "+\
	"--config 'global { locking_type = 0 } devices { preferred_names = [ \"^/dev/dm\" ] }'"
	out = run_cmd(options, cmd)
	if out["rc"]:
		fail_usage("Failed: Cannot get shared devices")
	for line in out["out"].splitlines():
		vg_attr, pv_name = line.strip().split(":")
		if vg_attr[5] in "cs":
			devs.append(pv_name)
	return devs


def get_mpath_slaves(dev):
	if dev[:5] == "/dev/":
		dev = dev[5:]
	slaves = [i for i in os.listdir("/sys/block/" + dev + "/slaves/") if i[:1] != "."]
	if slaves[0][:2] == "dm":
		slaves = get_mpath_slaves(slaves[0])
	else:
		slaves = ["/dev/" + x for x in slaves]
	return slaves


def define_new_opts():
	all_opt["devices"] = {
		"getopt" : "d:",
		"longopt" : "devices",
		"help" : "-d, --devices=[devices]        List of devices to use for current operation",
		"required" : "0",
		"shortdesc" : "List of devices to use for current operation. Devices can \
be comma or space separated list of raw devices (eg. /dev/sdc). Each device must support SCSI-3 \
persistent reservations. Optional if cluster is configured with clvm or lvmlockd.",
		"order": 1
	}
	all_opt["nodename"] = {
		"getopt" : ":",
		"longopt" : "nodename",
		"help" : "",
		"required" : "0",
		"shortdesc" : "",
		"order": 1
	}
	all_opt["key"] = {
		"getopt" : "k:",
		"longopt" : "key",
		"help" : "-k, --key=[key]                Key to use for the current operation",
		"required" : "0",
		"shortdesc" : "Key to use for the current operation. This key should be \
unique to a node. For the \"on\" action, the key specifies the key use to \
register the local node. For the \"off\" action, this key specifies the key to \
be removed from the device(s).",
		"order": 1
	}
	all_opt["aptpl"] = {
		"getopt" : "a",
		"longopt" : "aptpl",
		"help" : "-a, --aptpl                    Use the APTPL flag for registrations",
		"required" : "0",
		"shortdesc" : "Use the APTPL flag for registrations. This option is only used for the 'on' action.",
		"order": 1
	}
	all_opt["readonly"] = {
		"getopt" : "",
		"longopt" : "readonly",
		"help" : "--readonly                     Open DEVICE read-only. May be useful with PRIN commands if there are unwanted side effects with the default read-write open.",
		"required" : "0",
		"shortdesc" : "Open DEVICE read-only.",
		"order": 4
	}
	all_opt["suppress-errors"] = {
		"getopt" : "",
		"longopt" : "suppress-errors",
		"help" : "--suppress-errors              Suppress error log. Suppresses error logging when run from the watchdog service before pacemaker starts.",
		"required" : "0",
		"shortdesc" : "Error log suppression.",
		"order": 5
	}
	all_opt["logfile"] = {
		"getopt" : ":",
		"longopt" : "logfile",
		"help" : "-f, --logfile                  Log output (stdout and stderr) to file",
		"required" : "0",
		"shortdesc" : "Log output (stdout and stderr) to file",
		"order": 6
	}
	all_opt["corosync_cmap_path"] = {
		"getopt" : ":",
		"longopt" : "corosync-cmap-path",
		"help" : "--corosync-cmap-path=[path]    Path to corosync-cmapctl binary",
		"required" : "0",
		"shortdesc" : "Path to corosync-cmapctl binary",
		"default" : "@COROSYNC_CMAPCTL_PATH@",
		"order": 300
	}
	all_opt["sg_persist_path"] = {
		"getopt" : ":",
		"longopt" : "sg_persist-path",
		"help" : "--sg_persist-path=[path]       Path to sg_persist binary",
		"required" : "0",
		"shortdesc" : "Path to sg_persist binary",
		"default" : "@SG_PERSIST_PATH@",
		"order": 300
	}
	all_opt["sg_turs_path"] = {
		"getopt" : ":",
		"longopt" : "sg_turs-path",
		"help" : "--sg_turs-path=[path]          Path to sg_turs binary",
		"required" : "0",
		"shortdesc" : "Path to sg_turs binary",
		"default" : "@SG_TURS_PATH@",
		"order": 300
	}
	all_opt["vgs_path"] = {
		"getopt" : ":",
		"longopt" : "vgs-path",
		"help" : "--vgs-path=[path]              Path to vgs binary",
		"required" : "0",
		"shortdesc" : "Path to vgs binary",
		"default" : "@VGS_PATH@",
		"order": 300
	}
	all_opt["key_value"] = {
		"getopt" : ":",
		"longopt" : "key-value",
		"help" : "--key-value=<id|hash>          SCSI key node generation method",
		"required" : "0",
		"shortdesc" : "Method used to generate the SCSI key. \"id\" (default) \
uses the positional ID from \"corosync-cmactl nodelist\" output which can get inconsistent \
when nodes are removed from cluster without full cluster restart. \"hash\" uses part of hash \
made out of node names which is not affected over time but there is theoretical chance that \
hashes can collide as size of SCSI key is quite limited.",
		"default" : "id",
		"order": 300
	}


def scsi_check_get_options(options):
	try:
		f = open("/etc/sysconfig/stonith", "r")
	except IOError:
		return options

	match = re.findall(r"^\s*(\S*)\s*=\s*(\S*)\s*", "".join(f.readlines()), re.MULTILINE)

	for m in match:
		options[m[0].lower()] = m[1].lower()

	f.close()

	return options


def scsi_check(hardreboot=False):
	if len(sys.argv) >= 3 and sys.argv[1] == "repair":
		return int(sys.argv[2])
	options = {}
	options["--sg_turs-path"] = "@SG_TURS_PATH@"
	options["--sg_persist-path"] = "@SG_PERSIST_PATH@"
	options["--power-timeout"] = "5"
	options["retry"] = "0"
	options["retry-sleep"] = "1"
	options = scsi_check_get_options(options)
	if "verbose" in options and options["verbose"] == "yes":
		logging.getLogger().setLevel(logging.DEBUG)
	devs = dev_read(fail=False,opt=options)
	if not devs:
		if "--suppress-errors" not in options:
			logging.error("No devices found")
		return 0
	key = get_key(fail=False)
	if not key:
		logging.error("Key not found")
		return 0
	for dev in devs:
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


def main():

	atexit.register(atexit_handler)

	device_opt = ["no_login", "no_password", "devices", "nodename", "port",\
	"no_port", "key", "aptpl", "fabric_fencing", "on_target", "corosync_cmap_path",\
	"sg_persist_path", "sg_turs_path", "readonly", "suppress-errors", "logfile", "vgs_path",\
	"force_on", "key_value"]

	define_new_opts()

	all_opt["delay"]["getopt"] = "H:"

	all_opt["port"]["help"] = "-n, --plug=[nodename]          Name of the node to be fenced"
	all_opt["port"]["shortdesc"] = "Name of the node to be fenced. The node name is used to \
generate the key value used for the current operation. This option will be \
ignored when used with the -k option."

	#fence_scsi_check
	if os.path.basename(sys.argv[0]) == "fence_scsi_check":
		sys.exit(scsi_check())
	elif os.path.basename(sys.argv[0]) == "fence_scsi_check_hardreboot":
		sys.exit(scsi_check(True))

	options = check_input(device_opt, process_input(device_opt), other_conditions=True)

	# hack to remove list/list-status actions which are not supported
	options["device_opt"] = [ o for o in options["device_opt"] if o != "separator" ]

	docs = {}
	docs["shortdesc"] = "Fence agent for SCSI persistent reservation"
	docs["longdesc"] = "fence_scsi is an I/O Fencing agent that uses SCSI-3 \
persistent reservations to control access to shared storage devices. These \
devices must support SCSI-3 persistent reservations (SPC-3 or greater) as \
well as the \"preempt-and-abort\" subcommand.\nThe fence_scsi agent works by \
having each node in the cluster register a unique key with the SCSI \
device(s). Reservation key is generated from \"node id\" (default) or from \
\"node name hash\" (RECOMMENDED) by adjusting \"key_value\" option. \
Using hash is recommended to prevent issues when removing nodes \
from cluster without full cluster restart. \
Once registered, a single node will become the reservation holder \
by creating a \"write exclusive, registrants only\" reservation on the \
device(s). The result is that only registered nodes may write to the \
device(s). When a node failure occurs, the fence_scsi agent will remove the \
key belonging to the failed node from the device(s). The failed node will no \
longer be able to write to the device(s). A manual reboot is required.\
\n.P\n\
When used as a watchdog device you can define e.g. retry=1, retry-sleep=2 and \
verbose=yes parameters in /etc/sysconfig/stonith if you have issues with it \
failing."
	docs["vendorurl"] = ""
	show_docs(options, docs)

	run_delay(options)

	# backward compatibility layer BEGIN
	if "--logfile" in options:
		try:
			logfile = open(options["--logfile"], 'w')
			sys.stderr = logfile
			sys.stdout = logfile
		except IOError:
			fail_usage("Failed: Unable to create file " + options["--logfile"])
	# backward compatibility layer END

	options["store_path"] = STORE_PATH

	# Input control BEGIN
	stop_after_error = False if options["--action"] == "validate-all" else True

	if options["--action"] == "monitor":
		sys.exit(do_action_monitor(options))

	# workaround to avoid regressions
	if "--nodename" in options and options["--nodename"]:
		options["--plug"] = options["--nodename"]
		del options["--nodename"]

	if not (("--plug" in options and options["--plug"])\
	or ("--key" in options and options["--key"])):
		fail_usage("Failed: nodename or key is required", stop_after_error)

	if options["--action"] != "validate-all":
		if not ("--key" in options and options["--key"]):
			options["--key"] = generate_key(options)

		if options["--key"] == "0" or not options["--key"]:
			fail_usage("Failed: key cannot be 0", stop_after_error)

	if "--key-value" in options\
	and (options["--key-value"] != "id" and options["--key-value"] != "hash"):
		fail_usage("Failed: key-value has to be 'id' or 'hash'", stop_after_error)

	if options["--action"] == "validate-all":
		sys.exit(0)

	options["--key"] = options["--key"].lstrip('0')

	if not ("--devices" in options and [d for d in re.split(r"\s*,\s*|\s+", options["--devices"].strip()) if d]):
		options["devices"] = get_shared_devices(options)
	else:
		options["devices"] = [d for d in re.split(r"\s*,\s*|\s+", options["--devices"].strip()) if d]

	if not options["devices"]:
		fail_usage("Failed: No devices found")
	# Input control END

	result = fence_action(None, options, set_status, get_status)
	sys.exit(result)

if __name__ == "__main__":
	main()
