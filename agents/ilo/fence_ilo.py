#!@PYTHON@ -tt

#####
##
## The Following Agent Has Been Tested On:
##
##  iLO Version
## +---------------------------------------------+
##  iLO  / firmware 1.91 / RIBCL 2.22
##  iLO2 / firmware 1.22 / RIBCL 2.22
##  iLO2 / firmware 1.50 / RIBCL 2.22
#####

import sys, re, pexpect
import atexit
from xml.sax.saxutils import quoteattr
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_LOGIN_DENIED

def get_power_status(conn, options):
	conn.send("<LOGIN USER_LOGIN = " + quoteattr(options["--username"]) + \
		" PASSWORD = " + quoteattr(options["--password"]) + ">\r\n")
	conn.send("<SERVER_INFO MODE = \"read\"><GET_HOST_POWER_STATUS/>\r\n")
	conn.send("</SERVER_INFO></LOGIN>\r\n")
	conn.log_expect("HOST_POWER=\"(.*?)\"", int(options["--power-timeout"]))

	status = conn.match.group(1)
	return status.lower().strip()

def set_power_status(conn, options):
	conn.send("<LOGIN USER_LOGIN = " + quoteattr(options["--username"]) + \
		" PASSWORD = " + quoteattr(options["--password"]) + ">\r\n")
	conn.send("<SERVER_INFO MODE = \"write\">")

	if options.get("fw_processor", None) == "iLO2":
		if options["fw_version"] > 1.29:
			conn.send("<HOLD_PWR_BTN TOGGLE=\"yes\" />\r\n")
		else:
			conn.send("<HOLD_PWR_BTN />\r\n")
	elif options["--ribcl-version"] < 2.21:
		conn.send("<SET_HOST_POWER HOST_POWER = \"" + options["--action"] + "\" />\r\n")
	else:
		if options["--action"] == "off":
			conn.send("<HOLD_PWR_BTN/>\r\n")
		else:
			conn.send("<PRESS_PWR_BTN/>\r\n")
	conn.send("</SERVER_INFO></LOGIN>\r\n")

	return

def define_new_opts():
	all_opt["ribcl"] = {
		"getopt" : "r:",
		"longopt" : "ribcl-version",
		"help" : "-r, --ribcl-version=[version]  Force ribcl version to use",
		"required" : "0",
		"shortdesc" : "Force ribcl version to use",
		"order" : 1}

def main():
	device_opt = ["ipaddr", "login", "passwd", "ssl", "notls", "tls1.0", "ribcl"]

	atexit.register(atexit_handler)

	define_new_opts()

	all_opt["login_timeout"]["default"] = "10"
	all_opt["retry_on"]["default"] = "3"
	all_opt["ssl"]["default"] = "1"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for HP iLO"
	docs["longdesc"] = "fence_ilo is an I/O Fencing agent \
used for HP servers with the Integrated Light Out (iLO) PCI card.\
The agent opens an SSL connection to the iLO card. Once the SSL \
connection is established, the agent is able to communicate with \
the iLO card through an XML stream."
	docs["vendorurl"] = "http://www.hp.com"
	docs["symlink"] = [("fence_ilo2", "Fence agent for HP iLO2")]
	show_docs(options, docs)

	##
	## Login and get version number
	####
	conn = fence_login(options)
	try:
		conn.send("<?xml version=\"1.0\"?>\r\n")
		conn.log_expect(["</RIBCL>", "<END_RIBCL/>"], int(options["--login-timeout"]))
	except pexpect.TIMEOUT:
		fail(EC_LOGIN_DENIED)
	except pexpect.EOF:
		if "--tls1.0" in options:
			fail(EC_LOGIN_DENIED)
		options["--tls1.0"] = "1"
		conn.close()
		conn = fence_login(options)
		try:
			conn.send("<?xml version=\"1.0\"?>\r\n")
			conn.log_expect(["</RIBCL>", "<END_RIBCL/>"], int(options["--login-timeout"]))
		except pexpect.TIMEOUT:
			fail(EC_LOGIN_DENIED)
		except pexpect.EOF:
			fail(EC_LOGIN_DENIED)

	try:
		version = re.compile("<RIBCL VERSION=\"(.*?)\"", re.IGNORECASE).search(conn.before).group(1)
		if "--ribcl-version" not in options:
			options["--ribcl-version"] = float(version)

		if options["--ribcl-version"] >= 2:
			conn.send("<RIBCL VERSION=\"2.0\">\r\n")
		else:
			conn.send("<RIBCL VERSION=\"1.2\">\r\n")

		conn.send("<LOGIN USER_LOGIN = " + quoteattr(options["--username"]) + \
			" PASSWORD = " + quoteattr(options["--password"]) + ">\r\n")
		if options["--ribcl-version"] >= 2:
			conn.send("<RIB_INFO MODE=\"read\"><GET_FW_VERSION />\r\n")
			conn.send("</RIB_INFO>\r\n")
			conn.log_expect(r"<GET_FW_VERSION\s*\n", int(options["--shell-timeout"]))
			conn.log_expect("/>", int(options["--shell-timeout"]))
			options["fw_version"] = float(re.compile(r"FIRMWARE_VERSION\s*=\s*\"(.*?)\"",
					re.IGNORECASE).search(conn.before).group(1))
			options["fw_processor"] = re.compile(r"MANAGEMENT_PROCESSOR\s*=\s*\"(.*?)\"",
					re.IGNORECASE).search(conn.before).group(1)
		conn.send("</LOGIN>\r\n")
	except pexpect.TIMEOUT:
		fail(EC_LOGIN_DENIED)
	except pexpect.EOF:
		fail(EC_LOGIN_DENIED)

	##
	## Fence operations
	####
	result = fence_action(conn, options, set_power_status, get_power_status, None)

	sys.exit(result)

if __name__ == "__main__":
	main()
