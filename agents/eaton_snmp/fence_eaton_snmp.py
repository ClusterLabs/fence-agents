#!@PYTHON@ -tt

# The Following agent has been tested on:
# - Eaton ePDU Managed - SNMP v1
#   EATON | Powerware ePDU model: Managed ePDU (PW104MA0UB99), firmware: 01.01.01
# - Eaton ePDU Switched - SNMP v1
#   EATON | Powerware ePDU model: Switched ePDU (IPV3600), firmware: 2.0.K

import sys
import atexit
import logging
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage
from fencing_snmp import FencingSnmp

### CONSTANTS ###
# oid defining fence device
OID_SYS_OBJECT_ID = '.1.3.6.1.2.1.1.2.0'

### GLOBAL VARIABLES ###
# Device - see EatonManagedePDU, EatonSwitchedePDU
device = None

# Port ID
port_id = None
# Switch ID
switch_id = None

# Did we issue a set before get (to adjust OID with Switched ePDU)
after_set = False

# Classes describing Device params
# Managed ePDU
class EatonManagedePDU(object):
	status_oid =       '.1.3.6.1.4.1.534.6.6.6.1.2.2.1.3.%d'
	control_oid =      '.1.3.6.1.4.1.534.6.6.6.1.2.2.1.3.%d'
	outlet_table_oid = '.1.3.6.1.4.1.534.6.6.6.1.2.2.1.1'
	ident_str = "Eaton Managed ePDU"
	state_off = 0
	state_on = 1
	state_cycling = 2	# FIXME: not usable with fence-agents
	turn_off = 0
	turn_on = 1
	turn_cycle = 2		# FIXME: not usable with fence-agents
	has_switches = False

# Switched ePDU (Pulizzi 2)
# NOTE: sysOID reports "20677.1", while data are actually at "20677.2"
class EatonSwitchedePDU(object):
	status_oid =       '.1.3.6.1.4.1.20677.2.6.3.%d.0'
	control_oid =      '.1.3.6.1.4.1.20677.2.6.2.%d.0'
	outlet_table_oid = '.1.3.6.1.4.1.20677.2.6.3'
	ident_str = "Eaton Switched ePDU"
	state_off = 2
	state_on = 1
	state_cycling = 0 # Note: this status doesn't exist on this device
	turn_off = 2
	turn_on = 1
	turn_cycle = 3	# FIXME: not usable with fence-agents
	has_switches = False

### FUNCTIONS ###
def eaton_set_device(conn):
	global device

	agents_dir = {'.1.3.6.1.4.1.534.6.6.6':EatonManagedePDU,
				'.1.3.6.1.4.1.20677.1':EatonSwitchedePDU,
				'.1.3.6.1.4.1.20677.2':EatonSwitchedePDU}

	# First resolve type of Eaton
	eaton_type = conn.walk(OID_SYS_OBJECT_ID)

	if not ((len(eaton_type) == 1) and (eaton_type[0][1] in agents_dir)):
		eaton_type = [[None, None]]

	device = agents_dir[eaton_type[0][1]]

	logging.debug("Trying %s"%(device.ident_str))

def eaton_resolv_port_id(conn, options):
	global port_id, switch_id

	if device == None:
		eaton_set_device(conn)

	# Restore the increment, that was removed in main for ePDU Managed
	if device.ident_str == "Eaton Switched ePDU":
		options["--plug"] = str(int(options["--plug"]) + 1)

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
					if device.ident_str == "Eaton Switched ePDU":
						port_id = int(t[len(t)-3])
					else:
						port_id = int(t[len(t)-1])

	if port_id == None:
		# Restore index offset, to provide a valid error output on Managed ePDU
		if device.ident_str != "Eaton Switched ePDU":
			options["--plug"] = str(int(options["--plug"]) + 1)
		fail_usage("Can't find port with name %s!"%(options["--plug"]))

def get_power_status(conn, options):
	global port_id, after_set

	if port_id == None:
		eaton_resolv_port_id(conn, options)

	# Ajust OID for Switched ePDU when the get is after a set
	if after_set and device.ident_str == "Eaton Switched ePDU":
		port_id -= 1
		after_set = False

	oid = ((device.has_switches) and device.status_oid%(switch_id, port_id) or device.status_oid%(port_id))

	try:
		(oid, status) = conn.get(oid)
		if status == str(device.state_on):
			return "on"
		elif status == str(device.state_off):
			return "off"
		else:
			return None
	except Exception:
		return None

def set_power_status(conn, options):
	global port_id, after_set

	after_set = True

	if port_id == None:
		eaton_resolv_port_id(conn, options)

	# Controls start at #2 on Switched ePDU, since #1 is the global command
	if device.ident_str == "Eaton Switched ePDU":
		port_id = int(port_id)+1

	oid = ((device.has_switches) and device.control_oid%(switch_id, port_id) or device.control_oid%(port_id))

	conn.set(oid, (options["--action"] == "on" and device.turn_on or device.turn_off))


def get_outlets_status(conn, options):
	outletCount = 0
	result = {}

	if device == None:
		eaton_set_device(conn)

	res_ports = conn.walk(device.outlet_table_oid, 30)

	for x in res_ports:
		outletCount += 1
		status = x[1]
		t = x[0].split('.')

		# Plug indexing start from zero, so we substract '1' from the
		# user's given plug number
		if device.ident_str == "Eaton Managed ePDU":
			port_num = str(int(((device.has_switches) and
					"%s:%s"%(t[len(t)-3], t[len(t)-1]) or "%s"%(t[len(t)-1]))) + 1)

			# Plug indexing start from zero, so we add '1'
			# for the user's exposed plug number
			port_name = str(int(x[1].strip('"')) + 1)
			port_status = ""
			result[port_num] = (port_name, port_status)
		else:
			# Switched ePDU do not propose an outletCount OID!
			# Invalid status (ie value == '0'), retrieved via the walk,
			# means the outlet is absent
			port_num = str(outletCount)
			port_name = str(outletCount)
			port_status = ""
			if status != '0':
				result[port_num] = (port_name, port_status)

	return result

# Main agent method
def main():
	device_opt = ["ipaddr", "login", "passwd", "no_login", "no_password", \
		       "port", "snmp_version", "snmp"]

	atexit.register(atexit_handler)

	all_opt["switch"]["default"] = 1
	all_opt["power_wait"]["default"] = 2
	all_opt["snmp_version"]["default"] = "1"
	all_opt["community"]["default"] = "private"
	options = check_input(device_opt, process_input(device_opt))

	# Plug indexing start from zero on ePDU Managed, so we substract '1' from
	# the user's given plug number.
	# For Switched ePDU, we will add this back again later.
	if "--plug" in options and options["--plug"].isdigit():
		options["--plug"] = str(int(options["--plug"]) - 1)

	docs = {}
	docs["shortdesc"] = "Fence agent for Eaton over SNMP"
	docs["longdesc"] = "fence_eaton_snmp is an I/O Fencing agent \
which can be used with the Eaton network power switch. It logs \
into a device via SNMP and reboots a specified outlet. It supports \
SNMP v1 and v3 with all combinations of  authenticity/privacy settings."
	docs["vendorurl"] = "http://powerquality.eaton.com"
	show_docs(options, docs)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)
if __name__ == "__main__":
	main()
