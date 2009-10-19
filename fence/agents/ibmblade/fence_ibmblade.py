#!/usr/bin/python

import sys, re, pexpect
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing_snmp import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="IBM Blade SNMP fence agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

### CONSTANTS ###
# From fence_ibmblade.pl
STATUSES_OID=".1.3.6.1.4.1.2.3.51.2.22.1.5.1.1.4" # remoteControlBladePowerState
CONTROL_OID=".1.3.6.1.4.1.2.3.51.2.22.1.6.1.1.7" # powerOnOffBlade

# Status constants returned as value from SNMP
STATUS_DOWN=0
STATUS_UP=1

# Status constants to set as value to SNMP
STATUS_SET_OFF=0
STATUS_SET_ON=1

### FUNCTIONS ###

def get_power_status(conn,options):
	(oid,status)=conn.get("%s.%s"%(STATUSES_OID,options["-n"]))
	return (status==str(STATUS_UP) and "on" or "off")

def set_power_status(conn, options):
	conn.set("%s.%s"%(CONTROL_OID,options["-n"]),(options["-o"]=="on" and STATUS_SET_ON or STATUS_SET_OFF))

def get_outlets_status(conn, options):
	result={}

	res_blades=conn.walk(STATUSES_OID,30)

	for x in res_blades:
		port_num=x[0].split('.')[-1]

		port_alias=""
		port_status=(x[1]==str(STATUS_UP) and "on" or "off")

		result[port_num]=(port_alias,port_status)

	return result

# Define new options
def ibmblade_define_defaults():
	all_opt["snmp_version"]["default"]="1"

# Main agent method
def main():
	global port_oid

	device_opt = [ "help", "version", "agent", "quiet", "verbose", "debug",
		       "action", "ipaddr", "login", "passwd", "passwd_script",
		       "test", "port", "separator", "no_login", "no_password",
		       "snmp_version", "community", "snmp_auth_prot", "snmp_sec_level",
		       "snmp_priv_prot", "snmp_priv_passwd", "snmp_priv_passwd_script",
		       "udpport","inet4_only","inet6_only",
		       "power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)

	snmp_define_defaults ()
	ibmblade_define_defaults()

	options=check_input(device_opt,process_input(device_opt))

	docs = { }
	docs["shortdesc"] = "Fence agent for IBM BladeCenter over SNMP"
	docs["longdesc"] = ""
	show_docs(options, docs)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)
if __name__ == "__main__":
	main()
