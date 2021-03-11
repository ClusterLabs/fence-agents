""" Library for fence agents testing via predefined scenarios """
from configobj import ConfigObj
import re, sys, os

EC_CONFIG_FAIL = 1

def _prepare_command(agent_file, method):
	""" Parse configuration of fence device and prepare (command + STDIN values) to execute.

	Fence device configuration is used to generate a command which can be executed.
	Because fence agents supports several options how to enter data, we can select
	from three different methods ("stdin", "getopt" - short options, "longopt").
	When method "stdin" is used then this function will generate also text which should
	be entered on STDIN instead of command itself.
	
	Example of agent definition:
	name = "Dummy fence device configuration"
	agent = "/bin/true"
	[options]
		login = [ "foo", "--username", "-l" ]
		passwd = [ "bar", "--password", "-p" ]
		ipaddr = [ "fence.example.com", "--ip", "-a" ]
                port = [ "1", "--plug" ]
	"""
	assert (method in ["stdin", "getopt", "longopt"]), "Invalid method entered"

	config = ConfigObj(agent_file, unrepr = True)

	assert ("agent" in config), "Fence agent has to be defined"
	final_command = config["agent"]
	stdin_values = None

	for opt in list(config["options"].keys()):
		assert isinstance(config["options"][opt], list), "Option %s have to have at least value and longopt"% (opt)
		assert len(config["options"][opt]) >= 2, "Option %s have to have at least value and longopt"% (opt)
		value = config["options"][opt][0]
		if opt == "action":
			## ignore action as it is not part of fence device definition
			continue

		if method == "stdin":
			option = opt
			if stdin_values == None:
				stdin_values = ""
			stdin_values += option + "=" + value + "\n"
		elif method == "longopt":
			option = config["options"][opt][1]
			final_command += " " + option + " " + value
		elif method == "getopt":
			if len(config["options"][opt]) == (2 + 1):
				option = config["options"][opt][2]
			else:
				option = config["options"][opt][1]
			final_command += " " + option + " " + value

	return (final_command, stdin_values)		

def test_action(agent, action_file, method, verbose = False):
	""" Run defined sequence of actions on a given fence agent.

	This function will run one set of test on a fence agent. Test itself consists of
	sequence of action and expected return codes. User can select from actions supported
	by fence agent (on, off, reboot, list, status, monitor) and sleep(X) command where X
	is in seconds and determine the length of pause between commands. Each action has to
	have defined regular expression which define acceptable return codes from fence agent
	or sleep.
	
	Example of action configuration file:
	name = "Simple Status"
	actions = [ { "command" : "status", "return_code" : "^[02]$" }, { "command" : "sleep(1)", "return_code" : "^0$" } ]	
	"""
	re_sleep_command = re.compile('sleep\(([0-9]+)\)', re.IGNORECASE)
	config = ConfigObj(action_file, unrepr = True)

	(command, stdin_options) = _prepare_command(agent, method)

	for action in config["actions"]:
		assert "command" in action, "Action %s need to have defined 'command'"% (action_file)
		assert "return_code" in action, "Command %s (in %s) need to have 'return_code' defined"% (action_file, action["command"])
	
		sleep_wait = None
		current_command = None
		current_stdin_options = None

		if not (action["command"] in [ "status", "reboot", "on", "off", "list", "monitor" ]):
			is_sleep = re.search(re_sleep_command, action["command"])
			if is_sleep != None:
				sleep_wait = is_sleep.group(1)
			else:
				sys.stderr.write("ERROR: %s contains unsupported action \"%s\"\n"% (action_file, action["command"]))
				sys.exit(1)

		if sleep_wait != None:
			current_command = "/bin/sleep " + sleep_wait
			current_stdin_options = None
		else:			
			current_command = command
			current_stdin_options = stdin_options

			if method == "stdin":
				if current_stdin_options == None:
					current_stdin_options = ""
				current_stdin_options += "action=%s"% (action["command"])
			elif method == "longopt":
				current_command += " --action=%s"% (action["command"])
			elif method == "getopt":
				current_command += " -o %s"% (action["command"])

		# @note: Broken pipe can occur here and I'm not sure why - non-deterministic
		if method == "stdin" and sleep_wait == None:
			current_command = "printf \"" + current_stdin_options + "\" | " + current_command

		if verbose == False:
			result = os.system(current_command + " &> /dev/null")
		else:
			print(current_command)
			result = os.system(current_command)
		exitcode = (result >> 8) & 0xFF

		is_valid_result_code = re.search(action["return_code"], str(exitcode), re.IGNORECASE)

		if is_valid_result_code == None:
			print(("TEST FAILED: %s failed on %s when using (%s)\n"% (agent, action_file, method)))
			print(("TEST INFO: %s returns %s\n"% (action["command"], str(exitcode))))
			return
	print(("TEST PASSED: %s worked on %s (%s)\n"% (agent, action_file, method)))
