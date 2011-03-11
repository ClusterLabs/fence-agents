#!/usr/bin/python

# The Following agent has been tested on:
# - Eaton ePDU managed - SNMP v1

import sys, re, pexpect
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing_snmp import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="Eaton SNMP fence agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

### CONSTANTS ###
# oid defining fence device
OID_SYS_OBJECT_ID='.1.3.6.1.2.1.1.2.0'

### GLOBAL VARIABLES ###
# Device - see EatonManagedePDU
device=None

# Port ID
port_id=None
# Switch ID
switch_id=None

# Classes describing Device params
class EatonManagedePDU:
	status_oid=      '.1.3.6.1.4.1.534.6.6.6.1.2.2.1.3.%d'
	control_oid=     '.1.3.6.1.4.1.534.6.6.6.1.2.2.1.3.%d'
	outlet_table_oid='.1.3.6.1.4.1.534.6.6.6.1.2.2.1.1'
	ident_str="Eaton Managed ePDU"
	state_off=0
	state_on=1
	state_cycling=2
	turn_off=0
	turn_on=1
	turn_cycle=2
	# FIXME: what's this?
	has_switches=False

### FUNCTIONS ###
def eaton_set_device(conn,options):
	global device

	agents_dir={'.1.3.6.1.4.1.534.6.6.6':EatonManagedePDU}

	# First resolve type of Eaton
	eaton_type=conn.walk(OID_SYS_OBJECT_ID)

	if (not ((len(eaton_type)==1) and (agents_dir.has_key(eaton_type[0][1])))):
		eaton_type=[[None,None]]

	device=agents_dir[eaton_type[0][1]]

	conn.log_command("Trying %s"%(device.ident_str))

def eaton_resolv_port_id(conn,options):
	global port_id,switch_id,device

	if (device==None):
		eaton_set_device(conn,options)

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
		eaton_resolv_port_id(conn,options)

	oid=((device.has_switches) and device.status_oid%(switch_id,port_id) or device.status_oid%(port_id))

	(oid,status)=conn.get(oid)
	return (status==str(device.state_on) and "on" or "off")

def set_power_status(conn, options):
	global port_id,switch_id,device

	if (port_id==None):
		eaton_resolv_port_id(conn,options)

	oid=((device.has_switches) and device.control_oid%(switch_id,port_id) or device.control_oid%(port_id))

	conn.set(oid,(options["-o"]=="on" and device.turn_on or device.turn_off))


def get_outlets_status(conn, options):
	global device

	result={}

	if (device==None):
		eaton_set_device(conn,options)

	res_ports=conn.walk(device.outlet_table_oid,30)

	for x in res_ports:
		t=x[0].split('.')

		# Plug indexing start from zero, so we substract '1' from the
		# user's given plug number
		port_num=str(int(((device.has_switches) and "%s:%s"%(t[len(t)-3],t[len(t)-1]) or "%s"%(t[len(t)-1]))) + 1)

                # Plug indexing start from zero, so we add '1'
                # for the user's exposed plug number
                port_name=str(int(x[1].strip('"')) + 1)
                port_status=""
                result[port_num]=(port_name,port_status)

        return result

# Define new options
def eaton_snmp_define_defaults():
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
	eaton_snmp_define_defaults()

	options=check_input(device_opt,process_input(device_opt))

        ## Support for -n [switch]:[plug] notation that was used before
	if ((options.has_key("-n")) and (-1 != options["-n"].find(":"))):
		(switch, plug) = options["-n"].split(":", 1)
		if ((switch.isdigit()) and (plug.isdigit())):
		        options["-s"] = switch
			options["-n"] = plug

	if (not (options.has_key("-s"))):
		options["-s"]="1"

	# Plug indexing start from zero, so we substract '1' from the
	# user's given plug number
	if ((options.has_key("-n")) and (options["-n"].isdigit())):
		options["-n"] = str(int(options["-n"]) - 1)

	docs = { }
	docs["shortdesc"] = "Fence agent for Eaton over SNMP"
	docs["longdesc"] = "fence_eaton_snmp is an I/O Fencing agent \
which can be used with the Eaton network power switch. It logs \
into a device via SNMP and reboots a specified outlet. It supports \
SNMP v1 and v3 with all combinations of  authenticity/privacy settings."
	docs["vendorurl"] = "http://powerquality.eaton.com"
	show_docs(options, docs)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)
if __name__ == "__main__":
	main()
