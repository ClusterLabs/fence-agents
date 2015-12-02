#!/usr/bin/python -tt

import sys, getopt, time, os, uuid, pycurl, stat
import pexpect, re, syslog
import logging
import subprocess
import threading
import shlex
import exceptions
import socket
import textwrap
import __main__

## do not add code here.
#BEGIN_VERSION_GENERATION
RELEASE_VERSION = "New fence lib agent - test release on steroids"
REDHAT_COPYRIGHT = ""
BUILD_DATE = "March, 2008"
#END_VERSION_GENERATION

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

all_opt = {
	"help"    : {
		"getopt" : "h",
		"longopt" : "help",
		"help" : "-h, --help                     Display this help and exit",
		"required" : "0",
		"shortdesc" : "Display help and exit",
		"order" : 54},
	"version" : {
		"getopt" : "V",
		"longopt" : "version",
		"help" : "-V, --version                  Display version information and exit",
		"required" : "0",
		"shortdesc" : "Display version information and exit",
		"order" : 53},
	"verbose" : {
		"getopt" : "v",
		"longopt" : "verbose",
		"help" : "-v, --verbose                  Verbose mode",
		"required" : "0",
		"order" : 51},
	"debug" : {
		"getopt" : "D:",
		"longopt" : "debug-file",
		"help" : "-D, --debug-file=[debugfile]   Debugging to output file",
		"required" : "0",
		"shortdesc" : "Write debug information to given file",
		"order" : 52},
	"delay" : {
		"getopt" : ":",
		"longopt" : "delay",
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
		"help" : "-u, --ipport=[port]            TCP/UDP port to use for connection",
		"required" : "0",
		"shortdesc" : "TCP/UDP port to use for connection with device",
		"order" : 1},
	"login" : {
		"getopt" : "l:",
		"longopt" : "username",
		"help" : "-l, --username=[name]          Login name",
		"required" : "?",
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
		"order" : ""},
	"diag" : {
		"getopt" : "",
		"help" : "",
		"order" : ""},
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
		"help" : "--login-timeout=[seconds]      Wait X seconds for cmd prompt after login",
		"default" : "5",
		"required" : "0",
		"order" : 200},
	"shell_timeout" : {
		"getopt" : ":",
		"longopt" : "shell-timeout",
		"help" : "--shell-timeout=[seconds]      Wait X seconds for cmd prompt after issuing command",
		"default" : "3",
		"required" : "0",
		"order" : 200},
	"power_timeout" : {
		"getopt" : ":",
		"longopt" : "power-timeout",
		"help" : "--power-timeout=[seconds]      Test X seconds for status change after ON/OFF",
		"default" : "20",
		"required" : "0",
		"order" : 200},
	"power_wait" : {
		"getopt" : ":",
		"longopt" : "power-wait",
		"help" : "--power-wait=[seconds]         Wait X seconds after issuing ON/OFF",
		"default" : "0",
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
		"order" : 1}
}

# options which are added automatically if 'key' is encountered ("default" is always added)
DEPENDENCY_OPT = {
		"default" : ["help", "debug", "verbose", "version", "action", "agent", \
			"power_timeout", "shell_timeout", "login_timeout", "power_wait", "retry_on", "delay"],
		"passwd" : ["passwd_script"],
		"sudo" : ["sudo_path"],
		"secure" : ["identity_file", "ssh_options", "ssh_path"],
		"telnet" : ["telnet_path"],
		"ipaddr" : ["ipport", "inet4_only", "inet6_only"],
		"port" : ["separator"],
		"ssl" : ["ssl_secure", "ssl_insecure", "gnutlscli_path"],
		"snmp" : ["snmp_auth_prot", "snmp_sec_level", "snmp_priv_prot", \
			"snmp_priv_passwd", "snmp_priv_passwd_script", "community", \
			"snmpset_path", "snmpget_path", "snmpwalk_path"]
	}

class fspawn(pexpect.spawn):
	def __init__(self, options, command):
		logging.info("Running command: %s", command)
		pexpect.spawn.__init__(self, command)
		self.opt = options

	def log_expect(self, pattern, timeout):
		result = self.expect(pattern, timeout)
		logging.debug("Received: %s", self.before + self.after)
		return result

	def send(self, message):
		logging.debug("Sent: %s", message)
		return pexpect.spawn.send(self, message)

	# send EOL according to what was detected in login process (telnet)
	def send_eol(self, message):
		return self.send(message + self.opt["eol"])

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
		if DEPENDENCY_OPT.has_key(opt):
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

def fail(error_code):
	message = {
		EC_LOGIN_DENIED : "Unable to connect/login to fencing device",
		EC_CONNECTION_LOST : "Connection lost",
		EC_TIMED_OUT : "Connection timed out",
		EC_WAITING_ON : "Failed: Timed out waiting to power ON",
		EC_WAITING_OFF : "Failed: Timed out waiting to power OFF",
		EC_STATUS : "Failed: Unable to obtain correct plug status or plug is not available",
		EC_STATUS_HMC : "Failed: Either unable to obtain correct plug status, "
				"partition is not available or incorrect HMC version used",
		EC_PASSWORD_MISSING : "Failed: You have to set login password",
		EC_INVALID_PRIVILEGES : "Failed: The user does not have the correct privileges to do the requested action."
	}[error_code] + "\n"
	logging.error("%s\n", message)
	sys.exit(EC_GENERIC_ERROR)

def usage(avail_opt):
	print "Usage:"
	print "\t" + os.path.basename(sys.argv[0]) + " [options]"
	print "Options:"

	sorted_list = [(key, all_opt[key]) for key in avail_opt]
	sorted_list.sort(lambda x, y: cmp(x[1]["order"], y[1]["order"]))

	for key, value in sorted_list:
		if len(value["help"]) != 0:
			print "   " + _join_wrap([value["help"]], first_indent=3)

def metadata(avail_opt, docs):
	# avail_opt has to be unique, if there are duplicities then they should be removed
	sorted_list = [(key, all_opt[key]) for key in list(set(avail_opt))]
	sorted_list.sort(lambda x, y: cmp(x[0], y[0]))
	sorted_list.sort(lambda x, y: cmp(x[1]["order"], y[1]["order"]))

	print "<?xml version=\"1.0\" ?>"
	print "<resource-agent name=\"" + os.path.basename(sys.argv[0]) + \
			"\" shortdesc=\"" + docs["shortdesc"] + "\" >"
	for (symlink, desc) in docs.get("symlink", []):
		print "<symlink name=\"" + symlink + "\" shortdesc=\"" + desc + "\"/>"
	print "<longdesc>" + docs["longdesc"] + "</longdesc>"
	print "<vendor-url>" + docs["vendorurl"] + "</vendor-url>"
	print "<parameters>"
	for option, _ in sorted_list:
		if all_opt[option].has_key("help") and len(all_opt[option]["help"]) > 0:
			print "\t<parameter name=\"" + option + "\" unique=\"0\" required=\"" + all_opt[option]["required"] + "\">"

			default = ""
			if all_opt[option].has_key("default"):
				default = "default=\"" + _encode_html_entities(str(all_opt[option]["default"])) + "\" "

			mixed = all_opt[option]["help"]
			## split it between option and help text
			res = re.compile(r"^(.*?--\S+)\s+", re.IGNORECASE | re.S).search(mixed)
			if None != res:
				mixed = res.group(1)
			mixed = _encode_html_entities(mixed)

			if not "shortdesc" in all_opt[option]:
				shortdesc = re.sub("\s\s+", " ", all_opt[option]["help"][31:])
			else:
				shortdesc = all_opt[option]["shortdesc"]

			print "\t\t<getopt mixed=\"" + mixed + "\" />"
			if all_opt[option].has_key("choices"):
				print "\t\t<content type=\"select\" "+default+" >"
				for choice in all_opt[option]["choices"]:
					print "\t\t\t<option value=\"%s\" />" % (choice)
				print "\t\t</content>"
			elif all_opt[option]["getopt"].count(":") > 0:
				print "\t\t<content type=\"string\" "+default+" />"
			else:
				print "\t\t<content type=\"boolean\" "+default+" />"
			print "\t\t<shortdesc lang=\"en\">" + shortdesc + "</shortdesc>"
			print "\t</parameter>"
	print "</parameters>"
	print "<actions>"

	(available_actions, _) = _get_available_actions(avail_opt)

	if "on" in available_actions:
		available_actions.remove("on")
		on_target = ' on_target="1"' if avail_opt.count("on_target") else ''
		print "\t<action name=\"on\"%s automatic=\"%d\"/>" % (on_target, avail_opt.count("fabric_fencing"))

	for action in available_actions:
		print "\t<action name=\"%s\" />" % (action)
	print "</actions>"
	print "</resource-agent>"

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

	if options["--action"] == "metadata" or any(options.has_key(k) for k in ("--help", "--version")):
		return options

	if options.has_key("--verbose"):
		logging.getLogger().setLevel(logging.DEBUG)

	## add logging to syslog
	logging.getLogger().addHandler(SyslogLibHandler())
	## add logging to stderr
	logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stderr))

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
		_validate_input(options, False)
		sys.exit(EC_OK)
	else:
		_validate_input(options, True)

	if options.has_key("--debug-file"):
		try:
			debug_file = logging.FileHandler(options["--debug-file"])
			debug_file.setLevel(logging.DEBUG)
			logging.getLogger().addHandler(debug_file)
		except IOError:
			logging.error("Unable to create file %s", options["--debug-file"])
			fail_usage("Failed: Unable to create file " + options["--debug-file"])

	if options.has_key("--snmp-priv-passwd-script"):
		options["--snmp-priv-passwd"] = os.popen(options["--snmp-priv-passwd-script"]).read().rstrip()

	if options.has_key("--password-script"):
		options["--password"] = os.popen(options["--password-script"]).read().rstrip()

	return options

## Obtain a power status from possibly more than one plug
##	"on" is returned if at least one plug is ON
######
def get_multi_power_fn(connection, options, get_power_fn):
	status = "off"
	plugs = options["--plugs"] if options.has_key("--plugs") else [""]

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

def set_multi_power_fn(connection, options, set_power_fn, get_power_fn, retry_attempts=1):
	plugs = options["--plugs"] if options.has_key("--plugs") else [""]

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

		for _ in xrange(int(options["--power-timeout"])):
			if get_multi_power_fn(connection, options, get_power_fn) != options["--action"]:
				time.sleep(1)
			else:
				return True
	return False

def show_docs(options, docs=None):
	device_opt = options["device_opt"]

	if docs == None:
		docs = {}
		docs["shortdesc"] = "Fence agent"
		docs["longdesc"] = ""

	if options.has_key("--help"):
		usage(device_opt)
		sys.exit(0)

	if options.get("--action", "") == "metadata":
		if "port_as_ip" in device_opt:
			device_opt.remove("separator")
		metadata(device_opt, docs)
		sys.exit(0)

	if options.has_key("--version"):
		print __main__.RELEASE_VERSION, __main__.BUILD_DATE
		print __main__.REDHAT_COPYRIGHT
		sys.exit(0)

def fence_action(connection, options, set_power_fn, get_power_fn, get_outlet_list=None, reboot_cycle_fn=None):
	result = 0

	try:
		if options.has_key("--plug"):
			options["--plugs"] = options["--plug"].split(",")

		## Process options that manipulate fencing device
		#####
		if (options["--action"] in ["list", "list-status"]) or \
			((options["--action"] == "monitor") and 1 == options["device_opt"].count("port") and \
			0 == options["device_opt"].count("port_as_ip")):

			if 0 == options["device_opt"].count("port"):
				print "N/A"
			elif get_outlet_list == None:
				## @todo: exception?
				## This is just temporal solution, we will remove default value
				## None as soon as all existing agent will support this operation
				print "NOTICE: List option is not working on this device yet"
			else:
				options["--original-action"] = options["--action"]
				options["--action"] = "list"
				outlets = get_outlet_list(connection, options)
				options["--action"] = options["--original-action"]
				del options["--original-action"]

				## keys can be numbers (port numbers) or strings (names of VM, UUID)
				for outlet_id in outlets.keys():
					(alias, status) = outlets[outlet_id]
					if status is None or (not status.upper() in ["ON", "OFF"]):
						status = "UNKNOWN"
						status = status.upper()

					if options["--action"] == "list":
						print outlet_id + options["--separator"] + alias
					elif options["--action"] == "list-status":
						print outlet_id + options["--separator"] + alias + options["--separator"] + status

			return

		if options["--action"] == "monitor" and not "port" in options["device_opt"] and "no_status" in options["device_opt"]:
			# Unable to do standard monitoring because 'status' action is not available
			return 0

		status = None
		if not "no_status" in options["device_opt"]:
			status = get_multi_power_fn(connection, options, get_power_fn)
			if status != "on" and status != "off":
				fail(EC_STATUS)

		if options["--action"] == status:
			if not (status == "on" and "force_on" in options["device_opt"]):
				print "Success: Already %s" % (status.upper())
				return 0

		if options["--action"] == "on":
			if set_multi_power_fn(connection, options, set_power_fn, get_power_fn, 1 + int(options["--retry-on"])):
				print "Success: Powered ON"
			else:
				fail(EC_WAITING_ON)
		elif options["--action"] == "off":
			if set_multi_power_fn(connection, options, set_power_fn, get_power_fn):
				print "Success: Powered OFF"
			else:
				fail(EC_WAITING_OFF)
		elif options["--action"] == "reboot":
			power_on = False
			if options.get("--method", "").lower() == "cycle" and reboot_cycle_fn is not None:
				for _ in range(1, 1 + int(options["--retry-on"])):
					if reboot_cycle_fn(connection, options):
						power_on = True
						break

				if not power_on:
					fail(EC_TIMED_OUT)

			else:
				if status != "off":
					options["--action"] = "off"
					if not set_multi_power_fn(connection, options, set_power_fn, get_power_fn):
						fail(EC_WAITING_OFF)

				options["--action"] = "on"

				try:
					power_on = set_multi_power_fn(connection, options, set_power_fn, get_power_fn, int(options["--retry-on"]))
				except Exception, ex:
					# an error occured during power ON phase in reboot
					# fence action was completed succesfully even in that case
					logging.warning("%s", str(ex))

			if power_on == False:
				# this should not fail as node was fenced succesfully
				logging.error('Timed out waiting to power ON\n')

			print "Success: Rebooted"
		elif options["--action"] == "status":
			print "Status: " + status.upper()
			if status.upper() == "OFF":
				result = 2
		elif options["--action"] == "monitor":
			pass
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)
	except pycurl.error, ex:
		logging.error("%s\n", str(ex))
		fail(EC_TIMED_OUT)
	except socket.timeout, ex:
		logging.error("%s\n", str(ex))
		fail(EC_TIMED_OUT)

	return result

def fence_login(options, re_login_string=r"(login\s*: )|((?!Last )Login Name:  )|(username: )|(User Name :)"):
	run_delay(options)

	if not options.has_key("eol"):
		options["eol"] = "\r\n"

	if options.has_key("--command-prompt") and type(options["--command-prompt"]) is not list:
		options["--command-prompt"] = [options["--command-prompt"]]

	try:
		if options.has_key("--ssl"):
			conn = _open_ssl_connection(options)
		elif options.has_key("--ssh") and not options.has_key("--identity-file"):
			conn = _login_ssh_with_password(options, re_login_string)
		elif options.has_key("--ssh") and options.has_key("--identity-file"):
			conn = _login_ssh_with_identity_file(options)
		else:
			conn = _login_telnet(options, re_login_string)
	except pexpect.EOF, exception:
		logging.debug("%s", str(exception))
		fail(EC_LOGIN_DENIED)
	except pexpect.TIMEOUT, exception:
		logging.debug("%s", str(exception))
		fail(EC_LOGIN_DENIED)
	return conn

def is_executable(path):
	if os.path.exists(path):
		stats = os.stat(path)
		if stat.S_ISREG(stats.st_mode) and os.access(path, os.X_OK):
			return True
	return False

def run_command(options, command, timeout=None, env=None):
	if timeout is None and "--power-timeout" in options:
		timeout = options["--power-timeout"]
	if timeout is not None:
		timeout = float(timeout)

	# For IPMI password occurs on command line, it should not be part of debug info
	log_command = command
	if "ipmitool" in log_command:
		log_command = re.sub("-P (.+?) -p", "-P [set] -p", log_command)
	logging.info("Executing: %s\n", log_command)

	try:
		process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
	except OSError:
		fail_usage("Unable to run %s\n" % command)

	thread = threading.Thread(target=process.wait)
	thread.start()
	thread.join(timeout)
	if thread.is_alive():
		process.kill()
		fail(EC_TIMED_OUT)

	status = process.wait()

	(pipe_stdout, pipe_stderr) = process.communicate()
	process.stdout.close()
	process.stderr.close()

	logging.debug("%s %s %s\n", str(status), str(pipe_stdout), str(pipe_stderr))

	return (status, pipe_stdout, pipe_stderr)

def run_delay(options):
	## Delay is important for two-node clusters fencing but we do not need to delay 'status' operations
	if options["--action"] in ["off", "reboot"]:
		logging.info("Delay %s second(s) before logging in to the fence device", options["--delay"])
		time.sleep(int(options["--delay"]))

def fence_logout(conn, logout_string, sleep=0):
	# Logout is not required part of fencing but we should attempt to do it properly
	# In some cases our 'exit' command is faster and we can not close connection as it
	# was already closed by fencing device
	try:
		conn.send_eol(logout_string)
		time.sleep(sleep)
		conn.close()
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass

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

	if options.has_key("--notls"):
		gnutls_opts = "--priority \"NORMAL:-VERS-TLS1.2:-VERS-TLS1.1:-VERS-TLS1.0:+VERS-SSL3.0\""
	elif options.has_key("--tls1.0"):
		gnutls_opts = "--priority \"NORMAL:-VERS-TLS1.2:-VERS-TLS1.1:+VERS-TLS1.0:%LATEST_RECORD_VERSION\""

	# --ssl is same as the --ssl-secure; it means we want to verify certificate in these cases
	if options.has_key("--ssl-insecure"):
		ssl_opts = "--insecure"

	command = '%s %s %s --crlf -p %s %s' % \
		(options["--gnutlscli-path"], gnutls_opts, ssl_opts, options["--ipport"], options["--ip"])
	try:
		conn = fspawn(options, command)
	except pexpect.ExceptionPexpect, ex:
		logging.error("%s\n", str(ex))
		sys.exit(EC_GENERIC_ERROR)

	return conn

def _login_ssh_with_identity_file(options):
	if options.has_key("--inet6-only"):
		force_ipvx = "-6 "
	elif options.has_key("--inet4-only"):
		force_ipvx = "-4 "
	else:
		force_ipvx = ""

	command = '%s %s %s@%s -i %s -p %s' % \
		(options["--ssh-path"], force_ipvx, options["--username"], options["--ip"], \
		options["--identity-file"], options["--ipport"])
	if options.has_key("--ssh-options"):
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
		if options.has_key("--password"):
			conn.sendline(options["--password"])
			conn.log_expect(options["--command-prompt"], int(options["--login-timeout"]))
		else:
			fail_usage("Failed: You have to enter passphrase (-p) for identity file")

	return conn

def _login_telnet(options, re_login_string):
	re_login = re.compile(re_login_string, re.IGNORECASE)
	re_pass = re.compile("(password)|(pass phrase)", re.IGNORECASE)

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
	re_pass = re.compile("(password)|(pass phrase)", re.IGNORECASE)

	if options.has_key("--inet6-only"):
		force_ipvx = "-6 "
	elif options.has_key("--inet4-only"):
		force_ipvx = "-4 "
	else:
		force_ipvx = ""

	command = '%s %s %s@%s -p %s -o PubkeyAuthentication=no' % \
			(options["--ssh-path"], force_ipvx, options["--username"], options["--ip"], options["--ipport"])
	if options.has_key("--ssh-options"):
		command += ' ' + options["--ssh-options"]

	conn = fspawn(options, command)

	if options.has_key("telnet_over_ssh"):
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

		if all_opt["ipport"].has_key("default"):
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
		if all_opt[opt].has_key("default") and not opt == "ipport":
			getopt_long = "--" + all_opt[opt]["longopt"]
			if not options.has_key(getopt_long):
				options[getopt_long] = all_opt[opt]["default"]

	return options

# stop = True/False : exit fence agent when problem is encountered
def _validate_input(options, stop = True):
	device_opt = options["device_opt"]
	valid_input = True

	if not options.has_key("--username") and \
			device_opt.count("login") and (device_opt.count("no_login") == 0):
		valid_input = False
		fail_usage("Failed: You have to set login name", stop)

	if device_opt.count("ipaddr") and not options.has_key("--ip") and not options.has_key("--managed"):
		valid_input = False
		fail_usage("Failed: You have to enter fence address", stop)

	if device_opt.count("no_password") == 0:
		if 0 == device_opt.count("identity_file"):
			if not (options.has_key("--password") or options.has_key("--password-script")):
				valid_input = False
				fail_usage("Failed: You have to enter password or password script", stop)
		else:
			if not (options.has_key("--password") or \
					options.has_key("--password-script") or options.has_key("--identity-file")):
				valid_input = False
				fail_usage("Failed: You have to enter password, password script or identity file", stop)

	if not options.has_key("--ssh") and options.has_key("--identity-file"):
		valid_input = False
		fail_usage("Failed: You have to use identity file together with ssh connection (-x)", stop)

	if options.has_key("--identity-file") and not os.path.isfile(options["--identity-file"]):
		valid_input = False
		fail_usage("Failed: Identity file " + options["--identity-file"] + " does not exist", stop)

	if (0 == ["list", "list-status", "monitor"].count(options["--action"])) and \
		not options.has_key("--plug") and device_opt.count("port") and \
		device_opt.count("no_port") == 0 and not device_opt.count("port_as_ip"):
		valid_input = False
		fail_usage("Failed: You have to enter plug number or machine identification", stop)

	if options.has_key("--plug") and len(options["--plug"].split(",")) > 1 and \
			options.has_key("--method") and options["--method"] == "cycle":
		valid_input = False
		fail_usage("Failed: Cannot use --method cycle for more than 1 plug", stop)

	for failed_opt in _get_opts_with_invalid_choices(options):
		valid_input = False
		fail_usage("Failed: You have to enter a valid choice for %s from the valid values: %s" % \
			("--" + all_opt[failed_opt]["longopt"], str(all_opt[failed_opt]["choices"])), stop)

	return valid_input

def _encode_html_entities(text):
	return text.replace("&", "&amp;").replace('"', "&quot;").replace('<', "&lt;"). \
		replace('>', "&gt;").replace("'", "&apos;")

def _prepare_getopt_args(options):
	getopt_string = ""
	longopt_list = []
	for k in options:
		if all_opt.has_key(k) and all_opt[k]["getopt"] != ":":
			# getopt == ":" means that opt is without short getopt, but has value
			getopt_string += all_opt[k]["getopt"]
		elif not all_opt.has_key(k):
			fail_usage("Parse error: unknown option '"+k+"'")

		if all_opt.has_key(k) and all_opt[k].has_key("longopt"):
			if all_opt[k]["getopt"].endswith(":"):
				longopt_list.append(all_opt[k]["longopt"] + "=")
			else:
				longopt_list.append(all_opt[k]["longopt"])

	return (getopt_string, longopt_list)

def _parse_input_stdin(avail_opt):
	opt = {}
	name = ""
	for line in sys.stdin.readlines():
		line = line.strip()
		if (line.startswith("#")) or (len(line) == 0):
			continue

		(name, value) = (line + "=").split("=", 1)
		value = value[:-1]

		if avail_opt.count(name) == 0 and name in ["nodename"]:
			continue
		elif avail_opt.count(name) == 0:
			logging.warning("Parse error: Ignoring unknown option '%s'\n", line)
			continue

		if all_opt[name]["getopt"].endswith(":"):
			opt["--"+all_opt[name]["longopt"].rstrip(":")] = value
		elif value.lower() in ["1", "yes", "on", "true"]:
			opt["--"+all_opt[name]["longopt"]] = "1"
		else:
			logging.warning("Parse error: Ignoring option '%s' because it does not have value\n", name)
	return opt

def _parse_input_cmdline(avail_opt):
	filtered_opts = {}
	_verify_unique_getopt(avail_opt)
	(getopt_string, longopt_list) = _prepare_getopt_args(avail_opt)

	try:
		(entered_opt, left_arg) = getopt.gnu_getopt(sys.argv[1:], getopt_string, longopt_list)
		if len(left_arg) > 0:
			logging.warning("Unused arguments on command line: %s" % (str(left_arg)))
	except getopt.GetoptError, error:
		fail_usage("Parse error: " + error.msg)

	for opt in avail_opt:
		filtered_opts.update({opt : all_opt[opt]})

	# Short and long getopt names are changed to consistent "--" + long name (e.g. --username)
	long_opts = {}
	for arg_name in dict(entered_opt).keys():
		all_key = [key for (key, value) in filtered_opts.items() \
			if "--" + value.get("longopt", "") == arg_name or "-" + value.get("getopt", "").rstrip(":") == arg_name][0]
		long_opts["--" + filtered_opts[all_key]["longopt"]] = dict(entered_opt)[arg_name]

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
		if all_opt[opt].has_key("choices"):
			longopt = "--" + all_opt[opt]["longopt"]
			possible_values_upper = [y.upper() for y in all_opt[opt]["choices"]]
			if options.has_key(longopt):
				options[longopt] = options[longopt].upper()
				if not options["--" + all_opt[opt]["longopt"]] in possible_values_upper:
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
		"monitor", "metadata", "validate-all"]
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
