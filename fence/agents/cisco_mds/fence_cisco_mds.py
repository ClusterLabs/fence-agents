#!/usr/bin/python

# The Following agent has been tested on:
# - Cisco MDS UROS 9134 FC (1 Slot) Chassis ("1/2/4 10 Gbps FC/Supervisor-2") Motorola, e500v2
#   with BIOS 1.0.16, kickstart 4.1(1c), system 4.1(1c)
# - Cisco MDS 9124 (1 Slot) Chassis ("1/2/4 Gbps FC/Supervisor-2") Motorola, e500
#   with BIOS 1.0.16, kickstart 4.1(1c), system 4.1(1c)

import sys, re, pexpect
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing_snmp import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="Cisco MDS 9xxx SNMP fence agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

### CONSTANTS ###
# Cisco admin status
PORT_ADMIN_STATUS_OID=".1.3.6.1.2.1.75.1.2.2.1.1"

# IF-MIB trees for alias, status and port
ALIASES_OID=".1.3.6.1.2.1.31.1.1.1.18"
PORTS_OID=".1.3.6.1.2.1.2.2.1.2"

### GLOBAL VARIABLES ###
# OID converted from fc port name (fc(x)/(y))
port_oid=""

### FUNCTIONS ###

# Convert cisco port name (fc(x)/(y)) to OID
def cisco_port2oid(port):
	port=port.lower()

	nums=re.match('^fc(\d+)/(\d+)$',port)

	if ((nums) and (len(nums.groups()))==2):
		return "%s.%d.%d"%(PORT_ADMIN_STATUS_OID,int(nums.group(1))+21,int(nums.group(2))-1)
	else:
		fail_usage("Mangled port number: %s"%(port))

def get_power_status(conn,options):
	global port_oid

	(oid,status)=conn.get(port_oid)
	return (status=="1" and "on" or "off")

def set_power_status(conn, options):
	global port_oid

	conn.set(port_oid,(options["-o"]=="on" and 1 or 2))

# Convert array of format [[key1, value1], [key2, value2], ... [keyN, valueN]] to dict, where key is
# in format a.b.c.d...z and returned dict has key only z
def array_to_dict(ar):
	return dict(map(lambda y:[y[0].split('.')[-1],y[1]],ar))

def get_outlets_status(conn, options):
	result={}

	res_fc=conn.walk(PORTS_OID,30)
	res_aliases=array_to_dict(conn.walk(ALIASES_OID,30))

	fc_re=re.compile('^"fc\d+/\d+"$')

	for x in res_fc:
		if fc_re.match(x[1]):
			port_num=x[0].split('.')[-1]

			port_name=x[1].strip('"')
			port_alias=(res_aliases.has_key(port_num) and res_aliases[port_num].strip('"') or "")
			port_status=""
			result[port_name]=(port_alias,port_status)

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
	options=process_input(device_opt)

	# Emulate enable/disable functionality
	if (options.has_key("-o")):
		options["-o"]=options["-o"].lower()

		if (options["-o"]=="enable"):
			options["-o"]="on"
		if (options["-o"]=="disable"):
			options["-o"]="off"
	else:
		options["-o"]="off"

	options = check_input(device_opt, options)

	show_docs(options)

	if (not (options["-o"] in ["list","monitor"])):
		port_oid=cisco_port2oid(options["-n"])

	# Operate the fencing device
	fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

if __name__ == "__main__":
	main()
