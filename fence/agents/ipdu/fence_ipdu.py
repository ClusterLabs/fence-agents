#!/usr/bin/python -tt

# The Following agent has been tested on:
#   IBM iPDU model 46M4002
#   Firmware release OPDP_sIBM_v01.2_1
#

import sys
import atexit
import logging
sys.path.append("/usr/share/fence")
from fencing import *
from fencing import fail_usage
from fencing_snmp import FencingSnmp

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="IBM iPDU SNMP fence agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

### CONSTANTS ###
# oid defining fence device
OID_SYS_OBJECT_ID = '.1.3.6.1.2.1.1.2.0'

### GLOBAL VARIABLES ###
# Device - see IBM iPDU
device = None

# Port ID
port_id = None
# Switch ID
switch_id = None

# Classes describing Device params
class IBMiPDU(object):
	# iPDU
	status_oid =       '.1.3.6.1.4.1.2.6.223.8.2.2.1.11.%d'
	control_oid =      '.1.3.6.1.4.1.2.6.223.8.2.2.1.11.%d'
	outlet_table_oid = '.1.3.6.1.4.1.2.6.223.8.2.2.1.2'
	ident_str = "IBM iPDU"
	state_on = 1
	state_off = 0
	turn_on = 1
	turn_off = 0
	has_switches = False

### FUNCTIONS ###
def ipdu_set_device(conn, options):
	global device

	agents_dir = {'.1.3.6.1.4.1.2.6.223':IBMiPDU,
		    None:IBMiPDU}

	# First resolve type of PDU device
	pdu_type = conn.walk(OID_SYS_OBJECT_ID)

	if not ((len(pdu_type) == 1) and (agents_dir.has_key(pdu_type[0][1]))):
		pdu_type = [[None, None]]

	device = agents_dir[pdu_type[0][1]]

	logging.debug("Trying %s"%(device.ident_str))

def ipdu_resolv_port_id(conn, options):
	global port_id, switch_id

	if device == None:
		ipdu_set_device(conn, options)

	# Now we resolv port_id/switch_id
	if options["--plug"].isdigit() and ((not device.has_switches) or (options["--switch"].isdigit())):
		port_id = int(options["--plug"])

		if device.has_switches:
			switch_id = int(options["--switch"])
	else:
		table = conn.walk(device.outlet_table_oid, 30)

		for x in table:
			if x[1].strip('"') == options["--plug"]:
				t = x[0].split('.')
				if device.has_switches:
					port_id = int(t[len(t)-1])
					switch_id = int(t[len(t)-3])
				else:
					port_id = int(t[len(t)-1])

	if port_id == None:
		fail_usage("Can't find port with name %s!"%(options["--plug"]))

def get_power_status(conn, options):
	if port_id == None:
		ipdu_resolv_port_id(conn, options)

	oid = ((device.has_switches) and device.status_oid%(switch_id, port_id) or device.status_oid%(port_id))

	(oid, status) = conn.get(oid)
	return status == str(device.state_on) and "on" or "off"

def set_power_status(conn, options):
	if port_id == None:
		ipdu_resolv_port_id(conn, options)

	oid = ((device.has_switches) and device.control_oid%(switch_id, port_id) or device.control_oid%(port_id))

	conn.set(oid, (options["--action"] == "on" and device.turn_on or device.turn_off))


def get_outlets_status(conn, options):
	result = {}

	if device == None:
		ipdu_set_device(conn, options)

	res_ports = conn.walk(device.outlet_table_oid, 30)

	for x in res_ports:
		t = x[0].split('.')

		port_num = ((device.has_switches) and "%s:%s"%(t[len(t)-3], t[len(t)-1]) or "%s"%(t[len(t)-1]))

		port_name = x[1].strip('"')
		port_status = ""
		result[port_num] = (port_name, port_status)

	return result

# Main agent method
def main():
	global device

	device_opt = ["ipaddr", "login", "passwd", "no_login", "no_password", \
		       "port", "snmp_version", "community"]

	atexit.register(atexit_handler)

	all_opt["snmp_version"]["default"] = "3"
	all_opt["community"]["default"] = "private"
	all_opt["switch"]["default"] = "1"
	device = IBMiPDU

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for iPDU over SNMP"
	docs["longdesc"] = "fence_ipdu is an I/O Fencing agent \
which can be used with the IBM iPDU network power switch. It logs \
into a device via SNMP and reboots a specified outlet. It supports \
SNMP v3 with all combinations of authenticity/privacy settings."
	docs["vendorurl"] = "http://www.ibm.com"
	show_docs(options, docs)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)
if __name__ == "__main__":
	main()
