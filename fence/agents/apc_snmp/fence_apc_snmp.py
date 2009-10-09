#!/usr/bin/python

# The Following agent has been tested on:
# - APC Switched Rack PDU (MB:v3.7.0 PF:v2.7.0 PN:apc_hw02_aos_270.bin AF1:v2.7.3 AN1:apc_hw02_aos_270.bin
#    AF1:v2.7.3 AN1:apc_hw02_rpdu_273.bin MN:AP7930 HR:B2) - SNMP v1
# - APC Web/SNMP Management Card (MB:v3.8.6 PF:v3.5.8 PN:apc_hw02_aos_358.bin AF1:v3.5.7 AN1:apc_hw02_aos_358.bin
#    AF1:v3.5.7 AN1:apc_hw02_rpdu_357.bin MN:AP7900 HR:B2) - SNMP v1 and v3 (noAuthNoPrivacy,authNoPrivacy, authPrivacy)
# - APC Switched Rack PDU (MB:v3.7.0 PF:v2.7.0 PN:apc_hw02_aos_270.bin AF1:v2.7.3 AN1:apc_hw02_rpdu_273.bin
#    MN:AP7951 HR:B2) - SNMP v1

import sys, re, pexpect
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing_snmp import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="APC SNMP fence agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

### CONSTANTS ###
# oid defining fence device
OID_SYS_OBJECT_ID='.1.3.6.1.2.1.1.2.0'

### GLOBAL VARIABLES ###
# Device - see ApcRPDU, ApcMSP, ApcMS
device=None

# Port ID
port_id=None
# Switch ID
switch_id=None

# Classes describing Device params
class ApcRPDU:
	# Rack PDU
	status_oid=      '.1.3.6.1.4.1.318.1.1.12.3.5.1.1.4.%d'
	control_oid=     '.1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.%d'
	outlet_table_oid='.1.3.6.1.4.1.318.1.1.12.3.5.1.1.2'
	ident_str="APC rPDU"
	state_on=1
	state_off=2
	turn_on=1
	turn_off=2
	has_switches=False

class ApcMSP:
	# Master Switch+
	status_oid=      '.1.3.6.1.4.1.318.1.1.6.7.1.1.5.%d.1.%d'
	control_oid=     '.1.3.6.1.4.1.318.1.1.6.5.1.1.5.%d.1.%d'
	outlet_table_oid='.1.3.6.1.4.1.318.1.1.6.7.1.1.4'
	ident_str="APC Master Switch+"
	state_on=1
	state_off=2
	turn_on=1
	turn_off=3
	has_switches=True

class ApcMS:
	# Master Switch - seems oldest, but supported on every APC PDU
	status_oid=      '.1.3.6.1.4.1.318.1.1.4.4.2.1.3.%d'
	control_oid=     '.1.3.6.1.4.1.318.1.1.4.4.2.1.3.%d'
	outlet_table_oid='.1.3.6.1.4.1.318.1.1.4.4.2.1.4'
	ident_str="APC Master Switch (fallback)"
	state_on=1
	state_off=2
	turn_on=1
	turn_off=2
	has_switches=False

### FUNCTIONS ###
def apc_set_device(conn,options):
	global device

	agents_dir={'.1.3.6.1.4.1.318.1.3.4.5':ApcRPDU,
		    '.1.3.6.1.4.1.318.1.3.4.4':ApcMSP,
		    None:ApcMS}

	# First resolve type of APC
	apc_type=conn.walk(OID_SYS_OBJECT_ID)

	if (not ((len(apc_type)==1) and (agents_dir.has_key(apc_type[0][1])))):
		apc_type=[[None,None]]

	device=agents_dir[apc_type[0][1]]

	conn.log_command("Trying %s"%(device.ident_str))

def apc_resolv_port_id(conn,options):
	global port_id,switch_id,device

	if (device==None):
		apc_set_device(conn,options)

	# Now we resolv port_id/switch_id
	if ((options["-n"].isdigit()) and ((not device.has_switches) or (options["-s"].isdigit()))):
		port_id=int(options["-n"])

		if (device.has_switches):
			switch_id=int(options["-s"])
	else:
		table=conn.walk(device.outlet_table_oid,30)

		for x in table:
			if (x[1].strip('"')==options["-n"]):
				t=x[0].split('.')
				if (device.has_switches):
					port_id=int(t[len(t)-1])
					switch_id=int(t[len(t)-3])
				else:
					port_id=int(t[len(t)-1])

	if (port_id==None):
		fail_usage("Can't find port with name %s!"%(options["-n"]))

def get_power_status(conn,options):
	global port_id,switch_id,device

	if (port_id==None):
		apc_resolv_port_id(conn,options)

	oid=((device.has_switches) and device.status_oid%(switch_id,port_id) or device.status_oid%(port_id))

	(oid,status)=conn.get(oid)
	return (status==str(device.state_on) and "on" or "off")

def set_power_status(conn, options):
	global port_id,switch_id,device

	if (port_id==None):
		apc_resolv_port_id(conn,options)

	oid=((device.has_switches) and device.control_oid%(switch_id,port_id) or device.control_oid%(port_id))

	conn.set(oid,(options["-o"]=="on" and device.turn_on or device.turn_off))


def get_outlets_status(conn, options):
	global device

	result={}

	if (device==None):
		apc_set_device(conn,options)

	res_ports=conn.walk(device.outlet_table_oid,30)

	for x in res_ports:
		t=x[0].split('.')

		port_num=((device.has_switches) and "%s:%s"%(t[len(t)-3],t[len(t)-1]) or "%s"%(t[len(t)-1]))

                port_name=x[1].strip('"')
                port_status=""
                result[port_num]=(port_name,port_status)

        return result

# Define new options
def apc_snmp_define_defaults():
	all_opt["snmp_version"]["default"]="1"
	all_opt["community"]["default"]="private"

# Main agent method
def main():
	device_opt = [ "help", "version", "agent", "quiet", "verbose", "debug",
		       "action", "ipaddr", "login", "passwd", "passwd_script",
		       "test", "port", "separator", "no_login", "no_password",
		       "snmp_version", "community", "snmp_auth_prot", "snmp_sec_level",
		       "snmp_priv_prot", "snmp_priv_passwd", "snmp_priv_passwd_script",
		       "udpport","inet4_only","inet6_only",
		       "power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)

	snmp_define_defaults ()
	apc_snmp_define_defaults()

	options=check_input(device_opt,process_input(device_opt))

        ## Support for -n [switch]:[plug] notation that was used before
	if ((options.has_key("-n")) and (-1 != options["-n"].find(":"))):
		(switch, plug) = options["-n"].split(":", 1)
		if ((switch.isdigit()) and (plug.isdigit())):
		        options["-s"] = switch
			options["-n"] = plug

	if (not (options.has_key("-s"))):
		options["-s"]="1"

	show_docs(options)

	# Operate the fencing device
	fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

if __name__ == "__main__":
	main()
