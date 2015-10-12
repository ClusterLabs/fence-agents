__author__ = 'Ondrej Mular <omular@redhat.com>'
__all__ = ["get_MITM_replay_cmd", "get_agent_path", "_prepare_command", "run_agent",
	"get_basename", "METHODS", "ACTIONS_PATH", "BINMITM_COUNTERFILE",
	"FENCING_LIB_PATH", "DEVICES_PATH", "MITM_LOGS_PATH", "MITM_PROXY_PATH"
	"show_help", "get_options", "get_MITM_record_cmd","get_and_remove_arg"]


from pipes import quote
import sys
import subprocess
import shlex
import logging
import os
import getopt


METHODS = ["getopt", "longopt", "stdin"] # all available methods to test
FENCING_LIB_PATH = "../fence/agents/lib" # apth to fencing libs
DEVICES_PATH = "./devices.d" # path to device directory
ACTIONS_PATH = "./actions.d" # path to actions directory
MITM_LOGS_PATH = "./data/mitm-logs" # path to mitm logs
MITM_PROXY_PATH = "../mitm/mitmproxy-0.1/build" # path to mitm_proxy servers
BINMITM_COUNTERFILE = "./.counterfile" # path to counter file for BINMITM

# returns command for MITM_PROXY replay server
def get_MITM_replay_cmd(agent_config, log):
	if "replay_server_type" not in agent_config:
		return None, None

	replay = "%s/scripts-2.7/mitmreplay_%s" % (MITM_PROXY_PATH, agent_config["replay_server_type"])

	port = ("-p %s" % agent_config["options"]["ipport"][0]) if "ipport" in agent_config["options"] else ""
	cmd = "%s -f %s %s %s" % (replay, log, port, agent_config.get("replay_server_args", ""))
	env = os.environ.copy()
	env["PYTHONPATH"] = "%s/lib" % MITM_PROXY_PATH

	return cmd, env

def get_MITM_record_cmd(agent_config, log):
	if "replay_server_type" not in agent_config:
		return None, None

	record = "%s/scripts-2.7/mitmproxy_%s" % (MITM_PROXY_PATH, agent_config["replay_server_type"])

	port = ("-P %s" % agent_config["options"]["ipport"][0]) if "ipport" in agent_config["options"] else ""
	cmd = "%s -o %s %s %s %s" % (record, log, port, agent_config.get("replay_server_args", ""), agent_config.get("record_server_args", ""))
	env = os.environ.copy()
	env["PYTHONPATH"] = "%s/lib" % MITM_PROXY_PATH

	return cmd, env

# returns path to fence agent
def get_agent_path(agent):
	return "../fence/agents/%s/%s" % (agent[6:], agent)



# prepare agent command to run
def _prepare_command(config, params="", method="getopt"):
	env = {}
	env["PYTHONPATH"] = FENCING_LIB_PATH

	final_command = "python "

	if config.has_key("agent_path"):
		final_command += config["agent_path"]
	else:
		final_command += get_agent_path(config["agent"])

	if params:
		final_command += " %s " % params

	stdin_values = None

	for opt in config["options"]:
		if not isinstance(config["options"][opt], list) or not len(config["options"][opt]) >= 2:
			raise Exception("Option %s have to have at least value and longopt"% opt)

		value = config["options"][opt][0]
		has_value = value  is not None
		if opt == "action":
			## ignore action as it is not part of fence device definition
			continue

		if method == "stdin":
			option = opt
			if stdin_values is None:
				stdin_values = ""

			stdin_values += option
			stdin_values += "=" + (value if has_value else "1")

			stdin_values += "\n"

		elif method == "longopt":
			option = config["options"][opt][1]
			final_command += " " + option

			if has_value:
				final_command += " " + quote(value)

		elif method == "getopt":
			if len(config["options"][opt]) == (2 + 1):
				option = config["options"][opt][2]
			else:
				option = config["options"][opt][1]

			final_command += " " + option
			if has_value:
				final_command += " " + quote(value)

	return (final_command, stdin_values, env)


def run_agent(command, stdin="", env_vars={}):
	env = os.environ.copy()
	env.update(env_vars)

	logging.debug("Running: %s" % command)

	if stdin:
		logging.debug("STDIN: %s" % stdin)
	if env_vars:
		logging.debug("ENV: %s" % str(env_vars))

	process = subprocess.Popen(shlex.split(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

	if stdin:
		process.stdin.write(stdin)

	(pipe_stdout, pipe_stderr) = process.communicate()

	status = process.wait()

	process.stdout.close()
	process.stderr.close()
	process.stdin.close()
	return status, pipe_stdout, pipe_stderr


def get_basename(path):
	return os.path.splitext(os.path.basename(path))[0]


# show help
def show_help(avail_opt, description=None):
	print "%s [options]" % os.path.basename(sys.argv[0])
	if description:
		print description
	print "Options:"
	max = 30
	for o in avail_opt:
		args = "-%s, --%s%s" % (avail_opt[o]["getopt"].strip(":"), avail_opt[o]["longopt"], " <value>" if avail_opt[o]["getopt"].endswith(":") else "")
		line = "\t%s%s%s" % (args, (' ' * (max-len(args)) if max-len(args) > 0 else ' ' * 5), avail_opt[o]["description"])
		print line


# get options from command line parameters
def get_options(avail_opt):
	opt = {}
	for o in avail_opt.itervalues(): # set default values
		if "default" in o:
			opt["--%s" % o["longopt"]] = o["default"]

	if len(sys.argv) > 1:
		os.putenv("LANG", "C")
		os.putenv("LC_ALL", "C")

		getopt_string = ""
		longopt_list = []
		for k in avail_opt:
			getopt_string += avail_opt[k]["getopt"]
			longopt_list.append("%s%s" % (avail_opt[k]["longopt"], "=" if avail_opt[k]["getopt"].endswith(":") else ""))

		try:
			old_opt, _ = getopt.gnu_getopt(sys.argv[1:], getopt_string, longopt_list)
		except getopt.GetoptError, error:
			logging.error("Parse error: " + error.msg)
			show_help(avail_opt)
			sys.exit(1)

		## Transform short getopt to long one
		#####
		for o in dict(old_opt).keys():
			if o.startswith("--"):
				for x in avail_opt.keys():
					if avail_opt[x].has_key("longopt") and "--" + avail_opt[x]["longopt"] == o:
						if avail_opt[x]["getopt"].endswith(":"):
							opt[o] = dict(old_opt)[o]
							if "list" in avail_opt[x]:
								opt[o] = opt[o].split(avail_opt[x]["list"])
						else:
							opt[o] = True
			else:
				for x in avail_opt.keys():
					if x in avail_opt and avail_opt[x].has_key("getopt") and avail_opt[x].has_key("longopt") and \
						("-" + avail_opt[x]["getopt"] == o or "-" + avail_opt[x]["getopt"].rstrip(":") == o):
						if avail_opt[x]["getopt"].endswith(":"):
							opt["--" + avail_opt[x]["longopt"]] = dict(old_opt)[o]
							if "list" in avail_opt[x]:
								opt["--" + avail_opt[x]["longopt"]] = opt["--" + avail_opt[x]["longopt"]].split(avail_opt[x]["list"])
						else:
							opt["--" + avail_opt[x]["longopt"]] = True

	return opt


def get_and_remove_arg(arg):
	logging.debug("Getting arg: %s" % arg)
	if arg in sys.argv:
		index = sys.argv.index(arg)
		sys.argv.remove(arg)
		if len(sys.argv) > index:
			value = sys.argv[index]
			sys.argv.remove(value)
			logging.debug("%s: %s" % (arg, value))
			return value
	return None
