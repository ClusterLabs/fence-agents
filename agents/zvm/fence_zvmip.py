#!@PYTHON@ -tt

import sys
import atexit
import socket
import struct
import logging
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, run_delay, EC_LOGIN_DENIED, EC_TIMED_OUT

INT4 = 4

def open_socket(options):
	try:
		if "--inet6-only" in options:
			protocol = socket.AF_INET6
		elif "--inet4-only" in options:
			protocol = socket.AF_INET
		else:
			protocol = 0
		(_, _, _, _, addr) = socket.getaddrinfo( \
				options["--ip"], options["--ipport"], protocol,
				0, socket.IPPROTO_TCP, socket.AI_PASSIVE
				)[0]
	except socket.gaierror:
		fail(EC_LOGIN_DENIED)

	if "--ssl-secure" in options or "--ssl-insecure" in options:
		import ssl
		sock = socket.socket()
		sslcx = ssl.create_default_context()
		if "--ssl-insecure" in options:
			sslcx.check_hostname = False
			sslcx.verify_mode = ssl.CERT_NONE
		conn = sslcx.wrap_socket(sock, server_hostname=options["--ip"])
	else:
		conn = socket.socket()
	conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	conn.settimeout(float(options["--shell-timeout"]) or None)
	try:
		conn.connect(addr)
	except socket.error as e:
		logging.debug(e)
		fail(EC_LOGIN_DENIED)

	return conn

def smapi_pack_string(string):
	return struct.pack("!i%ds" % (len(string)), len(string), string.encode("UTF-8"))

def prepare_smapi_command(options, smapi_function, additional_args):
	packet_size = 3*INT4 + len(smapi_function) + len(options["--username"]) + len(options["--password"])
	for arg in additional_args:
		packet_size += INT4 + len(arg)

	command = struct.pack("!i", packet_size)
	command += smapi_pack_string(smapi_function)
	command += smapi_pack_string(options["--username"])
	command += smapi_pack_string(options["--password"])
	for arg in additional_args:
		command += smapi_pack_string(arg)

	return command

def get_power_status(conn, options):
	del conn

	if options.get("--original-action", None) == "monitor":
		(return_code, reason_code, images_active) = \
			get_list_of_images(options, "Check_Authentication", None)

		logging.debug("Check_Authenticate (%d,%d)", return_code, reason_code)
		if return_code == 0:
			return {}
		else:
			fail(EC_LOGIN_DENIED)

	if options["--action"] == "list":
		# '*' = list all active images
		options["--plug"] = "*"

	(return_code, reason_code, images_active) = \
			get_list_of_images(options, "Image_Status_Query", options["--plug"])
	logging.debug("Image_Status_Query results are (%d,%d)", return_code, reason_code)

	if not options["--action"] == "list":
		if (return_code == 0) and (reason_code == 0):
			return "on"
		elif (return_code == 0) and (reason_code == 12):
			# We are running always with --missing-as-off because we can not check if image
			# is defined or not (look at rhbz#1188750)
			return "off"
		else:
			return "unknown"
	else:
		(return_code, reason_code, images_defined) = \
			get_list_of_images(options, "Image_Name_Query_DM", options["--username"])
		logging.debug("Image_Name_Query_DM results are (%d,%d)", return_code, reason_code)

		return dict([(i, ("", "on" if i in images_active else "off")) for i in images_defined])

def set_power_status(conn, options):
	conn = open_socket(options)

	packet = None
	if options["--action"] == "on":
		packet = prepare_smapi_command(options, "Image_Activate", [options["--plug"]])
	elif options["--action"] == "off":
		packet = prepare_smapi_command(options, "Image_Deactivate", [options["--plug"], "IMMED"])
	conn.send(packet)

	request_id = struct.unpack("!i", conn.recv(INT4))[0]
	(output_len, request_id, return_code, reason_code) = struct.unpack("!iiii", conn.recv(INT4 * 4))
	logging.debug("Image_(De)Activate results are (%d,%d)", return_code, reason_code)

	conn.close()
	return

def get_list_of_images(options, command, data_as_plug):
	conn = open_socket(options)

	if data_as_plug is None:
		packet = prepare_smapi_command(options, command, [])
	else:
		packet = prepare_smapi_command(options, command, [data_as_plug])

	conn.send(packet)

	try:
		request_id = struct.unpack("!i", conn.recv(INT4))[0]
		(output_len, request_id, return_code, reason_code) = struct.unpack("!iiii", conn.recv(INT4 * 4))
	except struct.error:
		logging.debug(sys.exc_info())
		fail_usage("Failed: Unable to connect to {} port: {} SSL: {} \n".format(options["--ip"], options["--ipport"], bool("--ssl" in options)))

	images = set()

	if output_len > 3*INT4:
		recvflag = socket.MSG_WAITALL if "--ssl-secure" not in options and "--ssl-insecure" not in options else 0
		array_len = struct.unpack("!i", conn.recv(INT4))[0]
		data = ""

		while True:
			read_data = conn.recv(1024, recvflag).decode("UTF-8")
			data += read_data
			if array_len == len(data):
				break
			elif not read_data:
				logging.error("Failed: Not enough data read from socket")
				fail(EC_TIMED_OUT)

		parsed_len = 0
		while parsed_len < array_len:
			string_len = struct.unpack("!i", data[parsed_len:parsed_len+INT4].encode("UTF-8"))[0]
			parsed_len += INT4
			image_name = struct.unpack("!%ds" % (string_len), data[parsed_len:parsed_len+string_len].encode("UTF-8"))[0].decode("UTF-8")
			parsed_len += string_len
			images.add(image_name)

	conn.close()
	return (return_code, reason_code, images)

def define_new_opts():
	all_opt["disable_ssl"] = {
		"getopt" : "",
		"longopt" : "disable-ssl",
		"help" : "--disable-ssl                  Don't use SSL connection",
		"required" : "0",
		"shortdesc" : "Don't use SSL",
		"order": 2
	}

def main():
	device_opt = ["ipaddr", "login", "passwd", "port", "method", "missing_as_off",
		      "inet4_only", "inet6_only", "ssl", "disable_ssl"]

	atexit.register(atexit_handler)
	define_new_opts()

	all_opt["ssl"]["help"] = "-z, --ssl                      Use SSL connection with verifying certificate (Default)"

	all_opt["ipport"]["default"] = "44444"
	all_opt["shell_timeout"]["default"] = "5"
	all_opt["missing_as_off"]["default"] = "1"
	all_opt["ssl"]["default"] = "1"
	options = check_input(device_opt, process_input(device_opt), other_conditions=True)

	if "--disable-ssl" in options or options["--ssl"] == "0":
		for k in ["--ssl", "--ssl-secure", "--ssl-insecure"]:
			if k in options:
				del options[k]

	if len(options.get("--plug", "")) > 8:
		fail_usage("Failed: Name of image can not be longer than 8 characters")

	if options["--action"] == "validate-all":
		sys.exit(0)

	docs = {}
	docs["shortdesc"] = "Fence agent for use with z/VM Virtual Machines"
	docs["longdesc"] = """fence_zvmip is a Power Fencing agent for z/VM \
SMAPI service via TCP/IP.

The z/VM SMAPI service must be configured so that the virtual machine running
the agent can connect to the service, access the system's directory manager,
and shortly thereafter run image_deactivate and image_activate. This involves
updating the VSMWORK1 NAMELIST and VSMWORK1 AUTHLIST VMSYS:VSMWORK1 files.

The NAMELIST entry assigns all the required functions to one nick and should
look similar to this:

:nick.ZVM_FENCE\n.br\n\
:list.\n.br\n\
IMAGE_ACTIVATE\n.br\n\
IMAGE_DEACTIVATE\n.br\n\
IMAGE_STATUS_QUERY\n.br\n\
CHECK_AUTHENTICATION\n.br\n\
IMAGE_NAME_QUERY_DM


The AUTHLIST entry authorizes the user to perform all the functions associated
with the nick, and should look similar to this:

Column 1                   Column 66                Column 131

|                          |                        |\n.br\n\
V                          V                        V

XXXXXXXX                   ALL                      ZVM_FENCE

where XXXXXXXX is the name of the user in the authuser field of the request.

Refer to the official z/VM documentation for complete instructions and
reference materials.
"""
	docs["vendorurl"] = "http://www.ibm.com"
	show_docs(options, docs)

	run_delay(options)
	result = fence_action(None, options, set_power_status, get_power_status, get_power_status)
	sys.exit(result)

if __name__ == "__main__":
	main()
