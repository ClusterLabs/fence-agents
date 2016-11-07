#!/usr/bin/env python
import os
import time
from datetime import datetime
import sys
import subprocess
import re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import run_delay
import logging


#BEGIN_VERSION_GENERATION
RELEASE_VERSION="Powerman Fencing Agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION


#### important!!! #######
class PowerMan:
	"""Python wrapper for calling powerman commands

	This class makes calls to a powerman deamon for a cluster of computers.
	The make-up of such a call looks something like:
		$ pm -h elssd1:10101 <option> <node>
	where option is something like --off, --on, --cycle and where node is 
	elssd8, or whatever values are setup in powerman.conf (***this is key, 
	because otherwise this code will not work!)
	"""
	program_name = "powerman"

	def __init__(self, server_name, port="10101"):
		"""
		Args:
			server_name: (string) host or ip of powerman server
			port: (str) port number that the powerman server is listening on
		"""
		self.server_name = server_name
		self.port = port
		self.server_and_port = server_name + ":" + str(port)
		# this is a list of the command and its options. For example:
		# ['powerman', '--server-host', 'elssd1:10101']
		self.base_cmd = [
			self.program_name, 
			"--server-host", 
			self.server_and_port
		]

	def _run(self, cmd, only_first_line):
		# Args:
		#   cmd: (list) commands and arguments to pass to the program_name

		# add the 2 command lists together to get whole command to run
		run_this = self.base_cmd + cmd 
		try:
			popen = subprocess.Popen(run_this, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
			out = popen.communicate()
		except OSError as e:
			logging.error("_run command error: %s\n", e)
			sys.exit(1)
		if only_first_line == True:
			result_line = out[0].decode().strip()
			return (result_line, popen.returncode)
		else:
			result_list = []
			for line in out:
				result_list.append(line)
			return (result_list, popen.returncode)

	def is_running(self):
		"""simple query to see if powerman server is responding. Returns boolean"""
		cmd = ["-q"] # just check if we get a response from the server
		result, ret_code = self._run(cmd, True)
		if ret_code != 0:
			return False
		return True

	def on(self, host):
		logging.debug("PowerMan on: %s\n", host)
		cmd = ["--on", host]
		try:
			result, ret_code = self._run(cmd, True)
		except OSError as e:
			logging.error("PowerMan Error: The command '--on' failed: %s\n", e)
			return -1
		except ValueError as e:
			logging.error("PowerMan Error: Popen: invalid arguments: %s\n", e)
			return -1
		logging.debug("pm.on result: %s ret_code: %s\n", result, ret_code)

		## For some devices, the "on" or "off" command can fail silently,
		## but for query powerman keeps trying until it gets a valid answer;
		## so we must check after trying to power on/off a device.
		## Powerman seems to report the old state if asked too quickly, wait a second.

		time.sleep(1)
		queryret = self.query(host)

		if (ret_code == 0 and queryret == "off") or (ret_code < 0 and queryret == "on"):
			logging.warning("command '%s' returned (%s) but query reported (%s) afterwards\n", cmd, result, queryret)

		if queryret == "on":
			return 0
		else:
			return -1

	def off(self, host):
		logging.debug("PowerMan off: %s\n", host)
		cmd = ["--off", host]
		try:
			result, ret_code = self._run(cmd, True)
		except OSError as e:
			logging.error("PowerMan Error: The command '%s' failed: %s\n", cmd, e)
			return -1
		except ValueError as e:
			logging.error("PowerMan Error: Popen: invalid arguments: %s\n", e)
			return -1
		logging.debug("pm.off result: %s ret_code: %s\n", result, ret_code)

		## For some devices, the "on" or "off" command can fail silently,
		## but for query powerman keeps trying until it gets a valid answer;
		## so we must check after trying to power on/off a device.
		## Powerman seems to report the old state if asked too quickly, wait a second.

		time.sleep(1)
		queryret = self.query(host)

		if (ret_code == 0 and queryret == "on") or (ret_code < 0 and queryret == "off"):
			logging.warning("command '%s' returned (%s) but query reported (%s) afterwards\n", cmd, result, queryret)

		if queryret == "off":
			return 0
		else:
			return -1

	def list(self):
		## Error checking here is faulty.  Try passing
		## invalid args, e.g. --query --exprange to see failure
		cmd = ["-q","--exprange"]
		try:
			result, ret_code = self._run(cmd, False)
		except OSError as e:
			logging.error("PowerMan Error: The command '%s' failed: %s\n", cmd, e)
			return -1
		except ValueError as e:
			logging.error("PowerMan Error: Popen: invalid arguments: %s\n", e)
			return -1
		if ret_code < 0:
			# there was an error with the command
			return ret_code
		else:
			state = {}
			for line in result[0].split('\n'):
				if len(line) > 2:
					fields = line.split(':')
					if len(fields) == 2:
						state[fields[0]] = (fields[0],fields[1])
			return state

	def query(self, host):
		cmd = ["--query", host]
		try:
			result, ret_code = self._run(cmd, True)
		except OSError as e:
			logging.error("PowerMan Error: The command '%s' failed: %s\n", cmd, e)
			return -1
		except ValueError as e:
			logging.error("PowerMan Error: Popen: invalid arguments: %s\n", e)
			return -1
		if ret_code < 0:
			# there was an error with the command
			return ret_code
		else:
			res = result.split('\n')
			res = [r.split() for r in res]
			# find the host in command's returned output
			for lst in res:
				if lst[0] == 'No' and lst[1] == 'such' and lst[2] == 'nodes:':
					return -1
				if host in lst:
					return lst[0][:-1] # lst[0] would be 'off:'-- this removes the colon
			# host isn't in the output
			return -1


def get_power_status(conn, options):
	logging.debug("get_power_status function:\noptions: %s\n", str(options))
	pm = PowerMan(options['--ip'], options['--ipport'])
	# if Pacemaker is checking the status of the Powerman server...
	if options['--action'] == 'monitor':
		if pm.is_running():
			logging.debug("Powerman is running\n")
			return "on"
		logging.debug("Powerman is NOT running\n")
		return "off"
	else:
		status = pm.query(options['--plug'])
		if isinstance(int, type(status)):
			# query only returns ints on error
			logging.error("get_power_status: query returned %s\n", str(status))
			fail(EC_STATUS)
		return status


def set_power_status(conn, options):
	logging.debug("set_power_status function:\noptions: %s", str(options))
	pm = PowerMan(options['--ip'], options['--ipport'])

	action = options["--action"]
	if action == "on":
		pm.on(options['--plug'])
	elif action == "off":
		pm.off(options['--plug'])

	return


def reboot(conn, options):
	logging.debug("reboot function:\noptions: %s", str(options))
	pm = PowerMan(options['--ip'], options['--ipport'])
	res = pm.off(options['--plug'])
	if res < 0:
		logging.error("reboot: power off failed.\n")
		return False
	time.sleep(2)
	res = pm.on(options['--plug'])
	if res < 0:
		logging.error("reboot: power on failed.\n")
		return False
	return True


def get_list(conn, options):
	logging.debug("get_list function:\noptions: %s", str(options))
	pm = PowerMan(options['--ip'], options['--ipport'])

	outlets = pm.list()
	logging.debug("get_list outlets.keys: %s", str(outlets.keys()))
	return outlets


def define_new_opts():
	"""add elements to all_opt dict if you need to define new options"""
	pass


def main():
	device_opt = [
		'ipaddr',
		'no_password',
		'no_login',
	]

	raw_args=sys.argv

	atexit.register(atexit_handler)

	define_new_opts()

	# redefine default values for the options given by fencing.py
	# these 3 different values are derived from the lssd test cluster and may
	# need to adjusted depending on how other systems fare
	all_opt['ipport']['default'] = '10101'
	all_opt['delay']['default'] = '3'
	all_opt['power_wait']['default'] = '3'

	options = check_input(device_opt, process_input(device_opt))
	logging.debug("fence_powerman.main: RAW ARGS: %s\n options: %s", str(raw_args), str(options))
	docs = {}
	docs["shortdesc"] = "Fence Agent for Powerman"
	docs["longdesc"] = "This is a Pacemaker Fence Agent for the \
Powerman management utility that was designed for LLNL systems."
	docs["vendorurl"] = "https://github.com/chaos/powerman"
	show_docs(options, docs)

	## Do the delay of the fence device 
	run_delay(options)

	if options["--action"] in ["off", "reboot"]:
		# add extra delay if rebooting
		time.sleep(int(options["--delay"]))

	# call the fencing.fence_action function, passing in my various fence functions
	result = fence_action(
				None,
				options,
				set_power_status,
				get_power_status,
				get_list,
				reboot
			)

	sys.exit(result)


if __name__ == "__main__":
	main()
