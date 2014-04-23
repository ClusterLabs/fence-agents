#!/usr/bin/python -tt

# The Following agent has been tested on:
# - Cisco MDS UROS 9134 FC (1 Slot) Chassis ("1/2/4 10 Gbps FC/Supervisor-2") Motorola, e500v2
#   with BIOS 1.0.16, kickstart 4.1(1c), system 4.1(1c)
# - Cisco MDS 9124 (1 Slot) Chassis ("1/2/4 Gbps FC/Supervisor-2") Motorola, e500
#   with BIOS 1.0.16, kickstart 4.1(1c), system 4.1(1c)

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, array_to_dict
from fencing_snmp import FencingSnmp

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="Cisco MDS 9xxx SNMP fence agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

### CONSTANTS ###
# Cisco admin status
PORT_ADMIN_STATUS_OID = ".1.3.6.1.2.1.75.1.2.2.1.1"

# IF-MIB trees for alias, status and port
ALIASES_OID = ".1.3.6.1.2.1.31.1.1.1.18"
PORTS_OID = ".1.3.6.1.2.1.2.2.1.2"

### GLOBAL VARIABLES ###
# OID converted from fc port name (fc(x)/(y))
PORT_OID = ""

### FUNCTIONS ###

# Convert cisco port name (fc(x)/(y)) to OID
def cisco_port2oid(port):
	port = port.lower()

	nums = re.match(r'^fc(\d+)/(\d+)$', port)

	if nums and len(nums.groups()) == 2:
		return "%s.%d.%d"% (PORT_ADMIN_STATUS_OID, int(nums.group(1))+21, int(nums.group(2))-1)
	else:
		fail_usage("Mangled port number: %s"%(port))

def get_power_status(conn, options):
	(_, status) = conn.get(PORT_OID)
	return status == "1" and "on" or "off"

def set_power_status(conn, options):
	conn.set(PORT_OID, (options["--action"] == "on" and 1 or 2))

def get_outlets_status(conn, options):
	result = {}

	res_fc = conn.walk(PORTS_OID, 30)
	res_aliases = array_to_dict(conn.walk(ALIASES_OID, 30))

	fc_re = re.compile(r'^"fc\d+/\d+"$')

	for x in res_fc:
		if fc_re.match(x[1]):
			port_num = x[0].split('.')[-1]

			port_name = x[1].strip('"')
			port_alias = (res_aliases.has_key(port_num) and res_aliases[port_num].strip('"') or "")
			port_status = ""
			result[port_name] = (port_alias, port_status)

	return result

# Main agent method
def main():
	global PORT_OID

	device_opt = ["fabric_fencing", "ipaddr", "login", "passwd", "no_login", "no_password", \
		       "port", "snmp_version", "community"]

	atexit.register(atexit_handler)

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Cisco MDS"
	docs["longdesc"] = "fence_cisco_mds is an I/O Fencing agent \
which can be used with any Cisco MDS 9000 series with SNMP enabled device."
	docs["vendorurl"] = "http://www.cisco.com"
	show_docs(options, docs)

	if not options["--action"] in ["list", "monitor"]:
		PORT_OID = cisco_port2oid(options["--plug"])

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)

if __name__ == "__main__":
	main()
