#!/usr/bin/python -tt

import sys
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing_snmp import FencingSnmp

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="Emerson SNMP fence agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

### CONSTANTS ###
STATUSES_OID = ".1.3.6.1.4.1.476.1.42.3.8.50.20.1.95"
CONTROL_OID = ".1.3.6.1.4.1.476.1.42.3.8.50.20.1.100"
NAMES_OID = ".1.3.6.1.4.1.476.1.42.3.8.50.20.1.10"

# Status constants returned as value from SNMP
STATUS_DOWN = 1
STATUS_UP = 2

# Status constants to set as value to SNMP
STATUS_SET_OFF = 0
STATUS_SET_ON = 1

def get_power_status(conn, options):
	(_, status) = conn.get("%s.%s"% (STATUSES_OID, options["--plug"]))
	return status == str(STATUS_UP) and "on" or "off"

def set_power_status(conn, options):
	conn.set("%s.%s" % (CONTROL_OID, options["--plug"]),
			(options["--action"] == "on" and STATUS_SET_ON or STATUS_SET_OFF))

def get_outlets_status(conn, _):
	result = {}
	res_outlet = conn.walk(STATUSES_OID, 30)

	for outlet_info in res_outlet:
		port_num = ".".join(outlet_info[0].split('.')[-3:])
		port_alias = conn.get("%s.%s"% (NAMES_OID, port_num))[1]
		port_status = (outlet_info[1] == str(STATUS_UP) and "on" or "off")
		result[port_num] = (port_alias, port_status)
	return result

def main():
	device_opt = ["ipaddr", "login", "passwd", "no_login", "no_password", \
		       "port", "snmp_version", "community"]

	atexit.register(atexit_handler)

	all_opt["power_wait"]["default"] = "5"
	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Emerson over SNMP"
	docs["longdesc"] = "fence_emerson is an I/O Fencing agent \
	which can be used with MPX and MPH2 managed rack PDU."
	docs["vendorurl"] = "http://www.emersonnetworkpower.com"
	show_docs(options, docs)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)
if __name__ == "__main__":
	main()
