import sys
import subprocess
import shlex
import logging
import os
import getopt
from pipes import quote
from time import sleep


__all__ = [
	"get_mitm_replay_cmd", "get_agent_path", "prepare_command",
	"run_agent", "get_basename", "METHODS", "ACTIONS_PATH",
	"BINMITM_COUNTERFILE", "FENCING_LIB_PATH", "DEVICES_PATH", "MITM_LOGS_PATH",
	"MITM_PROXY_PATH", "show_help", "get_options", "get_mitm_record_cmd",
	"get_and_remove_arg"
]


METHODS = ["getopt", "longopt", "stdin"]  # all available methods to test
FENCING_LIB_PATH = "../fence/agents/lib"  # path to fencing libs
DEVICES_PATH = "./devices.d"  # path to device directory
ACTIONS_PATH = "./actions.d"  # path to actions directory
MITM_LOGS_PATH = "./data/mitm-logs"  # path to mitm logs
MITM_PROXY_PATH = "../mitm/mitmproxy-0.1/build"  # path to mitm_proxy servers
BINMITM_COUNTERFILE = "./.counterfile"  # path to counter file for BINMITM
MITMPROXY_STARTUP_TIMEOUT = 1


class LibException(Exception):
	pass


# returns command for MITM_PROXY replay server
def get_mitm_replay_cmd(agent_config, log):
	if "replay_server_type" not in agent_config:
		raise LibException(
			"Option 'replay_server_type' is not defined in device config. "
			"It is required when agent_type = 'mitmproxy'"
		)

	script_path = os.path.join(
		MITM_PROXY_PATH,
		"scripts-2.7/mitmreplay_" + agent_config["replay_server_type"]
	)

	port = ""
	if "ipport" in agent_config["options"]:
		port = "-p " + agent_config["options"]["ipport"][0]

	cmd = "{script} -f {log} {port} {args}".format(
		script=script_path,
		log=log,
		port=port,
		args=agent_config.get("replay_server_args", "")
	)

	env = os.environ.copy()
	env["PYTHONPATH"] = os.path.join(MITM_PROXY_PATH, "lib/")

	return cmd, env


def get_mitm_record_cmd(agent_config, log, local_port):
	if "replay_server_type" not in agent_config:
		raise LibException(
			"Option 'replay_server_type' is not defined in device config. "
			"It is required when agent_type = 'mitmproxy'"
		)

	script_path = os.path.join(
		MITM_PROXY_PATH,
		"scripts-2.7/mitmproxy_" + agent_config["replay_server_type"]
	)

	host = ""
	if "ipport" in agent_config["options"]:
		host = "-H " + agent_config["options"]["ipaddr"][0]

	port = ""
	if "ipport" in agent_config["options"]:
		port = "-P " + agent_config["options"]["ipport"][0]

	cmd = "{script} -o {log} -p {local_port} {host} {port} {a1} {a2}".format(
		script=script_path,
		log=log,
		local_port=local_port,
		host=host,
		port=port,
		a1=agent_config.get("record_server_args", ""),
		a2=agent_config.get("replay_server_args", "")
	)

	env = os.environ.copy()
	env["PYTHONPATH"] = os.path.join(MITM_PROXY_PATH, "lib/")

	return cmd, env


# returns path to fence agent
def get_agent_path(agent):
	return os.path.join("../fence/agents/", agent[6:], agent)


# prepare agent command to run
def prepare_command(config, params="", method="getopt"):
	env = {"PYTHONPATH": FENCING_LIB_PATH}

	final_command = "python "

	if "agent_path" in config:
		final_command += config["agent_path"]
	else:
		final_command += get_agent_path(config["agent"])

	if params:
		final_command += " " + params + " "

	stdin_values = None

	for opt in config["options"]:
		if not isinstance(config["options"][opt], list) or not len(
				config["options"][opt]) >= 2:
			raise LibException(
				"Option '{0}' have to have at least value and longopt".format(
					opt
				)
			)

		value = config["options"][opt][0]
		has_value = value is not None
		if opt == "action":
			# ignore action as it is not part of fence device definition
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

	return final_command, stdin_values, env


def run_agent(command, stdin="", env_vars=None):
	if env_vars is None:
		env_vars = {}
	env = os.environ.copy()
	env.update(env_vars)

	logging.debug("Running: {cmd}".format(cmd=command))

	if stdin:
		logging.debug("STDIN: {0}".format(stdin))
	if env_vars:
		logging.debug("ENV: {0}".format(str(env_vars)))

	process = subprocess.Popen(
		shlex.split(command),
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		env=env
	)

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
	space = 30
	for o in avail_opt:
		args = "-{short}, --{long}{val}".format(
			short=avail_opt[o]["getopt"].strip(":"),
			long=avail_opt[o]["longopt"],
			val=(" <value>" if avail_opt[o]["getopt"].endswith(":") else "")
		)
		line = "\t{args}{spaces}{description}".format(
			args=args,
			spaces=(
				' ' * (space - len(args)) if space - len(args) > 0 else ' ' * 5
			),
			description=avail_opt[o]["description"])
		print line


# get options from command line parameters
def get_options(avail_opt):
	opt = {}
	for o in avail_opt.itervalues():  # set default values
		if "default" in o:
			opt["--" + o["longopt"]] = o["default"]

	if len(sys.argv) > 1:
		os.putenv("LANG", "C")
		os.putenv("LC_ALL", "C")

		getopt_string = ""
		longopt_list = []
		for k in avail_opt:
			getopt_string += avail_opt[k]["getopt"]
			long_opt = avail_opt[k]["longopt"] + (
				"=" if avail_opt[k]["getopt"].endswith(":") else ""
			)
			longopt_list.append(long_opt)

		try:
			old_opt, _ = getopt.gnu_getopt(
				sys.argv[1:], getopt_string, longopt_list
			)
		except getopt.GetoptError as error:
			logging.error("Parse error: " + str(error))
			show_help(avail_opt)
			sys.exit(1)

		# Transform short getopt to long one
		#####
		for o in dict(old_opt).keys():
			if o.startswith("--"):
				for x in avail_opt.keys():
					if (
						"longopt" in avail_opt[x] and
						"--" + avail_opt[x]["longopt"] == o
					):
						if avail_opt[x]["getopt"].endswith(":"):
							opt[o] = dict(old_opt)[o]
							if "list" in avail_opt[x]:
								opt[o] = opt[o].split(avail_opt[x]["list"])
						else:
							opt[o] = True
			else:
				for x in avail_opt.keys():
					if (
						x in avail_opt and
						"getopt" in avail_opt[x] and
						"longopt" in avail_opt[x] and
						(
							"-" + avail_opt[x]["getopt"] == o or
							"-" + avail_opt[x]["getopt"].rstrip(":") == o
						)
					):
						key = "--" + avail_opt[x]["longopt"]
						if avail_opt[x]["getopt"].endswith(":"):
							opt[key] = dict(old_opt)[o]
							if "list" in avail_opt[x]:
								opt[key] = opt[key].split(avail_opt[x]["list"])
						else:
							opt[key] = True
	return opt


def get_and_remove_arg(arg):
	logging.debug("Getting arg: {0}".format(arg))
	if arg in sys.argv:
		index = sys.argv.index(arg)
		sys.argv.remove(arg)
		if len(sys.argv) > index:
			value = sys.argv[index]
			sys.argv.remove(value)
			logging.debug("{arg}: {val}".format(arg=arg, val=value))
			return value
	return None


def start_mitm_server(cmd, env):
	logging.debug("Executing: {cmd}".format(cmd=cmd))
	try:
		# Try to start replay server
		process = subprocess.Popen(
			shlex.split(cmd),
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			env=env
		)
	except OSError as e:
		raise LibException(
			"Unable to start replay server: {0}".format(str(e))
		)

	# wait for replay server
	sleep(MITMPROXY_STARTUP_TIMEOUT)
	# check if replay server is running correctly
	if process.poll() is not None:
		pipe_stdout, pipe_stderr = process.communicate()
		process.stdout.close()
		process.stderr.close()
		logging.debug(
			"MITM server STDOUT:\n{out}".format(out=str(pipe_stdout))
		)
		logging.debug(
			"MITM server STDERR:\n{err}".format(err=str(pipe_stderr))
		)
		raise LibException("MITM server is not running correctly.")
	return process


def stop_mitm_server(process):
	if process:
		# if server is still alive after test, kill it
		if process.poll() is None:
			try:
				# race condition, process can exit between checking and
				# killing process
				process.kill()
			except Exception:
				pass
		pipe_stdout, pipe_stderr = process.communicate()
		process.stdout.close()
		process.stderr.close()
		logging.debug(
			"MITM server STDOUT:\n{out}".format(out=str(pipe_stdout))
		)
		logging.debug(
			"MITM server STDERR:\n{err}".format(err=str(pipe_stderr))
		)
