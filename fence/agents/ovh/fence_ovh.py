#!/usr/bin/python -tt
# Copyright 2013 Adrian Gibanel Lopez (bTactic)
# Adrian Gibanel improved this script at 2013 to add verification of success and to output metadata

# Based on:
# This is a fence agent for use at OVH
# As there are no other fence devices available, we must use OVH's SOAP API #Quick-and-dirty
# assemled by Dennis Busch, secofor GmbH, Germany
# This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 Unported License.

import sys, time
import shutil, tempfile
import logging
import atexit
from datetime import datetime
from suds.client import Client
from suds.xsd.doctor import ImportDoctor, Import
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_LOGIN_DENIED, run_delay

OVH_RESCUE_PRO_NETBOOT_ID = '28'
OVH_HARD_DISK_NETBOOT_ID = '1'

STATUS_HARD_DISK_SLEEP = 240 # Wait 4 minutes to SO to boot
STATUS_RESCUE_PRO_SLEEP = 150 # Wait 2 minutes 30 seconds to Rescue-Pro to run

def define_new_opts():
	all_opt["email"] = {
		"getopt" : "Z:",
		"longopt" : "email",
		"help" : "-Z, --email=[email]          email for reboot message: admin@domain.com",
		"required" : "1",
		"shortdesc" : "Reboot email",
		"order" : 1}

def netboot_reboot(conn, options, mode):
	# dedicatedNetbootModifyById changes the mode of the next reboot
	conn.service.dedicatedNetbootModifyById(options["session"], options["--plug"], mode, '', options["--email"])

	# dedicatedHardRebootDo initiates a hard reboot on the given node
	conn.service.dedicatedHardRebootDo(options["session"],
			options["--plug"], 'Fencing initiated by cluster', '', 'en')

	conn.logout(options["session"])

def reboot_time(conn, options):
	result = conn.service.dedicatedHardRebootStatus(options["session"], options["--plug"])
	tmpstart = datetime.strptime(result.start, '%Y-%m-%d %H:%M:%S')
	tmpend = datetime.strptime(result.end, '%Y-%m-%d %H:%M:%S')
	result.start = tmpstart
	result.end = tmpend

	return result

def soap_login(options):
	imp = Import('http://schemas.xmlsoap.org/soap/encoding/')
	url = 'https://www.ovh.com/soapi/soapi-re-1.59.wsdl'
	imp.filter.add('http://soapi.ovh.com/manager')
	d = ImportDoctor(imp)

	tmp_dir = tempfile.mkdtemp()
	tempfile.tempdir = tmp_dir
	atexit.register(remove_tmp_dir, tmp_dir)

	try:
		soap = Client(url, doctor=d)
		session = soap.service.login(options["--username"], options["--password"], 'en', 0)
	except Exception:
		fail(EC_LOGIN_DENIED)

	options["session"] = session
	return soap

def remove_tmp_dir(tmp_dir):
	shutil.rmtree(tmp_dir)

def main():
	device_opt = ["login", "passwd", "port", "email", "no_status", "web"]

	atexit.register(atexit_handler)

	define_new_opts()
	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for OVH"
	docs["longdesc"] = "fence_ovh is an Power Fencing agent \
which can be used within OVH datecentre. \
Poweroff is simulated with a reboot into rescue-pro mode."

	docs["vendorurl"] = "http://www.ovh.net"
	show_docs(options, docs)

	if options["--action"] == "list":
		fail_usage("Action 'list' is not supported in this fence agent")

	if options["--action"] != "monitor" and not options["--plug"].endswith(".ovh.net"):
		options["--plug"] += ".ovh.net"

	if not options.has_key("--email"):
		fail_usage("You have to enter e-mail address which is notified by fence agent")

	run_delay(options)

	conn = soap_login(options)

	if options["--action"] == 'monitor':
		try:
			conn.service.logout(options["session"])
		except Exception:
			pass
		sys.exit(0)

	# Save datetime just before changing netboot
	before_netboot_reboot = datetime.now()

	if options["--action"] == 'off':
		# Reboot in Rescue-pro
		netboot_reboot(conn, options, OVH_RESCUE_PRO_NETBOOT_ID)
		time.sleep(STATUS_RESCUE_PRO_SLEEP)
	elif options["--action"] in  ['on', 'reboot']:
		# Reboot from HD
		netboot_reboot(conn, options, OVH_HARD_DISK_NETBOOT_ID)
		time.sleep(STATUS_HARD_DISK_SLEEP)

	# Save datetime just after reboot
	after_netboot_reboot = datetime.now()

	# Verify that action was completed sucesfully
	reboot_t = reboot_time(conn, options)

	logging.debug("reboot_start_end.start: %s\n",
		reboot_t.start.strftime('%Y-%m-%d %H:%M:%S'))
	logging.debug("before_netboot_reboot: %s\n",
		before_netboot_reboot.strftime('%Y-%m-%d %H:%M:%S'))
	logging.debug("reboot_start_end.end: %s\n",
		reboot_t.end.strftime('%Y-%m-%d %H:%M:%S'))
	logging.debug("after_netboot_reboot: %s\n",
		after_netboot_reboot.strftime('%Y-%m-%d %H:%M:%S'))

	if reboot_t.start < after_netboot_reboot < reboot_t.end:
		result = 0
		logging.debug("Netboot reboot went OK.\n")
	else:
		result = 1
		logging.debug("ERROR: Netboot reboot wasn't OK.\n")

	try:
		conn.service.logout(options["session"])
	except Exception:
		pass

	sys.exit(result)

if __name__ == "__main__":
	main()
