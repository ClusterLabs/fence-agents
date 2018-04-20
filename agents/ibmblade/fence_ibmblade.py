#!@PYTHON@ -tt

import sys
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing_snmp import FencingSnmp

### CONSTANTS ###
# From fence_ibmblade.pl
STATUSES_OID = ".1.3.6.1.4.1.2.3.51.2.22.1.5.1.1.4" # remoteControlBladePowerState
CONTROL_OID = ".1.3.6.1.4.1.2.3.51.2.22.1.6.1.1.7" # powerOnOffBlade

# Status constants returned as value from SNMP
STATUS_DOWN = 0
STATUS_UP = 1

# Status constants to set as value to SNMP
STATUS_SET_OFF = 0
STATUS_SET_ON = 1

### FUNCTIONS ###

def get_power_status(conn, options):
	(_, status) = conn.get("%s.%s"% (STATUSES_OID, options["--plug"]))
	return status == str(STATUS_UP) and "on" or "off"

def set_power_status(conn, options):
	conn.set("%s.%s" % (CONTROL_OID, options["--plug"]),
			(options["--action"] == "on" and STATUS_SET_ON or STATUS_SET_OFF))

def get_outlets_status(conn, _):
	result = {}

	res_blades = conn.walk(STATUSES_OID, 30)

	for blade_info in res_blades:
		port_num = blade_info[0].split('.')[-1]

		port_alias = ""
		port_status = (blade_info[1] == str(STATUS_UP) and "on" or "off")

		result[port_num] = (port_alias, port_status)

	return result

# Main agent method
def main():
	device_opt = ["ipaddr", "login", "passwd", "no_login", "no_password", \
		       "port", "snmp_version", "snmp"]

	atexit.register(atexit_handler)

	all_opt["snmp_version"]["default"] = "1"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for IBM BladeCenter over SNMP"
	docs["longdesc"] = "fence_ibmblade is an I/O Fencing agent \
which can be used with IBM BladeCenter chassis. It issues SNMP Set \
request to BladeCenter chassis, rebooting, powering up or down \
the specified Blade Server."
	docs["vendorurl"] = "http://www.ibm.com"
	show_docs(options, docs)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)
if __name__ == "__main__":
	main()
