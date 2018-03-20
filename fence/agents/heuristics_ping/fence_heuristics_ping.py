#!@PYTHON@ -tt

# The Following Agent Has Been Tested On:
#
# RHEL 7.4
#

import io
import re
import subprocess
import shlex
import sys, stat
import logging
import os
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import fail_usage, run_command, fence_action, all_opt
from fencing import atexit_handler, check_input, process_input, show_docs
from fencing import run_delay

def ping_test(con, options):
	# Send pings to the targets

	if options["--action"] == "on":
		# we want unfencing to always succeed
		return True

	if not "--ping-targets" in options or options["--ping-targets"] == "":
		# "off" was requested so fake "on" to provoke failure
		logging.error("ping target required")
		return False

	timeout = int(options["--ping-timeout"])
	count = int(options["--ping-count"])
	interval = int(options["--ping-interval"])
	good_required = int(options["--ping-good-count"])
	maxfail = int(options["--ping-maxfail"])
	targets = options["--ping-targets"].split(",")
	exitcode = True
	p = {}
	failcount = 0
	# search string for parsing the results of the ping-executable
	packet_count = re.compile(r".*transmitted, ([0-9]*)( packets)? received.*")

	# start a ping-process per target
	for target in targets:
		ping_path = '@PING_CMD@'
		target_mangled = target
		if target.startswith('inet6:'):
			if '@PING6_CMD@' == '':
				p[target] = None
				continue
			ping_path = '@PING6_CMD@'
			target_mangled = target.split(':',2)[1]
		elif target.startswith('inet:'):
			ping_path = '@PING4_CMD@'
			target_mangled = target.split(':',2)[1]

		ping_cmd = "%s -n -q -W %d -c %d -i %d %s" % (
			ping_path, timeout, count, interval, target_mangled)
		logging.info("Running command: %s", ping_cmd)
		try:
			p[target] = subprocess.Popen(shlex.split(ping_cmd),
				stdout=subprocess.PIPE);
		except OSError:
			p[target] = None

	# collect the results of the ping-processes
	for target in targets:
		good = 0
		if p[target] != None:
			p[target].wait()
			if p[target].returncode == 0:
				for line in p[target].stdout:
					searchres = packet_count.search(line.decode())
					if searchres:
						good = int(searchres.group(1))
						break
				if good >= good_required:
					logging.info("ping target %s received %d of %d" \
						% (target, good, count))
					continue
			failcount += 1
			logging.info("ping target %s received %d of %d and thus failed"
				% (target, good, count))
		else:
			failcount += 1
			logging.error("ping target %s failed on OS level" % target)

	if failcount > maxfail:
		exitcode = False

	return exitcode


def define_new_opts():
	all_opt["ping_count"] = {
		"getopt" : ":",
		"longopt" : "ping-count",
		"required" : "0",
		"help" : "--ping-count=[number]          Number of ping-probes to send",
		"shortdesc" : "The number of ping-probes that is being sent per target",
		"default" : "10",
		"order" : 1
		}

	all_opt["ping_good_count"] = {
		"getopt" : ":",
		"longopt" : "ping-good-count",
		"required" : "0",
		"help" : "--ping-good-count=[number]     Number of positive ping-probes required",
		"shortdesc" : "The number of positive ping-probes required to account a target as available",
		"default" : "8",
		"order" : 1
		}

	all_opt["ping_interval"] = {
		"getopt" : ":",
		"longopt" : "ping-interval",
		"required" : "0",
		"help" : "--ping-interval=[seconds]      Seconds between ping-probes",
		"shortdesc" : "The interval in seconds between ping-probes",
		"default" : "1",
		"order" : 1
		}

	all_opt["ping_timeout"] = {
		"getopt" : ":",
		"longopt" : "ping-timeout",
		"required" : "0",
		"help" : "--ping-timeout=[seconds]       Timeout for individual ping-probes",
		"shortdesc" : "The timeout in seconds till an individual ping-probe is accounted as lost",
		"default" : "2",
		"order" : 1
		}

	all_opt["ping_maxfail"] = {
		"getopt" : ":",
		"longopt" : "ping-maxfail",
		"required" : "0",
		"help" : "--ping-maxfail=[number]        Number of failed ping-targets allowed",
		"shortdesc" : "The number of failed ping-targets to still account as overall success",
		"default" : "0",
		"order" : 1
		}

	all_opt["ping_targets"] = {
		"getopt" : ":",
		"longopt" : "ping-targets",
		"required" : "1",
		"help" : "--ping-targets=tgt1,[inet6:]tgt2  Comma separated list of ping-targets",
		"shortdesc" : "A comma separated list of ping-targets (optionally prepended by 'inet:' or 'inet6:') to be probed",
		"default" : "",
		"order" : 1
		}


def main():
	device_opt = ["no_status", "no_password", "ping_count", "ping_good_count",
		"ping_interval", "ping_timeout", "ping_maxfail", "ping_targets", "method"]
	define_new_opts()
	atexit.register(atexit_handler)

	all_opt["method"]["default"] = "cycle"
	all_opt["method"]["help"] = "-m, --method=[method]          Method to fence (cycle|onoff) (Default: cycle)"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for ping-heuristic based fencing"
	docs["longdesc"] = "fence_heuristics_ping uses ping-heuristics to control execution of another fence agent on the same fencing level.\
\n.P\n\
This is not a fence agent by itself! \
Its only purpose is to enable/disable another fence agent that lives on the same fencing level but after fence_heuristics_ping."
	docs["vendorurl"] = ""
	show_docs(options, docs)

	# move ping-test to the end of the time-window set via --delay
	# as to give the network time to settle after the incident that has
	# caused fencing and have the results as current as possible
	max_pingcheck = (int(options["--ping-count"]) - 1) * \
		int(options["--ping-interval"]) + int(options["--ping-timeout"])
	run_delay(options, reserve=max_pingcheck)

	result = fence_action(\
				None, \
				options, \
				None, \
				None, \
				reboot_cycle_fn = ping_test,
				sync_set_power_fn = ping_test)

	# execute the remaining delay
	run_delay(options, result=result)
	sys.exit(result)

if __name__ == "__main__":
	main()
