#!/usr/bin/python -tt

# The Following Agent Has Been Tested On:
# ePowerSwitch 8M+ version 1.0.0.4

import sys, re
import httplib, base64, string, socket
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_LOGIN_DENIED, EC_TIMED_OUT, run_delay

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="ePowerSwitch 8M+ (eps)"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

# Run command on EPS device.
# @param options Device options
# @param params HTTP GET parameters (without ?)
def eps_run_command(options, params):
	try:
		# New http connection
		conn = httplib.HTTPConnection(options["--ip"])

		request_str = "/"+options["--page"]

		if params != "":
			request_str += "?"+params

		logging.debug("GET %s\n", request_str)
		conn.putrequest('GET', request_str)

		if options.has_key("--username"):
			if not options.has_key("--password"):
				options["--password"] = "" # Default is empty password

			# String for Authorization header
			auth_str = 'Basic ' + string.strip(base64.encodestring(options["--username"]+':'+options["--password"]))
			logging.debug("Authorization: %s\n", auth_str)
			conn.putheader('Authorization', auth_str)

		conn.endheaders()

		response = conn.getresponse()

		logging.debug("%d %s\n", response.status, response.reason)

		#Response != OK -> couldn't login
		if response.status != 200:
			fail(EC_LOGIN_DENIED)

		result = response.read()
		logging.debug("%s \n", result)
		conn.close()
	except socket.timeout:
		fail(EC_TIMED_OUT)
	except socket.error:
		fail(EC_LOGIN_DENIED)

	return result

def get_power_status(conn, options):
	del conn
	ret_val = eps_run_command(options, "")

	result = {}
	status = re.findall(r"p(\d{2})=(0|1)\s*\<br\>", ret_val.lower())
	for out_num, out_stat in status:
		result[out_num] = ("", (out_stat == "1" and "on" or "off"))

	if not options["--action"] in ['monitor', 'list']:
		if not options["--plug"] in result:
			fail_usage("Failed: You have to enter existing physical plug!")
		else:
			return result[options["--plug"]][1]
	else:
		return result

def set_power_status(conn, options):
	del conn
	eps_run_command(options, "P%s=%s"%(options["--plug"], (options["--action"] == "on" and "1" or "0")))

# Define new option
def eps_define_new_opts():
	all_opt["hidden_page"] = {
		"getopt" : "c:",
		"longopt" : "page",
		"help":"-c, --page=[page]              Name of hidden page (default hidden.htm)",
		"required" : "0",
		"shortdesc" : "Name of hidden page",
		"default" : "hidden.htm",
		"order": 1
		}

# Starting point of fence agent
def main():
	device_opt = ["ipaddr", "login", "passwd", "no_login", "no_password", \
			"port", "hidden_page", "web"]

	atexit.register(atexit_handler)

	eps_define_new_opts()

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for ePowerSwitch"
	docs["longdesc"] = "fence_eps  is an I/O Fencing agent \
which can be used with the ePowerSwitch 8M+ power switch to fence \
connected machines. Fence agent works ONLY on 8M+ device, because \
this is only one, which has support for hidden page feature. \
\n.TP\n\
Agent basically works by connecting to hidden page and pass \
appropriate arguments to GET request. This means, that hidden \
page feature must be enabled and properly configured."
	docs["vendorurl"] = "http://www.epowerswitch.com"
	show_docs(options, docs)

	run_delay(options)
	#Run fence action. Conn is None, beacause we always need open new http connection
	result = fence_action(None, options, set_power_status, get_power_status, get_power_status)

	sys.exit(result)

if __name__ == "__main__":
	main()
