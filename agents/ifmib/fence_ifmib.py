#!@PYTHON@ -tt

# The Following agent has been tested on:
# - Cisco MDS UROS 9134 FC (1 Slot) Chassis ("1/2/4 10 Gbps FC/Supervisor-2") Motorola, e500v2
#   with BIOS 1.0.16, kickstart 4.1(1c), system 4.1(1c)
# - Cisco MDS 9124 (1 Slot) Chassis ("1/2/4 Gbps FC/Supervisor-2") Motorola, e500
#   with BIOS 1.0.16, kickstart 4.1(1c), system 4.1(1c)
# - Partially with APC PDU (Network Management Card AOS v2.7.0, Rack PDU APP v2.7.3)
#   Only lance if is visible

import sys
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, array_to_dict
from fencing_snmp import FencingSnmp

### CONSTANTS ###
# IF-MIB trees for alias, status and port
ALIASES_OID = ".1.3.6.1.2.1.31.1.1.1.18"
PORTS_OID = ".1.3.6.1.2.1.2.2.1.2"
STATUSES_OID = ".1.3.6.1.2.1.2.2.1.7"

# Status constants returned as value from SNMP
STATUS_UP = 1
STATUS_DOWN = 2
STATUS_TESTING = 3

### GLOBAL VARIABLES ###
# Port number converted from port name or index
port_num = None

### FUNCTIONS ###

# Convert port index or name to port index
def port2index(conn, port):
	res = None

	if port.isdigit():
		res = int(port)
	else:
		ports = conn.walk(PORTS_OID, 30)

		for x in ports:
			if x[1].strip('"') == port:
				res = int(x[0].split('.')[-1])
				break

	if res == None:
		fail_usage("Can't find port with name %s!"%(port))

	return res

def get_power_status(conn, options):
	global port_num

	if port_num == None:
		port_num = port2index(conn, options["--plug"])

	(_, status) = conn.get("%s.%d"%(STATUSES_OID, port_num))
	return status == str(STATUS_UP) and "on" or "off"

def set_power_status(conn, options):
	global port_num

	if port_num == None:
		port_num = port2index(conn, options["--plug"])

	conn.set("%s.%d" % (STATUSES_OID, port_num), (options["--action"] == "on" and STATUS_UP or STATUS_DOWN))

def get_outlets_status(conn, options):
	result = {}

	res_fc = conn.walk(PORTS_OID, 30)
	res_aliases = array_to_dict(conn.walk(ALIASES_OID, 30))

	for x in res_fc:
		port_number = x[0].split('.')[-1]

		port_name = x[1].strip('"')
		port_alias = (port_number in res_aliases and res_aliases[port_number].strip('"') or "")
		port_status = ""
		result[port_name] = (port_alias, port_status)

	return result

# Main agent method
def main():
	device_opt = ["fabric_fencing", "ipaddr", "login", "passwd", "no_login", "no_password", \
		       "port", "snmp_version", "snmp"]

	atexit.register(atexit_handler)

	all_opt["snmp_version"]["default"] = "2c"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for IF MIB"
	docs["longdesc"] = "fence_ifmib is an I/O Fencing agent \
which can be used with any SNMP IF-MIB capable device. \
\n.P\n\
It was written with managed ethernet switches in mind, in order to \
fence iSCSI SAN connections. However, there are many devices that \
support the IF-MIB interface. The agent uses IF-MIB::ifAdminStatus \
to control the state of an interface."
	docs["vendorurl"] = "http://www.ietf.org/wg/concluded/ifmib.html"
	show_docs(options, docs)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)

if __name__ == "__main__":
	main()
