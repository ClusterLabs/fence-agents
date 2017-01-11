#!/usr/bin/python -tt

import sys
import logging
import os
import re
from configobj import ConfigObj

import fence_tests_lib as ftl


class RecordException(Exception):
	pass


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
	},
	"port": {
		"getopt": "p:",
		"longopt": "port",
		"description":
			"Local port for communication between agent and mitmproxy",
		"default": "4242"
	}
}


class RecordTestData(object):
	def __init__(
			self, device_cfg, action_cfg, local_port, force=False
	):
		self.local_port = local_port
		self.device_cfg = device_cfg
		self.action_cfg = action_cfg
		self.device_cfg_obj = ConfigObj(device_cfg, unrepr=True)
		self.action_cfg_obj = ConfigObj(action_cfg, unrepr=True)
		logs_path = os.path.join(
			ftl.MITM_LOGS_PATH, self.device_cfg_obj["agent"][6:]
		)
		if "subdir" in self.device_cfg_obj:
			logs_path = os.path.join(logs_path, self.device_cfg_obj["subdir"])
		self.log = os.path.join(
			logs_path, "{name}.log".format(name=ftl.get_basename(action_cfg))
		)
		logging.debug("Log file: {log}".format(log=self.log))

		if os.path.isfile(self.log) and not force:
			if force:
				os.remove(self.log)
			else:
				raise RecordException(
					"Log file already exists. Use --force to overwrite it."
				)

		self.mitm_process = None
		self.params = ""
		self.env = {}
		self.type = self.device_cfg_obj["agent_type"].lower()

	def set_up_mitm(self):
		self.mitm_process = ftl.start_mitm_server(
			*ftl.get_mitm_record_cmd(
				self.device_cfg_obj, self.log, self.local_port
			)
		)

		if "ipaddr" in self.device_cfg_obj["options"]:
			self.device_cfg_obj["options"]["ipaddr"][0] = "localhost"
		if "ipport" in self.device_cfg_obj["options"]:
			self.device_cfg_obj["options"]["ipport"][0] = self.local_port

	def tear_down_mitm(self):
		ftl.stop_mitm_server(self.mitm_process)

	def set_up_pycurl(self):
		self.params = "--fencing_pycurl-log-out {log}".format(log=self.log)

	def tear_down_pycurl(self):
		pass

	def set_up_binmitm(self):
		cf = os.path.abspath(ftl.BINMITM_COUNTERFILE)
		if os.path.exists(cf):
			os.remove(cf)
		if "BINMITM_INPUT" in os.environ:
			del os.environ["BINMITM_INPUT"]
		if "BINMITM_DEBUG" in os.environ:
			del os.environ["BINMITM_DEBUG"]
		self.env = {
			"BINMITM_COUNTER_FILE": ftl.BINMITM_COUNTERFILE,
			"BINMITM_OUTPUT": self.log
		}

	def tear_down_binmitm(self):
		cf = os.path.abspath(ftl.BINMITM_COUNTERFILE)
		if os.path.exists(cf):
			os.remove(cf)

	def set_up(self):
		if self.type == "mitmproxy":
			self.set_up_mitm()
		elif self.type == "pycurl":
			self.set_up_pycurl()
		elif self.type == "binmitm":
			self.set_up_binmitm()

	def tear_down(self):
		if self.type == "mitmproxy":
			self.tear_down_mitm()
		elif self.type == "pycurl":
			self.tear_down_pycurl()
		elif self.type == "binmitm":
			self.tear_down_binmitm()

	def record(self):
		self.set_up()

		success = True
		actions = self.action_cfg_obj

		for action in actions["actions"]:
			if not success:
				break
			cmd, stdin, env = ftl.prepare_command(
				self.device_cfg_obj, self.params
			)

			env.update(self.env)
			cmd += " -o {action}".format(action=(action["command"]))

			status, stdout, stderr = ftl.run_agent(cmd, stdin, env)

			logging.debug("AGENT EXITCODE: {0}".format(str(status)))
			logging.debug("AGENT STDOUT: {0}".format(stdout))
			logging.debug("AGENT STDERR: {0}".format(stderr))

			success = success and bool(
				re.search(action["return_code"], str(status), re.IGNORECASE)
			)
			if not success:
				logging.error(
					"EXITCODE: {actual} (expected: {expected})".format(
						actual=str(status),
						expected=action["return_code"]
					)
				)

		self.tear_down()
		return success


def get_device_cfg_path(device):
	device_cfg = os.path.join(
		ftl.DEVICES_PATH, "{name}.cfg".format(name=device)
	)
	if not os.path.isfile(device_cfg):
		raise RecordException(
			"Device config '{cfg}' not found.".format(cfg=device_cfg)
		)
	return device_cfg


def get_action_cfg_path(action):
	action_cfg = os.path.join(
		ftl.ACTIONS_PATH, "{name}.cfg".format(name=action)
	)
	if not os.path.isfile(action_cfg):
		raise RecordException(
			"Action config '{cfg}' not found.".format(cfg=action_cfg)
		)
	return action_cfg


def main():
	if VERBOSE:
		logging.getLogger().setLevel(logging.DEBUG)
	else:
		logging.getLogger().setLevel(logging.INFO)

	opt = ftl.get_options(avail_opt)

	if "--help" in opt:
		ftl.show_help(
			avail_opt,
			"This program can create testing data for MITM tests of "
			"fence-agents."
		)
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

		cmd, stdin, env = ftl.prepare_command(config)
		cmd += " -o status"
		status, stdout, stderr = ftl.run_agent(cmd, stdin, env)

		if status != 0 and status != 2:
			logging.error("Cannot obtain status)")
			logging.error("Agent RETURNCODE: {0}".format(str(status)))
			logging.error("Agent STDOUT: {0}".format(stdout))
			logging.error("Agent STDERR: {0}".format(stdout))
			sys.exit(1)
		print stdout,

		sys.exit(0)

	action_cfg = get_action_cfg_path(opt["--action"])

	try:
		status = RecordTestData(
			device_cfg,
			action_cfg,
			opt["--port"],
			opt["--force"]
		).record()
	except (ftl.LibException, RecordException) as e:
		logging.error(str(e))
		logging.error("Obtaining testing data failed.")
		sys.exit(1)

	if not status:
		logging.error("Obtaining testing data failed.")
		sys.exit(1)
	print "Obtaining log file was successful."


if __name__ == "__main__":
	main()
