#!/usr/bin/python -tt

__author__ = 'Ondrej Mular <omular@redhat.com>'

from configobj import ConfigObj
from time import sleep
import sys
import subprocess
import shlex
import logging
import os
import re
import fence_tests_lib as ftl

VERBOSE = not set(["-v", "--verbose"]).isdisjoint(sys.argv)

avail_opt = {
	"verbose": {
		"getopt": "v",
		"longopt": "verbose",
		"description": "Verbose mode"
	},
	"help": {
		"getopt": "h",
		"longopt": "help",
		"description": "Display help and exit"
	},
	"device": {
		"getopt": "d:",
		"longopt": "device",
		"description": "List of devices to test (e.g.: apc,docker)",
		"default": None
	},
	"action": {
		"getopt": "a:",
		"longopt": "action",
		"description": "List of actions to test",
		"default": None
	},
	"test-config": {
		"getopt": "t",
		"longopt": "test-config",
		"description": "Test device config",
		"default": False
	},
	"force": {
		"getopt": "f",
		"longopt": "force",
		"description": "force rewrite existing log file",
		"default": False
	}
}


class RecordTestData(object):

	def __init__(self, device_cfg, action_cfg, force=False):
		self.device_cfg = device_cfg
		self.action_cfg = action_cfg
		self.device_config = ConfigObj(device_cfg, unrepr=True)
		self.action_config = ConfigObj(action_cfg, unrepr=True)
		logs_path = os.path.join(ftl.MITM_LOGS_PATH, self.device_config["agent"][6:])
		if "subdir" in self.device_config:
			logs_path = os.path.join(logs_path, self.device_config["subdir"])
		self.log = os.path.join(logs_path, "%s.log" % ftl.get_basename(action_cfg))
		if os.path.isfile(self.log) and not force:
			raise Exception("Log file already exists. Use --force option to overwrite it.")
		elif os.path.isfile(self.log):
			os.remove(self.log)
		self.mitm_process = None
		self.params = ""
		self.env = {}
		self.type = self.device_config["agent_type"].lower()


	def setUp_MITM(self):
		cmd, env = ftl.get_MITM_record_cmd(self.device_cfg, self.log)
		if cmd:
			logging.debug("Executing: %s", cmd)
			try:
				# Try to start replay server
				process = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
			except OSError as e:
				logging.error("Unable to start record server: %s" % e.message)
				raise
			sleep(1)  # wait for replay server
			if process.poll() is not None:  # check if replay server is running correctly
				raise Exception("Replay server is not running correctly.")
			self.mitm_process = process

	def tearDown_MITM(self):
		if self.mitm_process:
			process = self.mitm_process
			# if server is still alive after test, kill it
			if process.poll() is None:
				try:
					# race condition, process can exit between checking and killing process
					process.kill()
				except Exception:
					pass
			pipe_stdout, pipe_stderr = process.communicate()
			process.stdout.close()
			process.stderr.close()
			logging.debug("Record server STDOUT:\n%s\nRecord server STDERR:\n%s", str(pipe_stdout), str(pipe_stderr))

	def setUp_pycurl(self):
		self.params = "--fencing_pycurl-log-out %s" % self.log

	def tearDown_pycurl(self):
		pass

	def setUp_binmitm(self):
		cf = os.path.abspath(ftl.BINMITM_COUNTERFILE)
		if os.path.exists(cf):
			os.remove(cf)
		if "BINMITM_INPUT" in os.environ:
			del os.environ["BINMITM_INPUT"]
		if "BINMITM_DEBUG" in os.environ:
			del os.environ["BINMITM_DEBUG"]
		self.env = {}
		self.env["BINMITM_COUNTER_FILE"] = ftl.BINMITM_COUNTERFILE
		self.env["BINMITM_OUTPUT"] = self.log

	def tearDown_binmitm(self):
		cf = os.path.abspath(ftl.BINMITM_COUNTERFILE)
		if os.path.exists(cf):
			os.remove(cf)

	def setUp(self):
		type = self.type
		if type == "mitmproxy":
			self.setUp_MITM()
		elif type =="pycurl":
			self.setUp_pycurl()
		elif type == "binmitm":
			self.setUp_binmitm()

	def tearDown(self):
		type = self.type
		if type == "mitmproxy":
			self.tearDown_MITM()
		elif type =="pycurl":
			self.tearDown_pycurl()
		elif type == "binmitm":
			self.tearDown_binmitm()

	def record(self):
		self.setUp()

		success = True
		actions = self.action_config

		for action in actions["actions"]:
			if not success:
				break
			cmd, stdin, env = ftl._prepare_command(self.device_config, self.params)
			env.update(self.env)
			cmd += " -o %s"% (action["command"])

			status, stdout, stderr = ftl.run_agent(cmd, stdin, env)

			logging.debug("AGENT EXITCODE: %s" % str(status))
			logging.debug("AGENT STDOUT: %s" % stdout)
			logging.debug("AGENT STDERRT: %s" % stderr)

			success = success and bool(re.search(action["return_code"], str(status), re.IGNORECASE))
			if not success:
				logging.error("EXITCODE: %s (expected: %s)" % (str(status), re.search(action["return_code"])))

		self.tearDown()
		return success


def get_device_cfg_path(device):
	device_cfg = os.path.join(ftl.DEVICES_PATH, "%s.cfg" % device)
	if not os.path.isfile(device_cfg):
		raise Exception("Device config '%s' not found." % device_cfg)
	return device_cfg


def get_action_cfg_path(action):
	action_cfg = os.path.join(ftl.ACTIONS_PATH, "%s.cfg" % action)
	if not os.path.isfile(action_cfg):
		raise Exception("Action config '%s' not found." % action_cfg)
	return action_cfg


def main():
	if VERBOSE:
		logging.getLogger().setLevel(logging.DEBUG)
	else:
		logging.getLogger().setLevel(logging.INFO)

	opt = ftl.get_options(avail_opt)

	if "--help" in opt:
		ftl.show_help(avail_opt, "This program can create testing data for MITM tests of fence-agents.")
		sys.exit(0)

	if opt["--device"] is None:
		logging.error("Device has to be defined.")
		ftl.show_help(avail_opt)
		sys.exit(1)

	if opt["--action"] is None and not opt["--test-config"]:
		logging.error("Action has to be defined when not testing config.")
		ftl.show_help(avail_opt)
		sys.exit(1)

	device_cfg = get_device_cfg_path(opt["--device"])

	if opt["--test-config"]:
		config = ConfigObj(device_cfg, unrepr=True)

		cmd, stdin, env = ftl._prepare_command(config)
		cmd += " -o status"
		status, stdout, stderr = ftl.run_agent(cmd, stdin, env)

		if status != 0 and status != 2:
			logging.error("Cannot obtain status:\nRETURNCODE: %s\nSTDOUT:\n%s\nSTDERR:\n%s\n" % (str(status), stdout, stderr))
			sys.exit(1)
		print stdout,

		sys.exit(0)

	action_cfg = get_action_cfg_path(opt["--action"])

	try:
		status = RecordTestData(device_cfg, action_cfg, opt["--force"]).record()
	except Exception as e:
		logging.error(e.message)
		logging.error("Obtaining testing data failed.")
		sys.exit(1)

	if not status:
		logging.error("Obtaining testing data failed.")
		sys.exit(1)
	print "Obtaining log file was successful."

if __name__ == "__main__":
	main()