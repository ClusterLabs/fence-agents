#!/usr/bin/python -tt

import sys
import logging
import os
import unittest
import re
import pprint
from configobj import ConfigObj

import fence_tests_lib as ftl

VERBOSE = not set(["-v", "--verbose"]).isdisjoint(sys.argv)
PARAM_FORCE = ftl.get_and_remove_arg("--param")
methods = ftl.get_and_remove_arg("--method") or ftl.get_and_remove_arg("-m")
METHODS_TO_TEST = methods.split(",") if methods else ftl.METHODS
LOCAL_PORT = (
	ftl.get_and_remove_arg("--port") or
	ftl.get_and_remove_arg("-p") or
	"4242"
)


# define tests which cannot be autodetected
# (device_config, action_config, log_file)
TESTS = [
]

# cli parameters
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
		"list": ",",
		"description": "List of devices to test (e.g.: apc,docker)",
		"default": None
	},
	"action": {
		"getopt": "a:",
		"longopt": "action",
		"list": ",",
		"description": "List of actions to test",
		"default": None
	},
	"method": {
		"getopt": "m:",
		"longopt": "method",
		"list": ",",
		"description": "List of input methods to test",
		"default": ftl.METHODS
	},
	"failfast": {
		"getopt": "f",
		"longopt": "failfast",
		"description": "Stop after first failed test",
		"default": False
	},
	"show-tests": {
		"getopt": "S",
		"longopt": "show-tests",
		"description": "Prints all found tests and exit",
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


# TestCase class which adds posibility to add param into tests
class ParametrizedTestCase(unittest.TestCase):
	"""
	TestCase classes that want to be parametrized should
	inherit from this class.
	"""

	def __init__(self, method_name='runTest', param=None):
		super(ParametrizedTestCase, self).__init__(method_name)
		self.param = param

	@staticmethod
	def parametrize(test_case_klass, param=None):
		"""
		Create a suite containing all tests taken from the given
		subclass, passing them the parameter 'param'.
		"""
		test_loader = unittest.TestLoader()
		test_names = test_loader.getTestCaseNames(test_case_klass)
		suite = unittest.TestSuite()
		for name in test_names:
			suite.addTest(test_case_klass(name, param=param))
		return suite


# TestCase for testing of one agent
class FenceAgentTestCase(ParametrizedTestCase):
	def __getattr__(self, key):
		return None

	# prepare environment for running test with MITM_PROXY
	def setUp_MITMPROXY(self):
		if "ipport" in self.device_config["options"]:
			self.device_config["options"]["ipport"][0] = LOCAL_PORT

		self.mitm_process = ftl.start_mitm_server(
			*ftl.get_mitm_replay_cmd(self.device_config, self.action_log)
		)

		if "ipaddr" in self.device_config["options"]:
			self.device_config["options"]["ipaddr"][0] = "localhost"

	def tearDown_MITMPROXY(self):
		ftl.stop_mitm_server(self.mitm_process)

	def setUp_pycurl(self):
		self.params = "--fencing_pycurl-log-in %s" % self.action_log

	def tearDown_pycurl(self):
		pass

	def setUp_BINMITM(self):
		cf = os.path.abspath(ftl.BINMITM_COUNTERFILE)
		if os.path.exists(cf):
			os.remove(cf)
		if "BINMITM_OUTPUT" in os.environ:
			del os.environ["BINMITM_OUTPUT"]
		if "BINMITM_DEBUG" in os.environ:
			del os.environ["BINMITM_DEBUG"]
		self.env = {
			"BINMITM_COUNTER_FILE": ftl.BINMITM_COUNTERFILE,
			"BINMITM_INPUT": self.action_log
		}

	def tearDown_BINMITM(self):
		cf = os.path.abspath(ftl.BINMITM_COUNTERFILE)
		if os.path.exists(cf):
			os.remove(cf)

	def setUp(self):
		self.device_cfg, self.action_cfg, self.action_log = self.param
		self.device_config = ConfigObj(self.device_cfg, unrepr=True)
		if PARAM_FORCE:
			force_param, force_param_val = PARAM_FORCE.split("=", 1)
			if force_param in self.device_config["options"]:
				self.device_config["options"][force_param][0] = force_param_val
		self.action_config = ConfigObj(self.action_cfg, unrepr=True)
		self.type = self.device_config["agent_type"].lower()
		self.params = ""
		self.mitm_process = None
		self.env = {}
		agent_type = self.type
		if agent_type == "mitmproxy":
			self.setUp_MITMPROXY()
		elif agent_type == "pycurl":
			self.setUp_pycurl()
		elif agent_type == "binmitm":
			self.setUp_BINMITM()

	def tearDown(self):
		agent_type = self.type
		if agent_type == "mitmproxy":
			self.tearDown_MITMPROXY()
		elif agent_type == "pycurl":
			self.tearDown_pycurl()
		elif agent_type == "binmitm":
			self.tearDown_BINMITM()

	@unittest.skipIf(
		"getopt" not in METHODS_TO_TEST, "Not testing getopt method"
	)
	def test_getopt(self):
		self.agent_test("getopt")

	@unittest.skipIf(
		"longopt" not in METHODS_TO_TEST, "Not testing longopt method"
	)
	def test_longopt(self):
		self.agent_test("longopt")

	@unittest.skipIf("stdin" not in METHODS_TO_TEST, "Not testing stdin method")
	def test_stdin(self):
		self.agent_test("stdin")

	def get_failure_message(
		self, expected_status, status, stdout="", stderr="", longer=False
	):
		msg = "Return code was {actual} (expected: {expected})".format(
			actual=status, expected=expected_status
		)
		if longer:
			msg += "\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}\n".format(
				stdout=stdout,
				stderr=stderr
			)
		return msg

	# run test of agent with specific method
	def agent_test(self, method):
		action_file = self.action_cfg
		actions = self.action_config
		for action in actions["actions"]:
			self.assertTrue(
				"command" in action,
				"Action {action} need to have defined 'command'".format(
					action=action_file
				)
			)
			self.assertTrue(
				"return_code" in action,
				"Command '{command}' (in {file}) need to have 'return_code' "
				"defined".format(
					command=action["command"], file=action_file
				)
			)

			cmd, stdin, env = ftl.prepare_command(
				self.device_config, self.params, method
			)
			env.update(self.env)

			if method == "stdin":
				if stdin is None:
					stdin = ""
				stdin += "action=" + action["command"]
			elif method == "longopt":
				cmd += " --action=" + action["command"]
			elif method == "getopt":
				cmd += " -o " + action["command"]

			status, stdout, stderr = ftl.run_agent(cmd, stdin, env)

			logging.debug("AGENT EXITCODE: {0}".format(status))
			logging.debug("AGENT STDOUT: {0}".format(stdout))
			logging.debug("AGENT STDERR: {0}".format(stderr))

			self.assertTrue(
				bool(re.search(
					action["return_code"], str(status), re.IGNORECASE)
				),
				self.get_failure_message(
					action["return_code"], status, stdout, stderr, VERBOSE
				)
			)

	def shortDescription(self):
		self.device_cfg, self.action_cfg, self.action_log = self.param
		return self.get_test_identificator(True)

	def get_test_identificator(self, short=False):
		if short:
			if not self.short_test_identificator:
				self.short_test_identificator = "{0} => {0}".format(
					ftl.get_basename(self.device_cfg),
					ftl.get_basename(self.action_cfg)
				)
			return self.short_test_identificator

		if not self.test_identificator:
			self.test_identificator =\
				"AGENT: {agent} ({config})\nACTION: {action}".format(
					agent=self.device_config["name"],
					config=self.device_cfg,
					action=self.action_cfg
				)
		return self.test_identificator


# method tries to find tests in directory tree
# returns list of (agent_cfg_path, action_cfg_path, log_path)
def find_tests(opt):
	tests = []
	agents = []
	for f in os.listdir(ftl.DEVICES_PATH):
		if (
			os.path.isfile(os.path.join(ftl.DEVICES_PATH, f)) and
			f.endswith(".cfg") and
			(not opt["--device"] or f[:-4] in opt["--device"])
		):
			agents.append(os.path.join(ftl.DEVICES_PATH, f))

	actions = []
	for f in os.listdir(ftl.ACTIONS_PATH):
		if (
			os.path.isfile(os.path.join(ftl.ACTIONS_PATH, f)) and
			f.endswith(".cfg") and
			(not opt["--action"] or f[:-4] in opt["--action"])
		):
			actions.append(f)

	for agent_cfg in agents:
		logging.debug("Opening device config '%s'" % agent_cfg)
		config = ConfigObj(agent_cfg, unrepr=True)
		logs_path = os.path.join(
			ftl.MITM_LOGS_PATH, config["agent"][6:]  # remove prefix 'fence_'
		)
		if "subdir" in config:
			logs_path = os.path.join(logs_path, config["subdir"])
		if not os.path.exists(logs_path):
			logging.info("Logs directory '{0}' not exists.".format(logs_path))
			continue
		logs = []
		for f in os.listdir(logs_path):
			if (
				os.path.isfile(os.path.join(logs_path, f)) and
				f.endswith(".log")
			):
				logs.append(f)

		for log in logs:
			action = "%scfg" % log[:-3]  # replace suffix 'log' with 'cfg'
			if action in actions:
				test = (
					agent_cfg,
					os.path.join(ftl.ACTIONS_PATH, action),
					os.path.join(logs_path, log)
				)
				logging.debug("Found test: {0}".format(test))
				tests.append(test)
	return tests


def main():
	if VERBOSE:
		logging.getLogger().setLevel(logging.DEBUG)
	else:
		logging.getLogger().setLevel(logging.INFO)

	opt = ftl.get_options(avail_opt)

	if "--help" in opt:
		ftl.show_help(
			avail_opt, "This program can run MITM tests of fence-agents."
		)
		sys.exit(0)

	valid_tests = find_tests(opt)

	if VERBOSE or opt["--show-tests"]:
		pprint.pprint(valid_tests)

	if opt["--show-tests"]:
		return

	for test in TESTS:
		if (
			test not in valid_tests and
			(
				opt["--device"] is None or
				os.path.basename(test[0])[:-4] in opt["--device"]
			) and
			(
				opt["--action"] is None or
				os.path.basename(test[1])[:-4] in opt["--action"]
			) and
			os.path.exists(test[0]) and
			os.path.exists(test[1]) and
			os.path.exists(test[2])
		):
			valid_tests.append(test)

	suite = unittest.TestSuite()

	for test in valid_tests:
		# agent, action, log = test
		suite.addTest(
			ParametrizedTestCase.parametrize(FenceAgentTestCase, param=test)
		)

	try:
		unittest.TextTestRunner(
			verbosity=2, failfast=opt["--failfast"]
		).run(suite)
	except ftl.LibException as e:
		logging.error(str(e))
		sys.exit(1)


if __name__ == "__main__":
	main()
