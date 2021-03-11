#!@PYTHON@ -tt
import os
import time
from datetime import datetime
import sys
import subprocess
import re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import is_executable, fail_usage, run_delay
import logging

#### important!!! #######
class PowerMan:
	"""Python wrapper for calling powerman commands

	This class makes calls to a powerman deamon for a cluster of computers.
	The make-up of such a call looks something like:
		$ pm -h elssd1:10101 <option> <node>
	where option is something like --off, --on, --cycle and where node is 
	elssd8, or whatever values are setup in powerman.conf.  Note that powerman
	itself must be configured for this fence agent to work.
	"""

	def __init__(self, powerman_path, server_name, port):
		"""
		Args:
			server_name: (string) host or ip of powerman server
			port: (str) port number that the powerman server is listening on
		"""
		self.powerman_path = powerman_path
		self.server_name = server_name
		self.port = port
		self.server_and_port = server_name + ":" + str(port)
		self.base_cmd = [
			self.powerman_path,
			"--server-host",
			self.server_and_port
		]

	def _run(self, cmd, only_first_line):
		# Args:
		#   cmd: (list) commands and arguments to pass to the program_name

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

	## Some devices respond to on or off actions as if the action was successful,
	## when it was not.
	##
	## This is not unique to powerman, and so fence_action ignores the return code
	## from the set_power_fn and queries the device to confirm the power status of
	## the machine.
	##
	## For this reason we do not do a query ourself, retry, etc. in on() or off().

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

		return ret_code

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

		return ret_code

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
	pm = PowerMan(options['--powerman-path'], options['--ip'], options['--ipport'])
	# if Pacemaker is checking the status of the Powerman server...
	if options['--action'] == 'monitor':
		if pm.is_running():
			logging.debug("Powerman is running\n")
			return "on"
		logging.debug("Powerman is NOT running\n")
		return "error"
	else:
		status = pm.query(options['--plug'])
		if isinstance(int, type(status)):
			# query only returns ints on error
			logging.error("get_power_status: query returned %s\n", str(status))
			fail(EC_STATUS)
		return status


def set_power_status(conn, options):
	logging.debug("set_power_status function:\noptions: %s", str(options))
	pm = PowerMan(options['--powerman-path'], options['--ip'], options['--ipport'])

	action = options["--action"]
	if action == "on":
		pm.on(options['--plug'])
	elif action == "off":
		pm.off(options['--plug'])

	return


def get_list(conn, options):
	logging.debug("get_list function:\noptions: %s", str(options))
	pm = PowerMan(options['--powerman-path'], options['--ip'], options['--ipport'])

	outlets = pm.list()
	logging.debug("get_list outlets.keys: %s", str(outlets.keys()))
	return outlets


def define_new_opts():
	all_opt["powerman_path"] = {
		"getopt" : ":",
		"longopt" : "powerman-path",
		"help" : "--powerman-path=[path]         Path to powerman binary",
		"required" : "0",
		"shortdesc" : "Path to powerman binary",
		"default" : "@POWERMAN_PATH@",
		"order": 200
	}


def main():
	device_opt = [
		'ipaddr',
		'no_password',
		'no_login',
		'powerman_path',
	]

	atexit.register(atexit_handler)

	define_new_opts()

	# redefine default values for the options given by fencing.py
	# these 3 different values are derived from the lssd test cluster and may
	# need to adjusted depending on how other systems fare
	all_opt['ipport']['default'] = '10101'
	all_opt['delay']['default'] = '3'
	all_opt['power_wait']['default'] = '3'

	options = check_input(device_opt, process_input(device_opt))
	docs = {}
	docs["shortdesc"] = "Fence Agent for Powerman"
	docs["longdesc"] = "This is a Pacemaker Fence Agent for the \
Powerman management utility that was designed for LLNL systems."
	docs["vendorurl"] = "https://github.com/chaos/powerman"
	show_docs(options, docs)

	run_delay(options)

	if not is_executable(options["--powerman-path"]):
		fail_usage("Powerman not found or not executable at path " + options["--powerman-path"])

	# call the fencing.fence_action function, passing in my various fence functions
	result = fence_action(
				None,
				options,
				set_power_status,
				get_power_status,
				get_list,
				None
			)
	sys.exit(result)


if __name__ == "__main__":
	main()
