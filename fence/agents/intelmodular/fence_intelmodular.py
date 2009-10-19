#!/usr/bin/python

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

import sys, re, pexpect
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing_snmp import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="Intel Modular SNMP fence agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

### CONSTANTS ###
# From INTELCORPORATION-MULTI-FLEX-SERVER-BLADES-MIB.my that ships with
# firmware updates
STATUSES_OID=".1.3.6.1.4.1.343.2.19.1.2.10.202.1.1.6"

# Status constants returned as value from SNMP
STATUS_UP=2
STATUS_DOWN=0

# Status constants to set as value to SNMP
STATUS_SET_ON=2
STATUS_SET_OFF=3

### FUNCTIONS ###

def get_power_status(conn,options):
	(oid,status)=conn.get("%s.%s"%(STATUSES_OID,options["-n"]))
	return (status==str(STATUS_UP) and "on" or "off")

def set_power_status(conn, options):
	conn.set("%s.%s"%(STATUSES_OID,options["-n"]),(options["-o"]=="on" and STATUS_SET_ON or STATUS_SET_OFF))

def get_outlets_status(conn, options):
	result={}

	res_blades=conn.walk(STATUSES_OID,30)

	for x in res_blades:
		port_num=x[0].split('.')[-1]

		port_alias=""
		port_status=(x[1]==str(STATUS_UP) and "on" or "off")

		result[port_num]=(port_alias,port_status)

	return result

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

	options=check_input(device_opt,process_input(device_opt))

	show_docs(options)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)
	
	sys.exit(result)

if __name__ == "__main__":
	main()
