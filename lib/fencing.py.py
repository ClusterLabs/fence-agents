#!@PYTHON@ -tt

import sys, getopt, time, os, uuid, pycurl, stat
import pexpect, re, syslog
import logging
import subprocess
import threading
import shlex
import socket
import textwrap
import __main__

import itertools

RELEASE_VERSION = "@RELEASE_VERSION@"

__all__ = ['atexit_handler', 'check_input', 'process_input', 'all_opt', 'show_docs',
		'fence_login', 'fence_action', 'fence_logout']

EC_OK = 0
EC_GENERIC_ERROR = 1
EC_BAD_ARGS = 2
EC_LOGIN_DENIED = 3
EC_CONNECTION_LOST = 4
EC_TIMED_OUT = 5
EC_WAITING_ON = 6
EC_WAITING_OFF = 7
EC_STATUS = 8
EC_STATUS_HMC = 9
EC_PASSWORD_MISSING = 10
EC_INVALID_PRIVILEGES = 11
EC_FETCH_VM_UUID = 12

LOG_FORMAT = "%(asctime)-15s %(levelname)s: %(message)s"

all_opt = {
	"help"    : {
		"getopt" : "h",
		"longopt" : "help",
		"help" : "-h, --help                     Display this help and exit",
		"required" : "0",
		"shortdesc" : "Display help and exit",
		"order" : 55},
	"version" : {
		"getopt" : "V",
		"longopt" : "version",
		"help" : "-V, --version                  Display version information and exit",
		"required" : "0",
		"shortdesc" : "Display version information and exit",
		"order" : 54},
	"verbose" : {
		"getopt" : "v",
		"longopt" : "verbose",
		"help" : "-v, --verbose                  Verbose mode. "
			"Multiple -v flags can be stacked on the command line "
			"(e.g., -vvv) to increase verbosity.",
		"required" : "0",
		"order" : 51},
	"verbose_level" : {
		"getopt" : ":",
		"longopt" : "verbose-level",
		"type" : "integer",
		"help" : "--verbose-level                "
			"Level of debugging detail in output. Defaults to the "
			"number of --verbose flags specified on the command "
			"line, or to 1 if verbose=1 in a stonith device "
			"configuration (i.e., on stdin).",
                "required" : "0",
		"order" : 52},
	"debug" : {
		"getopt" : "D:",
		"longopt" : "debug-file",
		"help" : "-D, --debug-file=[debugfile]   Debugging to output file",
		"required" : "0",
		"shortdesc" : "Write debug information to given file",
		"order" : 53},
	"delay" : {
		"getopt" : ":",
		"longopt" : "delay",
		"type" : "second",
		"help" : "--delay=[seconds]              Wait X seconds before fencing is started",
		"required" : "0",
		"default" : "0",
		"order" : 200},
	"agent"   : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"web"    : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"force_on" : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"action" : {
		"getopt" : "o:",
		"longopt" : "action",
		"help" : "-o, --action=[action]          Action: status, reboot (default), off or on",
		"required" : "1",
		"shortdesc" : "Fencing action",
		"default" : "reboot",
		"order" : 1},
	"fabric_fencing" : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"ipaddr" : {
		"getopt" : "a:",
		"longopt" : "ip",
		"help" : "-a, --ip=[ip]                  IP address or hostname of fencing device",
		"required" : "1",
		"order" : 1},
	"ipport" : {
		"getopt" : "u:",
		"longopt" : "ipport",
		"type" : "integer",
		"help" : "-u, --ipport=[port]            TCP/UDP port to use for connection",
		"required" : "0",
		"shortdesc" : "TCP/UDP port to use for connection with device",
		"order" : 1},
	"login" : {
		"getopt" : "l:",
		"longopt" : "username",
		"help" : "-l, --username=[name]          Login name",
		"required" : "0",
		"order" : 1},
	"no_login" : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"no_password" : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"no_port" : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"no_status" : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"no_on" : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"no_off" : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"telnet" : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"diag" : {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"passwd" : {
		"getopt" : "p:",
		"longopt" : "password",
		"help" : "-p, --password=[password]      Login password or passphrase",
		"required" : "0",
		"order" : 1},
	"passwd_script" : {
		"getopt" : "S:",
		"longopt" : "password-script",
		"help" : "-S, --password-script=[script] Script to run to retrieve password",
		"required" : "0",
		"order" : 1},
	"identity_file" : {
		"getopt" : "k:",
		"longopt" : "identity-file",
		"help" : "-k, --identity-file=[filename] Identity file (private key) for SSH",
		"required" : "0",
		"order" : 1},
	"cmd_prompt" : {
		"getopt" : "c:",
		"longopt" : "command-prompt",
		"help" : "-c, --command-prompt=[prompt]  Force Python regex for command prompt",
		"required" : "0",
		"order" : 1},
	"secure" : {
		"getopt" : "x",
		"longopt" : "ssh",
		"help" : "-x, --ssh                      Use SSH connection",
		"required" : "0",
		"order" : 1},
	"ssh_options" : {
		"getopt" : ":",
		"longopt" : "ssh-options",
		"help" : "--ssh-options=[options]        SSH options to use",
		"required" : "0",
		"order" : 1},
	"ssl" : {
		"getopt" : "z",
		"longopt" : "ssl",
		"help" : "-z, --ssl                      Use SSL connection with verifying certificate",
		"required" : "0",
		"order" : 1},
	"ssl_insecure" : {
		"getopt" : "",
		"longopt" : "ssl-insecure",
		"help" : "--ssl-insecure                 Use SSL connection without verifying certificate",
		"required" : "0",
		"order" : 1},
	"ssl_secure" : {
		"getopt" : "",
		"longopt" : "ssl-secure",
		"help" : "--ssl-secure                   Use SSL connection with verifying certificate",
		"required" : "0",
		"order" : 1},
	"notls" : {
		"getopt" : "t",
		"longopt" : "notls",
		"help" : "-t, --notls                    "
				"Disable TLS negotiation and force SSL3.0. "
				"This should only be used for devices that do not support TLS1.0 and up.",
		"required" : "0",
		"order" : 1},
	"tls1.0" : {
		"getopt" : "",
		"longopt" : "tls1.0",
		"help" : "--tls1.0                       "
				"Disable TLS negotiation and force TLS1.0. "
				"This should only be used for devices that do not support TLS1.1 and up.",
		"required" : "0",
		"order" : 1},
	"port" : {
		"getopt" : "n:",
		"longopt" : "plug",
		"help" : "-n, --plug=[id]                "
				"Physical plug number on device, UUID or identification of machine",
		"required" : "1",
		"order" : 1},
	"switch" : {
		"getopt" : "s:",
		"longopt" : "switch",
		"help" : "-s, --switch=[id]              Physical switch number on device",
		"required" : "0",
		"order" : 1},
	"exec" : {
		"getopt" : "e:",
		"longopt" : "exec",
		"help" : "-e, --exec=[command]           Command to execute",
		"required" : "0",
		"order" : 1},
	"vmware_type" : {
		"getopt" : "d:",
		"longopt" : "vmware_type",
		"help" : "-d, --vmware_type=[type]       Type of VMware to connect",
		"required" : "0",
		"order" : 1},
	"vmware_datacenter" : {
		"getopt" : "s:",
		"longopt" : "vmware-datacenter",
		"help" : "-s, --vmware-datacenter=[dc]   VMWare datacenter filter",
		"required" : "0",
		"order" : 2},
	"snmp_version" : {
		"getopt" : "d:",
		"longopt" : "snmp-version",
		"help" : "-d, --snmp-version=[version]   Specifies SNMP version to use (1|2c|3)",
		"required" : "0",
		"shortdesc" : "Specifies SNMP version to use",
		"choices" : ["1", "2c", "3"],
		"order" : 1},
	"community" : {
		"getopt" : "c:",
		"longopt" : "community",
		"help" : "-c, --community=[community]    Set the community string",
		"required" : "0",
		"order" : 1},
	"snmp_auth_prot" : {
		"getopt" : "b:",
		"longopt" : "snmp-auth-prot",
		"help" : "-b, --snmp-auth-prot=[prot]    Set authentication protocol (MD5|SHA)",
		"required" : "0",
		"shortdesc" : "Set authentication protocol",
		"choices" : ["MD5", "SHA"],
		"order" : 1},
	"snmp_sec_level" : {
		"getopt" : "E:",
		"longopt" : "snmp-sec-level",
		"help" : "-E, --snmp-sec-level=[level]   "
				"Set security level (noAuthNoPriv|authNoPriv|authPriv)",
		"required" : "0",
		"shortdesc" : "Set security level",
		"choices" : ["noAuthNoPriv", "authNoPriv", "authPriv"],
		"order" : 1},
	"snmp_priv_prot" : {
		"getopt" : "B:",
		"longopt" : "snmp-priv-prot",
		"help" : "-B, --snmp-priv-prot=[prot]    Set privacy protocol (DES|AES)",
		"required" : "0",
		"shortdesc" : "Set privacy protocol",
		"choices" : ["DES", "AES"],
		"order" : 1},
	"snmp_priv_passwd" : {
		"getopt" : "P:",
		"longopt" : "snmp-priv-passwd",
		"help" : "-P, --snmp-priv-passwd=[pass]  Set privacy protocol password",
		"required" : "0",
		"order" : 1},
	"snmp_priv_passwd_script" : {
		"getopt" : "R:",
		"longopt" : "snmp-priv-passwd-script",
		"help" : "-R, --snmp-priv-passwd-script  Script to run to retrieve privacy password",
		"required" : "0",
		"order" : 1},
	"inet4_only" : {
		"getopt" : "4",
		"longopt" : "inet4-only",
		"help" : "-4, --inet4-only               Forces agent to use IPv4 addresses only",
		"required" : "0",
		"order" : 1},
	"inet6_only" : {
		"getopt" : "6",
		"longopt" : "inet6-only",
		"help" : "-6, --inet6-only               Forces agent to use IPv6 addresses only",
		"required" : "0",
		"order" : 1},
	"plug_separator" : {
		"getopt" : ":",
		"longopt" : "plug-separator",
		"help" : "--plug-separator=[char]        Separator for plug parameter when specifying more than 1 plug",
		"default" : ",",
		"required" : "0",
		"order" : 100},
	"separator" : {
		"getopt" : "C:",
		"longopt" : "separator",
		"help" : "-C, --separator=[char]         Separator for CSV created by 'list' operation",
		"default" : ",",
		"required" : "0",
		"order" : 100},
	"login_timeout" : {
		"getopt" : ":",
		"longopt" : "login-timeout",
		"type" : "second",
		"help" : "--login-timeout=[seconds]      Wait X seconds for cmd prompt after login",
		"default" : "5",
		"required" : "0",
		"order" : 200},
	"shell_timeout" : {
		"getopt" : ":",
		"longopt" : "shell-timeout",
		"type" : "second",
		"help" : "--shell-timeout=[seconds]      Wait X seconds for cmd prompt after issuing command",
		"default" : "3",
		"required" : "0",
		"order" : 200},
	"power_timeout" : {
		"getopt" : ":",
		"longopt" : "power-timeout",
		"type" : "second",
		"help" : "--power-timeout=[seconds]      Test X seconds for status change after ON/OFF",
		"default" : "20",
		"required" : "0",
		"order" : 200},
	"disable_timeout" : {
		"getopt" : ":",
		"longopt" : "disable-timeout",
		"help" : "--disable-timeout=[true/false]     Disable timeout (true/false) (default: true when run from Pacemaker 2.0+)",
		"required" : "0",
		"order" : 200},
	"power_wait" : {
		"getopt" : ":",
		"longopt" : "power-wait",
		"type" : "second",
		"help" : "--power-wait=[seconds]         Wait X seconds after issuing ON/OFF",
		"default" : "0",
		"required" : "0",
		"order" : 200},
	"stonith_status_sleep" : {
		"getopt" : ":",
		"longopt" : "stonith-status-sleep",
		"type" : "second",
		"help" : "--stonith-status-sleep=[seconds]   Sleep X seconds between status calls during a STONITH action",
		"default" : "1",
		"required" : "0",
		"order" : 200},
	"missing_as_off" : {
		"getopt" : "",
		"longopt" : "missing-as-off",
		"help" : "--missing-as-off               Missing port returns OFF instead of failure",
		"required" : "0",
		"order" : 200},
	"retry_on" : {
		"getopt" : ":",
		"longopt" : "retry-on",
		"type" : "integer",
		"help" : "--retry-on=[attempts]          Count of attempts to retry power on",
		"default" : "1",
		"required" : "0",
		"order" : 201},
	"session_url" : {
		"getopt" : "s:",
		"longopt" : "session-url",
		"help" : "-s, --session-url              URL to connect to XenServer on",
		"required" : "1",
		"order" : 1},
	"sudo" : {
		"getopt" : "",
		"longopt" : "use-sudo",
		"help" : "--use-sudo                     Use sudo (without password) when calling 3rd party software",
		"required" : "0",
		"order" : 205},
	"method" : {
		"getopt" : "m:",
		"longopt" : "method",
		"help" : "-m, --method=[method]          Method to fence (onoff|cycle) (Default: onoff)",
		"required" : "0",
		"shortdesc" : "Method to fence",
		"default" : "onoff",
		"choices" : ["onoff", "cycle"],
		"order" : 1},
	"telnet_path" : {
		"getopt" : ":",
		"longopt" : "telnet-path",
		"help" : "--telnet-path=[path]           Path to telnet binary",
		"required" : "0",
		"default" : "@TELNET_PATH@",
		"order": 300},
	"ssh_path" : {
		"getopt" : ":",
		"longopt" : "ssh-path",
		"help" : "--ssh-path=[path]              Path to ssh binary",
		"required" : "0",
		"default" : "@SSH_PATH@",
		"order": 300},
	"gnutlscli_path" : {
		"getopt" : ":",
		"longopt" : "gnutlscli-path",
		"help" : "--gnutlscli-path=[path]        Path to gnutls-cli binary",
		"required" : "0",
		"default" : "@GNUTLSCLI_PATH@",
		"order": 300},
	"sudo_path" : {
		"getopt" : ":",
		"longopt" : "sudo-path",
		"help" : "--sudo-path=[path]             Path to sudo binary",
		"required" : "0",
		"default" : "@SUDO_PATH@",
		"order": 300},
	"snmpwalk_path" : {
		"getopt" : ":",
		"longopt" : "snmpwalk-path",
		"help" : "--snmpwalk-path=[path]         Path to snmpwalk binary",
		"required" : "0",
		"default" : "@SNMPWALK_PATH@",
		"order" : 300},
	"snmpset_path" : {
		"getopt" : ":",
		"longopt" : "snmpset-path",
		"help" : "--snmpset-path=[path]          Path to snmpset binary",
		"required" : "0",
		"default" : "@SNMPSET_PATH@",
		"order" : 300},
	"snmpget_path" : {
		"getopt" : ":",
		"longopt" : "snmpget-path",
		"help" : "--snmpget-path=[path]          Path to snmpget binary",
		"required" : "0",
		"default" : "@SNMPGET_PATH@",
		"order" : 300},
	"snmp": {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"port_as_ip": {
		"getopt" : "",
		"longopt" : "port-as-ip",
		"help" : "--port-as-ip                   Make \"port/plug\" to be an alias to IP address",
		"required" : "0",
		"order" : 200},
	"on_target": {
		"getopt" : "",
		"help" : "",
		"order" : 1},
	"quiet": {
		"getopt" : "q",
		"longopt": "quiet",
		"help" : "-q, --quiet                    Disable logging to stderr. Does not affect --verbose or --debug-file or logging to syslog.",
		"required" : "0",
		"order" : 50}
}

# options which are added automatically if 'key' is encountered ("default" is always added)
DEPENDENCY_OPT = {
		"default" : ["help", "debug", "verbose", "verbose_level",
			 "version", "action", "agent", "power_timeout",
			 "shell_timeout", "login_timeout", "disable_timeout",
			 "power_wait", "stonith_status_sleep", "retry_on", "delay",
			 "plug_separator", "quiet"],
		"passwd" : ["passwd_script"],
		"sudo" : ["sudo_path"],
		"secure" : ["identity_file", "ssh_options", "ssh_path", "inet4_only", "inet6_only"],
		"telnet" : ["telnet_path"],
		"ipaddr" : ["ipport"],
		"port" : ["separator"],
		"ssl" : ["ssl_secure", "ssl_insecure", "gnutlscli_path"],
		"snmp" : ["snmp_auth_prot", "snmp_sec_level", "snmp_priv_prot", \
			"snmp_priv_passwd", "snmp_priv_passwd_script", "community", \
			"snmpset_path", "snmpget_path", "snmpwalk_path"]
	}

class fspawn(pexpect.spawn):
	def __init__(self, options, command, **kwargs):
		if sys.version_info[0] > 2:
			kwargs.setdefault('encoding', 'utf-8')
		logging.info("Running command: %s", command)
		pexpect.spawn.__init__(self, command, **kwargs)
		self.opt = options

	def log_expect(self, pattern, timeout):
		result = self.expect(pattern, timeout if timeout != 0 else None)
		logging.debug("Received: %s", self.before + self.after)
		return result

	def read_nonblocking(self, size, timeout):
		return pexpect.spawn.read_nonblocking(self, size=100, timeout=timeout if timeout != 0 else None)

	def send(self, message):
		logging.debug("Sent: %s", message)
		return pexpect.spawn.send(self, message)

	# send EOL according to what was detected in login process (telnet)
	def send_eol(self, message):
		return self.send(message + self.opt["eol"])

def frun(command, timeout=30, withexitstatus=False, events=None,
	 extra_args=None, logfile=None, cwd=None, env=None, **kwargs):
	if sys.version_info[0] > 2:
		kwargs.setdefault('encoding', 'utf-8')
	return pexpect.run(command, timeout=timeout if timeout != 0 else None,
			   withexitstatus=withexitstatus, events=events,
			   extra_args=extra_args, logfile=logfile, cwd=cwd,
			   env=env, **kwargs)

def atexit_handler():
	try:
		sys.stdout.close()
		os.close(1)
	except IOError:
		logging.error("%s failed to close standard output\n", sys.argv[0])
		sys.exit(EC_GENERIC_ERROR)

def _add_dependency_options(options):
	## Add also options which are available for every fence agent
	added_opt = []
	for opt in options + ["default"]:
		if opt in DEPENDENCY_OPT:
			added_opt.extend([y for y in DEPENDENCY_OPT[opt] if options.count(y) == 0])

	if not "port" in (options + added_opt) and \
			not "nodename" in (options + added_opt) and \
			"ipaddr" in (options + added_opt):
		added_opt.append("port_as_ip")
		all_opt["port"]["help"] = "-n, --plug=[ip]                IP address or hostname of fencing device " \
			"(together with --port-as-ip)"

	return added_opt

def fail_usage(message="", stop=True):
	if len(message) > 0:
		logging.error("%s\n", message)
	if stop:
		logging.error("Please use '-h' for usage\n")
		sys.exit(EC_GENERIC_ERROR)

def fail(error_code, stop=True):
	message = {
		EC_GENERIC_ERROR : "Failed: Generic error",
		EC_LOGIN_DENIED : "Unable to connect/login to fencing device",
		EC_CONNECTION_LOST : "Connection lost",
		EC_TIMED_OUT : "Connection timed out",
		EC_WAITING_ON : "Failed: Timed out waiting to power ON",
		EC_WAITING_OFF : "Failed: Timed out waiting to power OFF",
		EC_STATUS : "Failed: Unable to obtain correct plug status or plug is not available",
		EC_STATUS_HMC : "Failed: Either unable to obtain correct plug status, "
				"partition is not available or incorrect HMC version used",
		EC_PASSWORD_MISSING : "Failed: You have to set login password",
		EC_INVALID_PRIVILEGES : "Failed: The user does not have the correct privileges to do the requested action.",
		EC_FETCH_VM_UUID : "Failed: Can not find VM UUID by its VM name given in the <plug> parameter."

	}[error_code] + "\n"
	logging.error("%s\n", message)
	if stop:
		sys.exit(EC_GENERIC_ERROR)

def usage(avail_opt):
	print("Usage:")
	print("\t" + os.path.basename(sys.argv[0]) + " [options]")
	print("Options:")

	sorted_list = [(key, all_opt[key]) for key in avail_opt]
	sorted_list.sort(key=lambda x: x[1]["order"])

	for key, value in sorted_list:
		if len(value["help"]) != 0:
			print("   " + _join_wrap([value["help"]], first_indent=3))

def metadata(options, avail_opt, docs, agent_name=os.path.basename(sys.argv[0])):
	# avail_opt has to be unique, if there are duplicities then they should be removed
	sorted_list = [(key, all_opt[key]) for key in list(set(avail_opt)) if "longopt" in all_opt[key]]
	# Find keys that are going to replace inconsistent names
	mapping = dict([(opt["longopt"].replace("-", "_"), key) for (key, opt) in sorted_list if (key != opt["longopt"].replace("-", "_"))])
	new_options = [(key, all_opt[mapping[key]]) for key in mapping]
	sorted_list.extend(new_options)

	sorted_list.sort(key=lambda x: (x[1]["order"], x[0]))

	if options["--action"] == "metadata":
               docs["longdesc"] = re.sub(r"\\f[BPIR]|\.P|\.TP|\.br\n", r"", docs["longdesc"])

	print("<?xml version=\"1.0\" ?>")
	print("<resource-agent name=\"" + agent_name + \
			"\" shortdesc=\"" + docs["shortdesc"] + "\" >")
	for (symlink, desc) in docs.get("symlink", []):
		print("<symlink name=\"" + symlink + "\" shortdesc=\"" + desc + "\"/>")
	print("<longdesc>" + docs["longdesc"] + "</longdesc>")
	print("<vendor-url>" + docs["vendorurl"] + "</vendor-url>")
	print("<parameters>")
	for (key, opt) in sorted_list:
		info = ""
		if key in all_opt:
			if key != all_opt[key].get('longopt', key).replace("-", "_"):
				info = "deprecated=\"1\""
		else:
			info = "obsoletes=\"%s\"" % (mapping.get(key))

		if "help" in opt and len(opt["help"]) > 0:
			if info != "":
				info = " " + info
			print("\t<parameter name=\"" + key + "\" unique=\"0\" required=\"" + opt["required"] + "\"" + info + ">")

			default = ""
			if "default" in opt:
				default = "default=\"" + _encode_html_entities(str(opt["default"])) + "\" "

			mixed = opt["help"]
			## split it between option and help text
			res = re.compile(r"^(.*?--\S+)\s+", re.IGNORECASE | re.S).search(mixed)
			if None != res:
				mixed = res.group(1)
			mixed = _encode_html_entities(mixed)

			if not "shortdesc" in opt:
				shortdesc = re.sub(r".*\s\s+", r"", opt["help"][31:])
			else:
				shortdesc = opt["shortdesc"]

			print("\t\t<getopt mixed=\"" + mixed + "\" />")
			if "choices" in opt:
				print("\t\t<content type=\"select\" "+default+" >")
				for choice in opt["choices"]:
					print("\t\t\t<option value=\"%s\" />" % (choice))
				print("\t\t</content>")
			elif opt["getopt"].count(":") > 0:
				t = opt.get("type", "string")
				print("\t\t<content type=\"%s\" " % (t) +default+" />")
			else:
				print("\t\t<content type=\"boolean\" "+default+" />")
			print("\t\t<shortdesc lang=\"en\">" + shortdesc + "</shortdesc>")
			print("\t</parameter>")
	print("</parameters>")
	print("<actions>")

	(available_actions, _) = _get_available_actions(avail_opt)

	if "on" in available_actions:
		available_actions.remove("on")
		on_target = ' on_target="1"' if avail_opt.count("on_target") else ''
		print("\t<action name=\"on\"%s automatic=\"%d\"/>" % (on_target, avail_opt.count("fabric_fencing")))

	for action in available_actions:
		print("\t<action name=\"%s\" />" % (action))
	print("</actions>")
	print("</resource-agent>")

def process_input(avail_opt):
	avail_opt.extend(_add_dependency_options(avail_opt))

	# @todo: this should be put elsewhere?
	os.putenv("LANG", "C")
	os.putenv("LC_ALL", "C")

	if "port_as_ip" in avail_opt:
		avail_opt.append("port")

	if len(sys.argv) > 1:
		opt = _parse_input_cmdline(avail_opt)
	else:
		opt = _parse_input_stdin(avail_opt)

	if "--port-as-ip" in opt and "--plug" in opt:
		opt["--ip"] = opt["--plug"]

	return opt

##
## This function checks input and answers if we want to have same answers
## in each of the fencing agents. It looks for possible errors and run
## password script to set a correct password
######
def check_input(device_opt, opt, other_conditions = False):
	device_opt.extend(_add_dependency_options(device_opt))

	options = dict(opt)
	options["device_opt"] = device_opt

	_update_metadata(options)
	options = _set_default_values(options)
	options["--action"] = options["--action"].lower()

	## In special cases (show help, metadata or version) we don't need to check anything
	#####
	# OCF compatibility
	if options["--action"] == "meta-data":
		options["--action"] = "metadata"

	if options["--action"] in ["metadata", "manpage"] or any(k in options for k in ("--help", "--version")):
		return options

	try:
		options["--verbose-level"] = int(options["--verbose-level"])
	except ValueError:
		options["--verbose-level"] = -1

	if options["--verbose-level"] < 0:
		logging.warning("Parse error: Option 'verbose_level' must "
				"be an integer greater than or equal to 0. "
				"Setting verbose_level to 0.")
		options["--verbose-level"] = 0

	if options["--verbose-level"] == 0 and "--verbose" in options:
		logging.warning("Parse error: Ignoring option 'verbose' "
				"because it conflicts with verbose_level=0")
		del options["--verbose"]

	if options["--verbose-level"] > 0:
		# Ensure verbose key exists
		options["--verbose"] = 1
	
	if "--verbose" in options:
		logging.getLogger().setLevel(logging.DEBUG)

	formatter = logging.Formatter(LOG_FORMAT)

	## add logging to syslog
	logging.getLogger().addHandler(SyslogLibHandler())
	if "--quiet" not in options:
		## add logging to stderr
		stderrHandler = logging.StreamHandler(sys.stderr)
		stderrHandler.setFormatter(formatter)
		logging.getLogger().addHandler(stderrHandler)

	(acceptable_actions, _) = _get_available_actions(device_opt)

	if 1 == device_opt.count("fabric_fencing"):
		acceptable_actions.extend(["enable", "disable"])

	if 0 == acceptable_actions.count(options["--action"]):
		fail_usage("Failed: Unrecognised action '" + options["--action"] + "'")

	## Compatibility layer
	#####
	if options["--action"] == "enable":
		options["--action"] = "on"
	if options["--action"] == "disable":
		options["--action"] = "off"


	if options["--action"] == "validate-all" and not other_conditions:
		if not _validate_input(options, False):
			fail_usage("validate-all failed")
		sys.exit(EC_OK)
	else:
		_validate_input(options, True)

	if "--debug-file" in options:
		try:
			debug_file = logging.FileHandler(options["--debug-file"])
			debug_file.setLevel(logging.DEBUG)
			debug_file.setFormatter(formatter)
			logging.getLogger().addHandler(debug_file)
		except IOError:
			logging.error("Unable to create file %s", options["--debug-file"])
			fail_usage("Failed: Unable to create file " + options["--debug-file"])

	if "--snmp-priv-passwd-script" in options:
		options["--snmp-priv-passwd"] = os.popen(options["--snmp-priv-passwd-script"]).read().rstrip()

	if "--password-script" in options:
		options["--password"] = os.popen(options["--password-script"]).read().rstrip()

	if "--ssl-secure" in options or "--ssl-insecure" in options:
		options["--ssl"] = ""

	if "--ssl" in options and "--ssl-insecure" not in options:
		options["--ssl-secure"] = ""

	if os.environ.get("PCMK_service") == "pacemaker-fenced" and "--disable-timeout" not in options:
		options["--disable-timeout"] = "1"

	if options.get("--disable-timeout", "").lower() in ["1", "yes", "on", "true"]:
		options["--power-timeout"] = options["--shell-timeout"] = options["--login-timeout"] = 0

	return options

## Obtain a power status from possibly more than one plug
##	"on" is returned if at least one plug is ON
######
def get_multi_power_fn(connection, options, get_power_fn):
	status = "off"
	plugs = options["--plugs"] if "--plugs" in options else [""]

	for plug in plugs:
		try:
			options["--uuid"] = str(uuid.UUID(plug))
		except ValueError:
			pass
		except KeyError:
			pass

		options["--plug"] = plug
		plug_status = get_power_fn(connection, options)
		if plug_status != "off":
			status = plug_status

	return status

def async_set_multi_power_fn(connection, options, set_power_fn, get_power_fn, retry_attempts):
	plugs = options["--plugs"] if "--plugs" in options else [""]

	for _ in range(retry_attempts):
		for plug in plugs:
			try:
				options["--uuid"] = str(uuid.UUID(plug))
			except ValueError:
				pass
			except KeyError:
				pass

			options["--plug"] = plug
			set_power_fn(connection, options)
			time.sleep(int(options["--power-wait"]))

		for _ in itertools.count(1):
			if get_multi_power_fn(connection, options, get_power_fn) != options["--action"]:
				time.sleep(int(options["--stonith-status-sleep"]))
			else:
				return True

			if int(options["--power-timeout"]) > 0 and _ >= int(options["--power-timeout"]):
				break

	return False

def sync_set_multi_power_fn(connection, options, sync_set_power_fn, retry_attempts):
	success = True
	plugs = options["--plugs"] if "--plugs" in options else [""]

	for plug in plugs:
		try:
			options["--uuid"] = str(uuid.UUID(plug))
		except ValueError:
			pass
		except KeyError:
			pass

		options["--plug"] = plug
		for retry in range(retry_attempts):
			if sync_set_power_fn(connection, options):
				break
			if retry == retry_attempts-1:
				success = False
		time.sleep(int(options["--power-wait"]))

	return success


def set_multi_power_fn(connection, options, set_power_fn, get_power_fn, sync_set_power_fn, retry_attempts=1):

	if set_power_fn != None:
		if get_power_fn != None:
			return async_set_multi_power_fn(connection, options, set_power_fn, get_power_fn, retry_attempts)
	elif sync_set_power_fn != None:
		return sync_set_multi_power_fn(connection, options, sync_set_power_fn, retry_attempts)

	return False

def multi_reboot_cycle_fn(connection, options, reboot_cycle_fn, retry_attempts=1):
	success = True
	plugs = options["--plugs"] if "--plugs" in options else [""]

	for plug in plugs:
		try:
			options["--uuid"] = str(uuid.UUID(plug))
		except ValueError:
			pass
		except KeyError:
			pass

		options["--plug"] = plug
		for retry in range(retry_attempts):
			if reboot_cycle_fn(connection, options):
				break
			if retry == retry_attempts-1:
				success = False
		time.sleep(int(options["--power-wait"]))

	return success

def show_docs(options, docs=None):
	device_opt = options["device_opt"]

	if docs == None:
		docs = {}
		docs["shortdesc"] = "Fence agent"
		docs["longdesc"] = ""

	if "--help" in options:
		usage(device_opt)
		sys.exit(0)

	if options.get("--action", "") in ["metadata", "manpage"]:
		if options["--action"] == "metadata" or "agent_name" not in docs:
			agent_name=os.path.basename(sys.argv[0])
		else:
			agent_name=docs["agent_name"]


		if "port_as_ip" in device_opt:
			device_opt.remove("separator")
		metadata(options, device_opt, docs, agent_name)
		sys.exit(0)

	if "--version" in options:
		print(RELEASE_VERSION)
		sys.exit(0)

def fence_action(connection, options, set_power_fn, get_power_fn, get_outlet_list=None, reboot_cycle_fn=None, sync_set_power_fn=None):
	result = EC_OK

	try:
		if "--plug" in options:
			options["--plugs"] = options["--plug"].split(options["--plug-separator"])

		## Process options that manipulate fencing device
		#####
		if (options["--action"] in ["list", "list-status"]) or \
			((options["--action"] == "monitor") and 1 == options["device_opt"].count("port") and \
			0 == options["device_opt"].count("port_as_ip")):

			if 0 == options["device_opt"].count("port"):
				print("N/A")
			elif get_outlet_list == None:
				## @todo: exception?
				## This is just temporal solution, we will remove default value
				## None as soon as all existing agent will support this operation
				print("NOTICE: List option is not working on this device yet")
			else:
				options["--original-action"] = options["--action"]
				options["--action"] = "list"
				outlets = get_outlet_list(connection, options)
				options["--action"] = options["--original-action"]
				del options["--original-action"]

				## keys can be numbers (port numbers) or strings (names of VM, UUID)
				for outlet_id in list(outlets.keys()):
					(alias, status) = outlets[outlet_id]
					if status is None or (not status.upper() in ["ON", "OFF"]):
						status = "UNKNOWN"
						status = status.upper()

					if options["--action"] == "list":
						try:
							print("{}{}{}".format(outlet_id, options["--separator"], alias))
						except UnicodeEncodeError as e:
							print("{}{}{}".format(outlet_id, options["--separator"], alias).encode("utf-8"))
					elif options["--action"] == "list-status":
						try:
							print("{}{}{}{}{}".format(outlet_id, options["--separator"], alias, options["--separator"], status))
						except UnicodeEncodeError as e:
							print("{}{}{}{}{}".format(outlet_id, options["--separator"], alias, options["--separator"], status).encode("utf-8"))

			return result

		if options["--action"] == "monitor" and not "port" in options["device_opt"] and "no_status" in options["device_opt"]:
			# Unable to do standard monitoring because 'status' action is not available
			return result

		status = None
		if not "no_status" in options["device_opt"]:
			status = get_multi_power_fn(connection, options, get_power_fn)
			if status != "on" and status != "off":
				fail(EC_STATUS)

		if options["--action"] == status:
			if not (status == "on" and "force_on" in options["device_opt"]):
				print("Success: Already %s" % (status.upper()))
				return result

		if options["--action"] == "on":
			if set_multi_power_fn(connection, options, set_power_fn, get_power_fn, sync_set_power_fn, 1 + int(options["--retry-on"])):
				print("Success: Powered ON")
			else:
				fail(EC_WAITING_ON)
		elif options["--action"] == "off":
			if set_multi_power_fn(connection, options, set_power_fn, get_power_fn, sync_set_power_fn):
				print("Success: Powered OFF")
			else:
				fail(EC_WAITING_OFF)
		elif options["--action"] == "reboot":
			power_on = False
			if options.get("--method", "").lower() == "cycle" and reboot_cycle_fn is not None:
				try:
					power_on = multi_reboot_cycle_fn(connection, options, reboot_cycle_fn, 1 + int(options["--retry-on"]))
				except Exception as ex:
					# an error occured during reboot action
					logging.warning("%s", str(ex))

				if not power_on:
					fail(EC_TIMED_OUT)

			else:
				if status != "off":
					options["--action"] = "off"
					if not set_multi_power_fn(connection, options, set_power_fn, get_power_fn, sync_set_power_fn):
						fail(EC_WAITING_OFF)

				options["--action"] = "on"

				try:
					power_on = set_multi_power_fn(connection, options, set_power_fn, get_power_fn, sync_set_power_fn, int(options["--retry-on"]))
				except Exception as ex:
					# an error occured during power ON phase in reboot
					# fence action was completed succesfully even in that case
					logging.warning("%s", str(ex))

				# switch back to original action for the case it is used lateron
				options["--action"] = "reboot"

			if power_on == False:
				# this should not fail as node was fenced succesfully
				logging.error('Timed out waiting to power ON\n')

			print("Success: Rebooted")
		elif options["--action"] == "status":
			print("Status: " + status.upper())
			if status.upper() == "OFF":
				result = 2
		elif options["--action"] == "monitor":
			pass
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)
	except pycurl.error as ex:
		logging.error("%s\n", str(ex))
		fail(EC_TIMED_OUT)
	except socket.timeout as ex:
		logging.error("%s\n", str(ex))
		fail(EC_TIMED_OUT)

	return result

def fence_login(options, re_login_string=r"(login\s*: )|((?!Last )Login Name:  )|(username: )|(User Name :)"):
	run_delay(options)

	if "eol" not in options:
		options["eol"] = "\r\n"

	if "--command-prompt" in options and type(options["--command-prompt"]) is not list:
		options["--command-prompt"] = [options["--command-prompt"]]

	try:
		if "--ssl" in options:
			conn = _open_ssl_connection(options)
		elif "--ssh" in options and "--identity-file" not in options:
			conn = _login_ssh_with_password(options, re_login_string)
		elif "--ssh" in options and "--identity-file" in options:
			conn = _login_ssh_with_identity_file(options)
		else:
			conn = _login_telnet(options, re_login_string)
	except pexpect.EOF as exception:
		logging.debug("%s", str(exception))
		fail(EC_LOGIN_DENIED)
	except pexpect.TIMEOUT as exception:
		logging.debug("%s", str(exception))
		fail(EC_LOGIN_DENIED)
	return conn

def is_executable(path):
	if os.path.exists(path):
		stats = os.stat(path)
		if stat.S_ISREG(stats.st_mode) and os.access(path, os.X_OK):
			return True
	return False

def run_commands(options, commands, timeout=None, env=None, log_command=None):
	# inspired by psutils.wait_procs (BSD License)
	def check_gone(proc, timeout):
		try:
			returncode = proc.wait(timeout=timeout)
		except subprocess.TimeoutExpired:
			pass
		else:
			if returncode is not None or not proc.is_running():
				proc.returncode = returncode
				gone.add(proc)

	if timeout is None and "--power-timeout" in options:
		timeout = options["--power-timeout"]
	if timeout == 0:
		timeout = None
	if timeout is not None:
		timeout = float(timeout)

	time_start = time.time()
	procs = []
	status = None
	pipe_stdout = ""
	pipe_stderr = ""

	for command in commands:
		logging.info("Executing: %s\n", log_command or command)

		try:
			process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
					# decodes newlines and in python3 also converts bytes to str
					universal_newlines=(sys.version_info[0] > 2))
		except OSError:
			fail_usage("Unable to run %s\n" % command)

		procs.append(process)

	gone = set()
	alive = set(procs)

	while True:
		if alive:
			max_timeout = 2.0 / len(alive)
			for proc in alive:
				if timeout is not None:
					if time.time()-time_start >= timeout:
						# quickly go over the rest
						max_timeout = 0
				check_gone(proc, max_timeout)
			alive = alive - gone

		if not alive:
			break

		if time.time()-time_start < 5.0:
			# give it at least 5s to get a complete answer
			# afterwards we're OK with a quorate answer
			continue

		if len(gone) > len(alive):
			good_cnt = 0
			for proc in gone:
				if proc.returncode == 0:
					good_cnt += 1
			# a positive result from more than half is fine
			if good_cnt > len(procs)/2:
				break

		if timeout is not None:
			if time.time() - time_start >= timeout:
				logging.debug("Stop waiting after %s\n", str(timeout))
				break

	logging.debug("Done: %d gone, %d alive\n", len(gone), len(alive))

	for proc in gone:
		if (status != 0):
			status = proc.returncode
		# hand over the best status we have
		# but still collect as much stdout/stderr feedback
		# avoid communicate as we know already process
		# is gone and it seems to block when there
		# are D state children we don't get rid off
		os.set_blocking(proc.stdout.fileno(), False)
		os.set_blocking(proc.stderr.fileno(), False)
		try:
			pipe_stdout += proc.stdout.read()
		except:
			pass
		try:
			pipe_stderr += proc.stderr.read()
		except:
			pass
		proc.stdout.close()
		proc.stderr.close()

	for proc in alive:
		proc.kill()

	if status is None:
		fail(EC_TIMED_OUT, stop=(int(options.get("retry", 0)) < 1))
		status = EC_TIMED_OUT
		pipe_stdout = ""
		pipe_stderr = "timed out"

	logging.debug("%s %s %s\n", str(status), str(pipe_stdout), str(pipe_stderr))

	return (status, pipe_stdout, pipe_stderr)

def run_command(options, command, timeout=None, env=None, log_command=None):
	if timeout is None and "--power-timeout" in options:
		timeout = options["--power-timeout"]
	if timeout is not None:
		timeout = float(timeout)

	logging.info("Executing: %s\n", log_command or command)

	try:
		process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
				# decodes newlines and in python3 also converts bytes to str
				universal_newlines=(sys.version_info[0] > 2))
	except OSError:
		fail_usage("Unable to run %s\n" % command)

	thread = threading.Thread(target=process.wait)
	thread.start()
	thread.join(timeout if timeout else None)
	if thread.is_alive():
		process.kill()
		fail(EC_TIMED_OUT, stop=(int(options.get("retry", 0)) < 1))

	status = process.wait()

	(pipe_stdout, pipe_stderr) = process.communicate()
	process.stdout.close()
	process.stderr.close()

	logging.debug("%s %s %s\n", str(status), str(pipe_stdout), str(pipe_stderr))

	return (status, pipe_stdout, pipe_stderr)

def run_delay(options, reserve=0, result=0):
	## Delay is important for two-node clusters fencing
	## but we do not need to delay 'status' operations
	## and get us out quickly if we already know that we are gonna fail
	## still wanna do something right before fencing? - reserve some time
	if options["--action"] in ["off", "reboot"] \
		and options["--delay"] != "0" \
		and result == 0 \
		and reserve >= 0:
		time_left = 1 + int(options["--delay"]) - (time.time() - run_delay.time_start) - reserve
		if time_left > 0:
			logging.info("Delay %d second(s) before logging in to the fence device", time_left)
			time.sleep(time_left)
# mark time when fence-agent is started
run_delay.time_start = time.time()

def fence_logout(conn, logout_string, sleep=0):
	# Logout is not required part of fencing but we should attempt to do it properly
	# In some cases our 'exit' command is faster and we can not close connection as it
	# was already closed by fencing device
	try:
		conn.send_eol(logout_string)
		time.sleep(sleep)
		conn.close()
	except OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass

def source_env(env_file):
    # POSIX: name shall not contain '=', value doesn't contain '\0'
    output = subprocess.check_output("source {} && env -0".format(env_file), shell=True,
                          executable="/bin/sh")
    # replace env
    os.environ.clear()
    os.environ.update(line.partition('=')[::2] for line in output.decode("utf-8").split('\0') if not re.match(r"^\s*$", line))

# Convert array of format [[key1, value1], [key2, value2], ... [keyN, valueN]] to dict, where key is
# in format a.b.c.d...z and returned dict has key only z
def array_to_dict(array):
	return dict([[x[0].split(".")[-1], x[1]] for x in array])

## Own logger handler that uses old-style syslog handler as otherwise everything is sourced
## from /dev/syslog
class SyslogLibHandler(logging.StreamHandler):
	"""
	A handler class that correctly push messages into syslog
	"""
	def emit(self, record):
		syslog_level = {
			logging.CRITICAL:syslog.LOG_CRIT,
			logging.ERROR:syslog.LOG_ERR,
			logging.WARNING:syslog.LOG_WARNING,
			logging.INFO:syslog.LOG_INFO,
			logging.DEBUG:syslog.LOG_DEBUG,
			logging.NOTSET:syslog.LOG_DEBUG,
		}[record.levelno]

		msg = self.format(record)

		# syslos.syslog can not have 0x00 character inside or exception is thrown
		syslog.syslog(syslog_level, msg.replace("\x00", "\n"))
		return

def _open_ssl_connection(options):
	gnutls_opts = ""
	ssl_opts = ""

	if "--notls" in options:
		gnutls_opts = "--priority \"NORMAL:-VERS-TLS1.2:-VERS-TLS1.1:-VERS-TLS1.0:+VERS-SSL3.0\""
	elif "--tls1.0" in options:
		gnutls_opts = "--priority \"NORMAL:-VERS-TLS1.2:-VERS-TLS1.1:+VERS-TLS1.0:%LATEST_RECORD_VERSION\""

	# --ssl is same as the --ssl-secure; it means we want to verify certificate in these cases
	if "--ssl-insecure" in options:
		ssl_opts = "--insecure"

	command = '%s %s %s --crlf -p %s %s' % \
		(options["--gnutlscli-path"], gnutls_opts, ssl_opts, options["--ipport"], options["--ip"])
	try:
		conn = fspawn(options, command)
	except pexpect.ExceptionPexpect as ex:
		logging.error("%s\n", str(ex))
		sys.exit(EC_GENERIC_ERROR)

	return conn

def _login_ssh_with_identity_file(options):
	if "--inet6-only" in options:
		force_ipvx = "-6 "
	elif "--inet4-only" in options:
		force_ipvx = "-4 "
	else:
		force_ipvx = ""

	command = '%s %s %s@%s -i %s -p %s' % \
		(options["--ssh-path"], force_ipvx, options["--username"], options["--ip"], \
		options["--identity-file"], options["--ipport"])
	if "--ssh-options" in options:
		command += ' ' + options["--ssh-options"]

	conn = fspawn(options, command)

	result = conn.log_expect(["Enter passphrase for key '" + options["--identity-file"] + "':", \
		"Are you sure you want to continue connecting (yes/no)?"] + \
		options["--command-prompt"], int(options["--login-timeout"]))
	if result == 1:
		conn.sendline("yes")
		result = conn.log_expect(
			["Enter passphrase for key '" + options["--identity-file"]+"':"] + \
			options["--command-prompt"], int(options["--login-timeout"]))
	if result == 0:
		if "--password" in options:
			conn.sendline(options["--password"])
			conn.log_expect(options["--command-prompt"], int(options["--login-timeout"]))
		else:
			fail_usage("Failed: You have to enter passphrase (-p) for identity file")

	return conn

def _login_telnet(options, re_login_string):
	re_login = re.compile(re_login_string, re.IGNORECASE)
	re_pass = re.compile(r"(password)|(pass phrase)", re.IGNORECASE)

	conn = fspawn(options, options["--telnet-path"])
	conn.send("set binary\n")
	conn.send("open %s -%s\n"%(options["--ip"], options["--ipport"]))

	conn.log_expect(re_login, int(options["--login-timeout"]))
	conn.send_eol(options["--username"])

	## automatically change end of line separator
	screen = conn.read_nonblocking(size=100, timeout=int(options["--shell-timeout"]))
	if re_login.search(screen) != None:
		options["eol"] = "\n"
		conn.send_eol(options["--username"])
		conn.log_expect(re_pass, int(options["--login-timeout"]))
	elif re_pass.search(screen) == None:
		conn.log_expect(re_pass, int(options["--shell-timeout"]))

	try:
		conn.send_eol(options["--password"])
		valid_password = conn.log_expect([re_login] + \
				options["--command-prompt"], int(options["--shell-timeout"]))
		if valid_password == 0:
			## password is invalid or we have to change EOL separator
			options["eol"] = "\r"
			conn.send_eol("")
			screen = conn.read_nonblocking(size=100, timeout=int(options["--shell-timeout"]))
			## after sending EOL the fence device can either show 'Login' or 'Password'
			if re_login.search(conn.after + screen) != None:
				conn.send_eol("")
			conn.send_eol(options["--username"])
			conn.log_expect(re_pass, int(options["--login-timeout"]))
			conn.send_eol(options["--password"])
			conn.log_expect(options["--command-prompt"], int(options["--login-timeout"]))
	except KeyError:
		fail(EC_PASSWORD_MISSING)

	return conn

def _login_ssh_with_password(options, re_login_string):
	re_login = re.compile(re_login_string, re.IGNORECASE)
	re_pass = re.compile(r"(password)|(pass phrase)", re.IGNORECASE)

	if "--inet6-only" in options:
		force_ipvx = "-6 "
	elif "--inet4-only" in options:
		force_ipvx = "-4 "
	else:
		force_ipvx = ""

	command = '%s %s %s@%s -p %s -o PubkeyAuthentication=no' % \
			(options["--ssh-path"], force_ipvx, options["--username"], options["--ip"], options["--ipport"])
	if "--ssh-options" in options:
		command += ' ' + options["--ssh-options"]

	conn = fspawn(options, command)

	if "telnet_over_ssh" in options:
		# This is for stupid ssh servers (like ALOM) which behave more like telnet
		# (ignore name and display login prompt)
		result = conn.log_expect( \
				[re_login, "Are you sure you want to continue connecting (yes/no)?"],
				int(options["--login-timeout"]))
		if result == 1:
			conn.sendline("yes") # Host identity confirm
			conn.log_expect(re_login, int(options["--login-timeout"]))

		conn.sendline(options["--username"])
		conn.log_expect(re_pass, int(options["--login-timeout"]))
	else:
		result = conn.log_expect( \
				["ssword:", "Are you sure you want to continue connecting (yes/no)?"],
				int(options["--login-timeout"]))
		if result == 1:
			conn.sendline("yes")
			conn.log_expect("ssword:", int(options["--login-timeout"]))

	conn.sendline(options["--password"])
	conn.log_expect(options["--command-prompt"], int(options["--login-timeout"]))

	return conn

#
# To update metadata, we change values in all_opt
def _update_metadata(options):
	device_opt = options["device_opt"]

	if device_opt.count("login") and device_opt.count("no_login") == 0:
		all_opt["login"]["required"] = "1"
	else:
		all_opt["login"]["required"] = "0"

	if device_opt.count("port_as_ip"):
		all_opt["ipaddr"]["required"] = "0"
		all_opt["port"]["required"] = "0"

	(available_actions, default_value) = _get_available_actions(device_opt)
	all_opt["action"]["default"] = default_value

	actions_with_default = \
			[x if not x == all_opt["action"]["default"] else x + " (default)" for x in available_actions]
	all_opt["action"]["help"] = \
			"-o, --action=[action]          Action: %s" % (_join_wrap(actions_with_default, last_separator=" or "))

	if device_opt.count("ipport"):
		default_value = None
		default_string = None

		if "default" in all_opt["ipport"]:
			default_value = all_opt["ipport"]["default"]
		elif device_opt.count("web") and device_opt.count("ssl"):
			default_value = "80"
			default_string = "(default 80, 443 if --ssl option is used)"
		elif device_opt.count("telnet") and device_opt.count("secure"):
			default_value = "23"
			default_string = "(default 23, 22 if --ssh option is used)"
		else:
			tcp_ports = {"community" : "161", "secure" : "22", "telnet" : "23", "web" : "80", "ssl" : "443"}
			# all cases where next command returns multiple results are covered by previous blocks
			protocol = [x for x in ["community", "secure", "ssl", "web", "telnet"] if device_opt.count(x)][0]
			default_value = tcp_ports[protocol]

		if default_string is None:
			all_opt["ipport"]["help"] = "-u, --ipport=[port]            TCP/UDP port to use (default %s)" % \
					(default_value)
		else:
			all_opt["ipport"]["help"] = "-u, --ipport=[port]            TCP/UDP port to use\n" + " "*40 + default_string

def _set_default_values(options):
	if "ipport" in options["device_opt"]:
		if not "--ipport" in options:
			if "default" in all_opt["ipport"]:
				options["--ipport"] = all_opt["ipport"]["default"]
			elif "community" in options["device_opt"]:
				options["--ipport"] = "161"
			elif "--ssh" in options or all_opt["secure"].get("default", "0") == "1":
				options["--ipport"] = "22"
			elif "--ssl" in options or all_opt["ssl"].get("default", "0") == "1":
				options["--ipport"] = "443"
			elif "--ssl-secure" in options or all_opt["ssl_secure"].get("default", "0") == "1":
				options["--ipport"] = "443"
			elif "--ssl-insecure" in options or all_opt["ssl_insecure"].get("default", "0") == "1":
				options["--ipport"] = "443"
			elif "web" in options["device_opt"]:
				options["--ipport"] = "80"
			elif "telnet" in options["device_opt"]:
				options["--ipport"] = "23"

			if "--ipport" in options:
				all_opt["ipport"]["default"] = options["--ipport"]

	for opt in options["device_opt"]:
		if "default" in all_opt[opt] and not opt == "ipport":
			getopt_long = "--" + all_opt[opt]["longopt"]
			if getopt_long not in options:
				options[getopt_long] = all_opt[opt]["default"]

	return options

# stop = True/False : exit fence agent when problem is encountered
def _validate_input(options, stop = True):
	device_opt = options["device_opt"]
	valid_input = True

	if "--username" not in options and \
			device_opt.count("login") and (device_opt.count("no_login") == 0):
		valid_input = False
		fail_usage("Failed: You have to set login name", stop)

	if device_opt.count("ipaddr") and "--ip" not in options and "--managed" not in options and "--target" not in options:
		valid_input = False
		fail_usage("Failed: You have to enter fence address", stop)

	if device_opt.count("no_password") == 0:
		if 0 == device_opt.count("identity_file"):
			if not ("--password" in options or "--password-script" in options):
				valid_input = False
				fail_usage("Failed: You have to enter password or password script", stop)
		else:
			if not ("--password" in options or \
					"--password-script" in options or "--identity-file" in options):
				valid_input = False
				fail_usage("Failed: You have to enter password, password script or identity file", stop)

	if "--ssh" not in options and "--identity-file" in options:
		valid_input = False
		fail_usage("Failed: You have to use identity file together with ssh connection (-x)", stop)

	if "--identity-file" in options and not os.path.isfile(options["--identity-file"]):
		valid_input = False
		fail_usage("Failed: Identity file " + options["--identity-file"] + " does not exist", stop)

	if (0 == ["list", "list-status", "monitor"].count(options["--action"])) and \
		"--plug" not in options and device_opt.count("port") and \
		device_opt.count("no_port") == 0 and not device_opt.count("port_as_ip"):
		valid_input = False
		fail_usage("Failed: You have to enter plug number or machine identification", stop)

	for failed_opt in _get_opts_with_invalid_choices(options):
		valid_input = False
		fail_usage("Failed: You have to enter a valid choice for %s from the valid values: %s" % \
			("--" + all_opt[failed_opt]["longopt"], str(all_opt[failed_opt]["choices"])), stop)

	for failed_opt in _get_opts_with_invalid_types(options):
		valid_input = False
		if all_opt[failed_opt]["type"] == "second":
			fail_usage("Failed: The value you have entered for %s is not a valid time in seconds" % \
				("--" + all_opt[failed_opt]["longopt"]), stop)
		else:
			fail_usage("Failed: The value you have entered for %s is not a valid %s" % \
				("--" + all_opt[failed_opt]["longopt"], all_opt[failed_opt]["type"]), stop)

	return valid_input

def _encode_html_entities(text):
	return text.replace("&", "&amp;").replace('"', "&quot;").replace('<', "&lt;"). \
		replace('>', "&gt;").replace("'", "&apos;")

def _prepare_getopt_args(options):
	getopt_string = ""
	longopt_list = []
	for k in options:
		if k in all_opt and all_opt[k]["getopt"] != ":":
			# getopt == ":" means that opt is without short getopt, but has value
			getopt_string += all_opt[k]["getopt"]
		elif k not in all_opt:
			fail_usage("Parse error: unknown option '"+k+"'")

		if k in all_opt and "longopt" in all_opt[k]:
			if all_opt[k]["getopt"].endswith(":"):
				longopt_list.append(all_opt[k]["longopt"] + "=")
			else:
				longopt_list.append(all_opt[k]["longopt"])

	return (getopt_string, longopt_list)

def _parse_input_stdin(avail_opt):
	opt = {}
	name = ""

	mapping_longopt_names = dict([(all_opt[o].get("longopt"), o) for o in avail_opt])

	for line in sys.stdin.readlines():
		line = line.strip()
		if (line.startswith("#")) or (len(line) == 0):
			continue

		(name, value) = (line + "=").split("=", 1)
		value = value[:-1]
		value = re.sub(r"^\"(.*)\"$", r"\1", value)

		if name.replace("-", "_") in mapping_longopt_names:
			name = mapping_longopt_names[name.replace("-", "_")]
		elif name.replace("_", "-") in mapping_longopt_names:
			name = mapping_longopt_names[name.replace("_", "-")]

		if avail_opt.count(name) == 0 and name in ["nodename"]:
			continue
		elif avail_opt.count(name) == 0:
			logging.warning("Parse error: Ignoring unknown option '%s'\n", line)
			continue

		if all_opt[name]["getopt"].endswith(":"):
			opt["--"+all_opt[name]["longopt"].rstrip(":")] = value
		elif value.lower() in ["1", "yes", "on", "true"]:
			opt["--"+all_opt[name]["longopt"]] = "1"
		elif value.lower() in ["0", "no", "off", "false"]:
			opt["--"+all_opt[name]["longopt"]] = "0"
		else:
			logging.warning("Parse error: Ignoring option '%s' because it does not have value\n", name)

	opt.setdefault("--verbose-level", opt.get("--verbose", 0))

	return opt

def _parse_input_cmdline(avail_opt):
	filtered_opts = {}
	_verify_unique_getopt(avail_opt)
	(getopt_string, longopt_list) = _prepare_getopt_args(avail_opt)

	try:
		(entered_opt, left_arg) = getopt.gnu_getopt(sys.argv[1:], getopt_string, longopt_list)
		if len(left_arg) > 0:
			logging.warning("Unused arguments on command line: %s" % (str(left_arg)))
	except getopt.GetoptError as error:
		fail_usage("Parse error: " + error.msg)

	for opt in avail_opt:
		filtered_opts.update({opt : all_opt[opt]})

	# Short and long getopt names are changed to consistent "--" + long name (e.g. --username)
	long_opts = {}
	verbose_count = 0
	for arg_name in [k for (k, v) in entered_opt]:
		all_key = [key for (key, value) in list(filtered_opts.items()) \
			if "--" + value.get("longopt", "") == arg_name or "-" + value.get("getopt", "").rstrip(":") == arg_name][0]
		long_opts["--" + filtered_opts[all_key]["longopt"]] = dict(entered_opt)[arg_name]
		if all_key == "verbose":
			verbose_count += 1

	long_opts.setdefault("--verbose-level", verbose_count)

	# This test is specific because it does not apply to input on stdin
	if "port_as_ip" in avail_opt and not "--port-as-ip" in long_opts and "--plug" in long_opts:
		fail_usage("Parser error: option -n/--plug is not recognized")

	return long_opts

# for ["John", "Mary", "Eli"] returns "John, Mary and Eli"
def _join2(words, normal_separator=", ", last_separator=" and "):
	if len(words) <= 1:
		return "".join(words)
	else:
		return last_separator.join([normal_separator.join(words[:-1]), words[-1]])

def _join_wrap(words, normal_separator=", ", last_separator=" and ", first_indent=42):
	x = _join2(words, normal_separator, last_separator)
	wrapper = textwrap.TextWrapper()
	wrapper.initial_indent = " "*first_indent
	wrapper.subsequent_indent = " "*40
	wrapper.width = 85
	wrapper.break_on_hyphens = False
	wrapper.break_long_words = False
	wrapped_text = ""
	for line in wrapper.wrap(x):
		wrapped_text += line + "\n"
	return wrapped_text.lstrip().rstrip("\n")

def _get_opts_with_invalid_choices(options):
	options_failed = []
	device_opt = options["device_opt"]

	for opt in device_opt:
		if "choices" in all_opt[opt]:
			longopt = "--" + all_opt[opt]["longopt"]
			possible_values_upper = [y.upper() for y in all_opt[opt]["choices"]]
			if longopt in options:
				options[longopt] = options[longopt].upper()
				if not options["--" + all_opt[opt]["longopt"]] in possible_values_upper:
					options_failed.append(opt)
	return options_failed

def _get_opts_with_invalid_types(options):
	options_failed = []
	device_opt = options["device_opt"]

	for opt in device_opt:
		if "type" in all_opt[opt]:
			longopt = "--" + all_opt[opt]["longopt"]
			if longopt in options:
				if all_opt[opt]["type"] in ["integer", "second"]:
					try:
						number = int(options["--" + all_opt[opt]["longopt"]])
					except ValueError:
						options_failed.append(opt)
	return options_failed

def _verify_unique_getopt(avail_opt):
	used_getopt = set()

	for opt in avail_opt:
		getopt_value = all_opt[opt].get("getopt", "").rstrip(":")
		if getopt_value and getopt_value in used_getopt:
			fail_usage("Short getopt for %s (-%s) is not unique" % (opt, getopt_value))
		else:
			used_getopt.add(getopt_value)

def _get_available_actions(device_opt):
	available_actions = ["on", "off", "reboot", "status", "list", "list-status", \
		"monitor", "metadata", "manpage", "validate-all"]
	default_value = "reboot"

	if device_opt.count("fabric_fencing"):
		available_actions.remove("reboot")
		default_value = "off"
	if device_opt.count("no_status"):
		available_actions.remove("status")
	if device_opt.count("no_on"):
		available_actions.remove("on")
	if device_opt.count("no_off"):
		available_actions.remove("off")
	if not device_opt.count("separator"):
		available_actions.remove("list")
		available_actions.remove("list-status")
	if device_opt.count("diag"):
		available_actions.append("diag")

	return (available_actions, default_value)
