#!@PYTHON@ -tt

# Tested with an Intel MFSYS25 using firmware package 2.6 Should work with an
# MFSYS35 as well.
#
# Notes:
#
# The manual and firmware release notes says SNMP is read only. This is not
# true, as per the MIBs that ship with the firmware you can write to
# the bladePowerLed oid to control the servers.
#
# Thanks Matthew Kent for original agent and testing.

import sys
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing_snmp import FencingSnmp

### CONSTANTS ###
# From INTELCORPORATION-MULTI-FLEX-SERVER-BLADES-MIB.my that ships with
# firmware updates
STATUSES_OID = ".1.3.6.1.4.1.343.2.19.1.2.10.202.1.1.6"

# Status constants returned as value from SNMP
STATUS_UP = 2
STATUS_DOWN = 0

# Status constants to set as value to SNMP
STATUS_SET_ON = 2
STATUS_SET_OFF = 3

### FUNCTIONS ###

def get_power_status(conn, options):
	(_, status) = conn.get("%s.%s"% (STATUSES_OID, options["--plug"]))
	return status == str(STATUS_UP) and "on" or "off"

def set_power_status(conn, options):
	conn.set("%s.%s" % (STATUSES_OID, options["--plug"]),
			(options["--action"] == "on" and STATUS_SET_ON or STATUS_SET_OFF))

def get_outlets_status(conn, options):
	result = {}

	res_blades = conn.walk(STATUSES_OID, 30)

	for x in res_blades:
		port_num = x[0].split('.')[-1]

		port_alias = ""
		port_status = (x[1] == str(STATUS_UP) and "on" or "off")

		result[port_num] = (port_alias, port_status)

	return result

# Main agent method
def main():
	device_opt = ["ipaddr", "login", "passwd", "no_login", "no_password",
		       "port", "snmp_version", "snmp"]

	atexit.register(atexit_handler)

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Intel Modular"
	docs["longdesc"] = "fence_intelmodular is an I/O Fencing agent \
which can be used with Intel Modular device (tested on Intel MFSYS25, should \
work with MFSYS35 as well). \
\n.P\n\
Note: Since firmware update version 2.7, SNMP v2 write support is \
removed, and replaced by SNMP v3 support. So agent now has default \
SNMP version 3. If you are using older firmware, please supply -d \
for command line and snmp_version option for your cluster.conf."
	docs["vendorurl"] = "http://www.intel.com"
	show_docs(options, docs)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)

if __name__ == "__main__":
	main()
