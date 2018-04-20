#!@PYTHON@ -tt

# The Following agent has been tested on:
# - APC Switched Rack PDU - SNMP v1
#	(MB:v3.7.0 PF:v2.7.0 PN:apc_hw02_aos_270.bin AF1:v2.7.3
#	AN1:apc_hw02_aos_270.bin AF1:v2.7.3 AN1:apc_hw02_rpdu_273.bin MN:AP7930 HR:B2)
# - APC Web/SNMP Management Card - SNMP v1 and v3 (noAuthNoPrivacy,authNoPrivacy, authPrivacy)
#	(MB:v3.8.6 PF:v3.5.8 PN:apc_hw02_aos_358.bin AF1:v3.5.7
#       AN1:apc_hw02_aos_358.bin AF1:v3.5.7 AN1:apc_hw02_rpdu_357.bin MN:AP7900 HR:B2)
# - APC Switched Rack PDU - SNMP v1
#       (MB:v3.7.0 PF:v2.7.0 PN:apc_hw02_aos_270.bin AF1:v2.7.3
#       AN1:apc_hw02_rpdu_273.bin MN:AP7951 HR:B2)
# - Tripplite PDUMH20HVNET 12.04.0055 - SNMP v1, v2c, v3

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
# Device - see ApcRPDU, ApcMSP, ApcMS, TripplitePDU
device = None

# Port ID
port_id = None
# Switch ID
switch_id = None

# Classes describing Device params
class TripplitePDU(object):
        # Rack PDU
	status_oid =       '.1.3.6.1.4.1.850.10.2.3.5.1.2.1.%d'
	control_oid =      '.1.3.6.1.4.1.850.10.2.3.5.1.4.1.%d'
	outlet_table_oid = '.1.3.6.1.4.1.850.10.2.3.5.1.5'
	ident_str = "Tripplite"
	state_on = 2
	state_off = 1
	turn_on = 2
	turn_off = 1
	has_switches = False

class ApcRPDU(object):
	# Rack PDU
	status_oid =       '.1.3.6.1.4.1.318.1.1.12.3.5.1.1.4.%d'
	control_oid =      '.1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.%d'
	outlet_table_oid = '.1.3.6.1.4.1.318.1.1.12.3.5.1.1.2'
	ident_str = "APC rPDU"
	state_on = 1
	state_off = 2
	turn_on = 1
	turn_off = 2
	has_switches = False

class ApcMSP(object):
	# Master Switch+
	status_oid =       '.1.3.6.1.4.1.318.1.1.6.7.1.1.5.%d.1.%d'
	control_oid =      '.1.3.6.1.4.1.318.1.1.6.5.1.1.5.%d.1.%d'
	outlet_table_oid = '.1.3.6.1.4.1.318.1.1.6.7.1.1.4'
	ident_str = "APC Master Switch+"
	state_on = 1
	state_off = 2
	turn_on = 1
	turn_off = 3
	has_switches = True

class ApcMS(object):
	# Master Switch - seems oldest, but supported on every APC PDU
	status_oid =       '.1.3.6.1.4.1.318.1.1.4.4.2.1.3.%d'
	control_oid =      '.1.3.6.1.4.1.318.1.1.4.4.2.1.3.%d'
	outlet_table_oid = '.1.3.6.1.4.1.318.1.1.4.4.2.1.4'
	ident_str = "APC Master Switch (fallback)"
	state_on = 1
	state_off = 2
	turn_on = 1
	turn_off = 2
	has_switches = False

class ApcMS6(object):
	# Master Switch with 6.x firmware
	status_oid = '.1.3.6.1.4.1.318.1.1.4.4.2.1.3.%d'
	control_oid = '.1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.%d'
	outlet_table_oid = '1.3.6.1.4.1.318.1.1.4.4.2.1.4'
	ident_str = "APC Master Switch with firmware v6.x"
	state_on = 1
	state_off = 2
	turn_on = 1
	turn_off = 2
	has_switches = False

### FUNCTIONS ###
def apc_set_device(conn):
	global device

	agents_dir = {'.1.3.6.1.4.1.318.1.3.4.5':ApcRPDU,
		    '.1.3.6.1.4.1.318.1.3.4.4':ApcMSP,
                    '.1.3.6.1.4.1.850.1':TripplitePDU,
		    '.1.3.6.1.4.1.318.1.3.4.6':ApcMS6,
		    None:ApcMS}

	# First resolve type of APC
	apc_type = conn.walk(OID_SYS_OBJECT_ID)

	if not ((len(apc_type) == 1) and (apc_type[0][1] in agents_dir)):
		apc_type = [[None, None]]

	device = agents_dir[apc_type[0][1]]

	logging.debug("Trying %s"%(device.ident_str))

def apc_resolv_port_id(conn, options):
	global port_id, switch_id

	if device == None:
		apc_set_device(conn)

	# Now we resolv port_id/switch_id
	if (options["--plug"].isdigit()) and ((not device.has_switches) or (options["--switch"].isdigit())):
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
		apc_resolv_port_id(conn, options)

	oid = ((device.has_switches) and device.status_oid%(switch_id, port_id) or device.status_oid%(port_id))

	(oid, status) = conn.get(oid)
	return status == str(device.state_on) and "on" or "off"

def set_power_status(conn, options):
	if port_id == None:
		apc_resolv_port_id(conn, options)

	oid = ((device.has_switches) and device.control_oid%(switch_id, port_id) or device.control_oid%(port_id))

	conn.set(oid, (options["--action"] == "on" and device.turn_on or device.turn_off))


def get_outlets_status(conn, options):
	result = {}

	if device == None:
		apc_set_device(conn)

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
	device_opt = ["ipaddr", "login", "passwd", "no_login", "no_password", \
		       "port", "snmp_version", "snmp"]

	atexit.register(atexit_handler)

	all_opt["snmp_version"]["default"] = "1"
	all_opt["community"]["default"] = "private"

	options = check_input(device_opt, process_input(device_opt))

        ## Support for -n [switch]:[plug] notation that was used before
	if ("--plug" in options) and (-1 != options["--plug"].find(":")):
		(switch, plug) = options["--plug"].split(":", 1)
		if switch.isdigit() and plug.isdigit():
			options["--switch"] = switch
			options["--plug"] = plug

	if "--switch" not in options:
		options["--switch"] = "1"

	docs = {}
	docs["shortdesc"] = "Fence agent for APC, Tripplite PDU over SNMP"
	docs["longdesc"] = "fence_apc_snmp is an I/O Fencing agent \
which can be used with the APC network power switch or Tripplite PDU devices.\
It logs into a device via SNMP and reboots a specified outlet. It supports \
SNMP v1, v2c, v3 with all combinations of  authenticity/privacy settings."
	docs["vendorurl"] = "http://www.apc.com"
	docs["symlink"] = [("fence_tripplite_snmp", "Fence agent for Tripplife over SNMP")]
	show_docs(options, docs)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)
if __name__ == "__main__":
	main()
