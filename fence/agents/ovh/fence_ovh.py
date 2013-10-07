#!/usr/bin/python
# Copyright 2013 Adrian Gibanel Lopez (bTactic)
# Adrian Gibanel improved this script at 2013 to add verification of success and to output metadata

# Based on:
# This is a fence agent for use at OVH
# As there are no other fence devices available, we must use OVH's SOAP API #Quick-and-dirty
# assemled by Dennis Busch, secofor GmbH, Germany
# This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 Unported License.

import sys, time
import shutil, tempfile
from datetime import datetime
from suds.client import Client
from suds.xsd.doctor import ImportDoctor, Import
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

OVH_RESCUE_PRO_NETBOOT_ID = '28'
OVH_HARD_DISK_NETBOOT_ID  = '1'

STATUS_HARD_DISK_SLEEP = 240 # Wait 4 minutes to SO to boot
STATUS_RESCUE_PRO_SLEEP = 150 # Wait 2 minutes 30 seconds to Rescue-Pro to run

def define_new_opts():
	all_opt["email"] = {
		"getopt" : "Z:",
		"longopt" : "email",
		"help" : "-Z, --email=<email>          email for reboot message: admin@domain.com",
		"required" : "1",
		"shortdesc" : "Reboot email",
		"default" : "",
		"order" : 1 }

def netboot_reboot(options, mode):
	conn = soap_login(options)

	# dedicatedNetbootModifyById changes the mode of the next reboot
	conn.service.dedicatedNetbootModifyById(options["session"], options["--plug"], mode, '', options["--email"])
 
	# dedicatedHardRebootDo initiates a hard reboot on the given node
	conn.service.dedicatedHardRebootDo(options["session"], options["--plug"], 'Fencing initiated by cluster', '', 'en')

	conn.logout(options["session"])

def reboot_time(options):
	conn = soap_login(options)

	result = conn.service.dedicatedHardRebootStatus(options["session"], options["--plug"])
	tmpstart = datetime.strptime(result.start,'%Y-%m-%d %H:%M:%S')
	tmpend = datetime.strptime(result.end,'%Y-%m-%d %H:%M:%S')
	result.start = tmpstart
	result.end = tmpend

	conn.logout(options["session"])

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
	except Exception, ex:
		fail(EC_LOGIN_DENIED)   

	options["session"] = session
	return soap

def remove_tmp_dir(tmp_dir):
	shutil.rmtree(tmp_dir)
	
def main():
	device_opt = [ "login", "passwd", "port", "email" ]

	atexit.register(atexit_handler)

	define_new_opts()
	options = check_input(device_opt, process_input(device_opt))

	docs = { }
	docs["shortdesc"] = "Fence agent for OVH"
	docs["longdesc"] = "fence_ovh is an Power Fencing agent \
which can be used within OVH datecentre. \
Poweroff is simulated with a reboot into rescue-pro mode."

	docs["vendorurl"] = "http://www.ovh.net"
	show_docs(options, docs)

	if options["--action"] in [ "list", "status"]:
		fail_usage("Action '" + options["--action"] + "' is not supported in this fence agent")

	if options["--plug"].endswith(".ovh.net") == False:
		options["--plug"] += ".ovh.net"

	if options.has_key("--email") == False:
		fail_usage("You have to enter e-mail address which is notified by fence agent")

	# Save datetime just before changing netboot
	before_netboot_reboot = datetime.now()

	if options["--action"] == 'off':
		# Reboot in Rescue-pro
		netboot_reboot(options,OVH_RESCUE_PRO_NETBOOT_ID)
		time.sleep(STATUS_RESCUE_PRO_SLEEP)
	elif options["--action"] in  ['on', 'reboot' ]:
		# Reboot from HD
		netboot_reboot(options,OVH_HARD_DISK_NETBOOT_ID)
		time.sleep(STATUS_HARD_DISK_SLEEP)

	# Save datetime just after reboot
	after_netboot_reboot = datetime.now()

	# Verify that action was completed sucesfully
	reboot_t = reboot_time(options)

	if options.has_key("--verbose"):
		options["debug_fh"].write("reboot_start_end.start: "+ reboot_t.start.strftime('%Y-%m-%d %H:%M:%S')+"\n")         
		options["debug_fh"].write("before_netboot_reboot: " + before_netboot_reboot.strftime('%Y-%m-%d %H:%M:%S')+"\n")
		options["debug_fh"].write("reboot_start_end.end: "  + reboot_t.end.strftime('%Y-%m-%d %H:%M:%S')+"\n")        
		options["debug_fh"].write("after_netboot_reboot: "  + after_netboot_reboot.strftime('%Y-%m-%d %H:%M:%S')+"\n")  
                
	if reboot_t.start < after_netboot_reboot < reboot_t.end:
		result = 0
		if options.has_key("--verbose"):
			options["debug_fh"].write("Netboot reboot went OK.\n")
	else:
		result = 1
		if options.has_key("--verbose"):
			options["debug_fh"].write("ERROR: Netboot reboot wasn't OK.\n")

	sys.exit(result)


if __name__ == "__main__":
	main()
