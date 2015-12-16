#!/usr/bin/python -tt

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

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

STORE_PATH = "/var/run/cluster/fence_scsi"


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

			register_dev(options, dev)
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
	if bool(run_cmd(options, options["--sg_persist-path"] + " -V")["err"]):
		logging.error("Unable to run " + options["--sg_persist-path"])
		return 1
	elif bool(run_cmd(options, options["--sg_turs-path"] + " -V")["err"]):
		logging.error("Unable to run " + options["--sg_turs-path"])
		return 1
	elif ("--devices" not in options and 
			bool(run_cmd(options,	options["--vgs-path"] + " --version")["err"])):
		logging.error("Unable to run " + options["--vgs-path"])
		return 1

	# Keys have to be present in order to fence/unfence
	get_key()
	dev_read()

	return 0


#run command, returns dict, ret["err"] = exit code; ret["out"] = output
def run_cmd(options, cmd):
	ret = {}
	(ret["err"], ret["out"], _) = run_command(options, cmd)
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
	reset_dev(options,dev)
	cmd = options["--sg_persist-path"] + " -n -o -A -T 5 -K " + host + " -S " + options["--key"] + " -d " + dev
	return not bool(run_cmd(options, cmd)["err"])


def reset_dev(options, dev):
	return run_cmd(options, options["--sg_turs-path"] + " " + dev)["err"]


def register_dev(options, dev):
	dev = os.path.realpath(dev)
	if re.search(r"^dm", dev[5:]):
		for slave in get_mpath_slaves(dev):
			register_dev(options, slave)
		return True
	reset_dev(options, dev)
	cmd = options["--sg_persist-path"] + " -n -o -I -S " + options["--key"] + " -d " + dev
	cmd += " -Z" if "--aptpl" in options else ""
	#cmd return code != 0 but registration can be successful
	return not bool(run_cmd(options, cmd)["err"])


def reserve_dev(options, dev):
	reset_dev(options,dev)
	cmd = options["--sg_persist-path"] + " -n -o -R -T 5 -K " + options["--key"] + " -d " + dev
	return not bool(run_cmd(options, cmd)["err"])


def get_reservation_key(options, dev):
	reset_dev(options,dev)
	cmd = options["--sg_persist-path"] + " -n -i -r -d " + dev
	out = run_cmd(options, cmd)
	if out["err"]:
		fail_usage("Cannot get reservation key")
	match = re.search(r"\s+key=0x(\S+)\s+", out["out"], re.IGNORECASE)
	return match.group(1) if match else None


def get_registration_keys(options, dev):
	reset_dev(options,dev)
	keys = []
	cmd = options["--sg_persist-path"] + " -n -i -k -d " + dev
	out = run_cmd(options, cmd)
	if out["err"]:
		fail_usage("Cannot get registration keys")
	for line in out["out"].split("\n"):
		match = re.search(r"\s+0x(\S+)\s*", line)
		if match:
			keys.append(match.group(1))
	return keys


def get_cluster_id(options):
	cmd = options["--corosync-cmap-path"] + " totem.cluster_name"

	match = re.search(r"\(str\) = (\S+)\n", run_cmd(options, cmd)["out"])
	return hashlib.md5(match.group(1)).hexdigest() if match else fail_usage("Failed: cannot get cluster name")


def get_node_id(options):
	cmd = options["--corosync-cmap-path"] + " nodelist."

	match = re.search(r".(\d).ring._addr \(str\) = " + options["--nodename"] + "\n", run_cmd(options, cmd)["out"])
	return match.group(1) if match else fail_usage("Failed: unable to parse output of corosync-cmapctl or node does not exist")


def generate_key(options):
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
		if fail:
			fail_usage("Failed: Cannot open file \""+ file_path + "\"")
		else:
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
	out = f.read()
	if not re.search(r"^" + dev + "\s+", out):
		f.write(dev + "\n")
	f.close()


def dev_read(fail=True):
	file_path = STORE_PATH + ".dev"
	try:
		f = open(file_path, "r")
	except IOError:
		if fail:
			fail_usage("Failed: Cannot open file \"" + file_path + "\"")
		else:
			return None
	# get not empty lines from file
	devs = [line.strip() for line in f if line.strip()]
	f.close()
	return devs


def dev_delete(options):
	file_path = options["store_path"] + ".dev"
	os.remove(file_path) if os.path.exists(file_path) else None


def get_clvm_devices(options):
	devs = []
	cmd = options["--vgs-path"] + " " +\
	"--noheadings " +\
	"--separator : " +\
	"--sort pv_uuid " +\
	"--options vg_attr,pv_name "+\
	"--config 'global { locking_type = 0 } devices { preferred_names = [ \"^/dev/dm\" ] }'"
	out = run_cmd(options, cmd)
	if out["err"]:
		fail_usage("Failed: Cannot get clvm devices")
	for line in out["out"].split("\n"):
		if 'c' in line.split(":")[0]:
			devs.append(line.split(":")[1])
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
be comma-separated list of raw device (eg. /dev/sdc) or device-mapper multipath \
devices (eg. /dev/dm-3). Each device must support SCSI-3 persistent reservations.",
		"order": 1
	}
	all_opt["nodename"] = {
		"getopt" : "n:",
		"longopt" : "nodename",
		"help" : "-n, --nodename=[nodename]      Name of the node to be fenced",
		"required" : "0",
		"shortdesc" : "Name of the node to be fenced. The node name is used to \
generate the key value used for the current operation. This option will be \
ignored when used with the -k option.",
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
	all_opt["logfile"] = {
		"getopt" : ":",
		"longopt" : "logfile",
		"help" : "-f, --logfile                  Log output (stdout and stderr) to file",
		"required" : "0",
		"shortdesc" : "Log output (stdout and stderr) to file",
		"order": 5
	}
	all_opt["corosync-cmap_path"] = {
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


def scsi_check_get_verbose():
	try:
		f = open("/etc/sysconfig/watchdog", "r")
	except IOError:
		return False
	match = re.search(r"^\s*verbose=yes", "".join(f.readlines()), re.MULTILINE)
	f.close()
	return bool(match)


def scsi_check(hardreboot=False):
	if len(sys.argv) >= 3 and sys.argv[1] == "repair":
		return int(sys.argv[2])
	options = {}
	options["--sg_turs-path"] = "@SG_TURS_PATH@"
	options["--sg_persist-path"] = "@SG_PERSIST_PATH@"
	options["--power-timeout"] = "5"
	if scsi_check_get_verbose():
		logging.getLogger().setLevel(logging.DEBUG)
	devs = dev_read(fail=False)
	if not devs:
		logging.error("No devices found")
		return 0
	key = get_key(fail=False)
	if not key:
		logging.error("Key not found")
		return 0
	for dev in devs:
		if key in get_registration_keys(options, dev):
			logging.debug("key " + key + " registered with device " + dev)
			return 0
		else:
			logging.debug("key " + key + " not registered with device " + dev)
	logging.debug("key " + key + " registered with any devices")

	if hardreboot == True:
		libc = ctypes.cdll['libc.so.6']
		libc.reboot(0x1234567)
	return 2


def main():

	atexit.register(atexit_handler)

	device_opt = ["no_login", "no_password", "devices", "nodename", "key",\
	"aptpl", "fabric_fencing", "on_target", "corosync-cmap_path",\
	"sg_persist_path", "sg_turs_path", "logfile", "vgs_path", "force_on"]

	define_new_opts()

	all_opt["delay"]["getopt"] = "H:"

	#fence_scsi_check
	if os.path.basename(sys.argv[0]) == "fence_scsi_check":
		sys.exit(scsi_check())
	elif os.path.basename(sys.argv[0]) == "fence_scsi_check_hardreboot":
		sys.exit(scsi_check(True))

	options = check_input(device_opt, process_input(device_opt), other_conditions=True)

	docs = {}
	docs["shortdesc"] = "Fence agent for SCSI persistentl reservation"
	docs["longdesc"] = "fence_scsi is an I/O fencing agent that uses SCSI-3 \
persistent reservations to control access to shared storage devices. These \
devices must support SCSI-3 persistent reservations (SPC-3 or greater) as \
well as the \"preempt-and-abort\" subcommand.\nThe fence_scsi agent works by \
having each node in the cluster register a unique key with the SCSI \
devive(s). Once registered, a single node will become the reservation holder \
by creating a \"write exclusive, registrants only\" reservation on the \
device(s). The result is that only registered nodes may write to the \
device(s). When a node failure occurs, the fence_scsi agent will remove the \
key belonging to the failed node from the device(s). The failed node will no \
longer be able to write to the device(s). A manual reboot is required."
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

	if not (("--nodename" in options and options["--nodename"])\
	or ("--key" in options and options["--key"])):
		fail_usage("Failed: nodename or key is required", stop_after_error)

	if not ("--key" in options and options["--key"]):
		options["--key"] = generate_key(options)

	if options["--key"] == "0" or not options["--key"]:
		fail_usage("Failed: key cannot be 0", stop_after_error)

	if options["--action"] == "validate-all":
		sys.exit(0)

	options["--key"] = options["--key"].lstrip('0')

	if not ("--devices" in options and options["--devices"].split(",")):
		options["devices"] = get_clvm_devices(options)
	else:
		options["devices"] = options["--devices"].split(",")

	if not options["devices"]:
		fail_usage("Failed: No devices found")
	# Input control END

	result = fence_action(None, options, set_status, get_status)
	sys.exit(result)

if __name__ == "__main__":
	main()
