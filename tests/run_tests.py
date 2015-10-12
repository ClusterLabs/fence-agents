#!/usr/bin/python -tt

__author__ = 'Ondrej Mular <omular@redhat.com>'

from configobj import ConfigObj
from time import sleep
import sys
import subprocess
import shlex
import logging
import os
import unittest
import re
import pprint
import fence_tests_lib as ftl

VERBOSE = not set(["-v", "--verbose"]).isdisjoint(sys.argv)
PARAM_FORCE = ftl.get_and_remove_arg("--param")
methods = ftl.get_and_remove_arg("--method") or ftl.get_and_remove_arg("-m")
METHODS_TO_TEST = methods.split(",") if methods else ftl.METHODS

# define tests which cannot be autodetected
#(device_config, action_config, log_file)
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
	}
}


# TestCase class which adds posibility to add param into tests
class ParametrizedTestCase(unittest.TestCase):
	""" TestCase classes that want to be parametrized should
		inherit from this class.
	"""
	def __init__(self, methodName='runTest', param=None):
		super(ParametrizedTestCase, self).__init__(methodName)
		self.param = param

	@staticmethod
	def parametrize(testcase_klass, param=None):
		""" Create a suite containing all tests taken from the given
			subclass, passing them the parameter 'param'.
		"""
		testloader = unittest.TestLoader()
		testnames = testloader.getTestCaseNames(testcase_klass)
		suite = unittest.TestSuite()
		for name in testnames:
			suite.addTest(testcase_klass(name, param=param))
		return suite


# TestCase for testing of one agent
class FenceAgentTestCase(ParametrizedTestCase):

	def __getattr__(self, key):
		return None


	# prepate enviroment for running test with MITM_PROXY
	def setUp_MITMPROXY(self):
		(replay_cmd, replay_env) = ftl.get_MITM_replay_cmd(self.device_config, self.action_log)
		if replay_cmd:
			logging.debug("Executing: %s", replay_cmd)
			try:
				# Try to start replay server
				process = subprocess.Popen(shlex.split(replay_cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=replay_env)
			except OSError as e:
				logging.error("Unable to start replay server: %s" % e.message)
				raise
			sleep(1)  # wait for replay server
			if process.poll() is not None:  # check if replay server is running correctly
				raise Exception("Replay server is not running correctly.")
			self.mitm_process = process


	def tearDown_MITMPROXY(self):
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
			logging.debug("Replay server STDOUT:\n%s\nReplay server STDERR:\n%s", str(pipe_stdout), str(pipe_stderr))


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
		self.env = {}
		self.env["BINMITM_COUNTER_FILE"] = ftl.BINMITM_COUNTERFILE
		self.env["BINMITM_INPUT"] = self.action_log


	def tearDown_BINMITM(self):
		cf = os.path.abspath(ftl.BINMITM_COUNTERFILE)
		if os.path.exists(cf):
			os.remove(cf)


	def setUp(self):
		if PARAM_FORCE:
			force_param, force_param_val = PARAM_FORCE.split("=", 1)
		self.device_cfg, self.action_cfg, self.action_log = self.param
		self.device_config = ConfigObj(self.device_cfg, unrepr=True)
		if PARAM_FORCE and force_param in self.device_config["options"]:
			self.device_config["options"][force_param][0] = force_param_val
		self.action_config = ConfigObj(self.action_cfg, unrepr=True)
		self.type = self.device_config["agent_type"].lower()
		self.params = ""
		self.mitm_process = None
		self.env = {}
		type = self.type
		if type == "mitmproxy":
			self.setUp_MITMPROXY()
		elif type =="pycurl":
			self.setUp_pycurl()
		elif type == "binmitm":
			self.setUp_BINMITM()


	def tearDown(self):
		type = self.type
		if type == "mitmproxy":
			self.tearDown_MITMPROXY()
		elif type =="pycurl":
			self.tearDown_pycurl()
		elif type == "binmitm":
			self.tearDown_BINMITM()


	@unittest.skipIf("getopt" not in METHODS_TO_TEST, "Not testing getopt method")
	def test_getopt(self):
		self.agent_test("getopt")


	@unittest.skipIf("longopt" not in METHODS_TO_TEST, "Not testing longopt method")
	def test_longopt(self):
		self.agent_test("longopt")


	@unittest.skipIf("stdin" not in METHODS_TO_TEST, "Not testing stdin method")
	def test_stdin(self):
		self.agent_test("stdin")


	def get_failure_message(self, expected_status, status, stdout="", stderr="", long=False):
		msg = "Return code was %s (expected: %s)" % (str(status), str(expected_status))
		if long:
			msg += "\nSTDOUT:\n%s\nSTDERR:\n%s\n" % (stdout, stderr)
		return msg

	# run test of agent with specific method
	def agent_test(self, method):
		action_file = self.action_cfg
		actions = self.action_config
		for action in actions["actions"]:
			self.assertTrue(action.has_key("command"), "Action %s need to have defined 'command'"% (action_file))
			self.assertTrue(action.has_key("return_code"), "Command %s (in %s) need to have 'return_code' defined"% (action_file, action["command"]))
			cmd, stdin, env = ftl._prepare_command(self.device_config, self.params, method)
			env.update(self.env)

			if method == "stdin":
				if stdin is None:
					stdin = ""
				stdin += "action=%s"% (action["command"])
			elif method == "longopt":
				cmd += " --action=%s"% (action["command"])
			elif method == "getopt":
				cmd += " -o %s"% (action["command"])

			status, stdout, stderr = ftl.run_agent(cmd, stdin, env)

			logging.debug("AGENT EXITCODE: %s" % str(status))

			self.assertTrue(bool(re.search(action["return_code"], str(status), re.IGNORECASE)), self.get_failure_message(action["return_code"], status, stdout, stderr, VERBOSE))


	def shortDescription(self):
		self.device_cfg, self.action_cfg, self.action_log = self.param
		return self.get_test_identificator(True)


	def get_test_identificator(self, short=False):
		if short:
			if not self.short_test_identificator:
				self.short_test_identificator = "%s => %s" % (ftl.get_basename(self.device_cfg), ftl.get_basename(self.action_cfg))
			return self.short_test_identificator

		if not self.test_identificator:
			self.test_identificator = "AGENT: %s (%s)\nACTION: %s" % (self.device_config["name"], self.device_cfg, self.action_cfg)
		return self.test_identificator


# method tries to find tests in directory tree
# returns list of (agent_cfg_path, action_cfg_path, log_path)
def find_tests(opt):
	tests = []
	agents = [os.path.join(ftl.DEVICES_PATH, f) for f in os.listdir(ftl.DEVICES_PATH)
		if os.path.isfile(os.path.join(ftl.DEVICES_PATH, f)) and f.endswith(".cfg") and (not opt["--device"] or f[:-4] in opt["--device"])]
	actions = [f for f in os.listdir(ftl.ACTIONS_PATH)
		if os.path.isfile(os.path.join(ftl.ACTIONS_PATH, f)) and f.endswith(".cfg") and (not opt["--action"] or f[:-4] in opt["--action"])]

	for agent_cfg in agents:
		logging.debug("Opening device config '%s'" % agent_cfg)
		config = ConfigObj(agent_cfg, unrepr = True)
		logs_path = os.path.join(ftl.MITM_LOGS_PATH, config["agent"][6:])  # remove prefix 'fence_' from agent name
		if "subdir" in config:
			logs_path = os.path.join(logs_path, config["subdir"])
		if not os.path.exists(logs_path):
			logging.info("Logs directory '%s' not exists." % logs_path)
			continue
		logs = [f for f in os.listdir(logs_path) if os.path.isfile(os.path.join(logs_path, f)) and f.endswith(".log")]
		for log in logs:
			action = "%scfg" % log[:-3]  # replace suffix 'log' with 'cfg'
			if action in actions:
				test = (agent_cfg, os.path.join(ftl.ACTIONS_PATH, action), os.path.join(logs_path, log))
				logging.debug("Found test: %s" % str(test))
				tests.append(test)
	return tests


def main():
	if VERBOSE:
		logging.getLogger().setLevel(logging.DEBUG)
	else:
		logging.getLogger().setLevel(logging.INFO)

	opt = ftl.get_options(avail_opt)

	if "--help" in opt:
		ftl.show_help(avail_opt, "This program can run MITM tests of fence-agents.")
		sys.exit(0)

	valid_tests = find_tests(opt)

	if VERBOSE or opt["--show-tests"]:
		pprint.pprint(valid_tests)

	if opt["--show-tests"]:
		return

	for test in TESTS:
		if test not in valid_tests \
			and (opt["--device"] is None or os.path.basename(test[0])[:-4] in opt["--device"]) \
			and (opt["--action"] is None or os.path.basename(test[1])[:-4] in opt["--action"]) \
			and os.path.exists(test[0]) \
			and os.path.exists(test[1]) \
			and os.path.exists(test[2]):
			valid_tests.append(test)

	suite = unittest.TestSuite()

	for test in valid_tests:
		#agent, action, log = test
		suite.addTest(ParametrizedTestCase.parametrize(FenceAgentTestCase, param=test))

	unittest.TextTestRunner(verbosity=2, failfast=opt["--failfast"]).run(suite)

if __name__ == "__main__":
	main()
