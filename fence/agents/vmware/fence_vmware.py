#!/usr/bin/python

#
# The Following agent has been tested on:
# vmrun 2.0.0 build-116503 (from VMware Server 2.0) against:
# 	VMware ESX 3.5 (works correctly)
# 	VMware Server 2.0.0 (works correctly)
#	VMware ESXi 3.5 update 2 (works correctly)
# 	VMware Server 1.0.7 (works but list/status show only running VMs)
#
# VI Perl API 1.6 against:
# 	VMware ESX 3.5
#	VMware ESXi 3.5 update 2
# 	VMware Virtual Center 2.5
#

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="VMware Agent using VI Perl API and/or VIX vmrun command"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

### CONSTANTS ####
# VMware type is ESX/ESXi/VC
VMWARE_TYPE_ESX=0
# VMware type is Server 1.x
VMWARE_TYPE_SERVER1=1
# VMware type is Server 2.x and/or ESX 3.5 up2, ESXi 3.5 up2, VC 2.5 up2
VMWARE_TYPE_SERVER2=2

# Minimum required version of vmrun command
VMRUN_MINIMUM_REQUIRED_VERSION=2

# Default path to vmhelper command
VMHELPER_COMMAND="fence_vmware_helper"
# Default path to vmrun command
VMRUN_COMMAND="/usr/bin/vmrun"
# Default type of vmware
VMWARE_DEFAULT_TYPE="esx"

#### GLOBAL VARIABLES ####
# Internal type. One of VMWARE_TYPE_, set by #vmware_check_vmware_type
vmware_internal_type=VMWARE_TYPE_ESX

# If ESX is disconnected, say, that VM is off (don't return previous state)
vmware_disconnected_hack=False

### FUNCTIONS ####

#Split string in simplified DSV format to array of items
def dsv_split(dsv_str):
	delimiter_c=':'
	escape_c='\\'

	res=[]
	status=0
	tmp_str=""

	for x in dsv_str:
		if (status==0):
			if (x==delimiter_c):
				res.append(tmp_str)
				tmp_str=""
			elif (x==escape_c):
				status=1
			else:
				tmp_str+=x
		elif (status==1):
			if (x==delimiter_c):
				tmp_str+=delimiter_c
			elif (x==escape_c):
				tmp_str+=escape_c
			else:
				tmp_str+=escape_c+x
			status=0

	if (tmp_str!=""):
		res.append(tmp_str)

	return res

# Quote string for proper existence in quoted string used for pexpect.run function
# Ex. test'this will return test'\''this. So pexpect run will really pass ' to argument
def quote_for_run(str):
	dstr=''

	for c in str:
		if c==r"'":
			dstr+="'\\''"
		else:
			dstr+=c

	return dstr

# Return string with command and additional parameters (something like vmrun -h 'host'
def vmware_prepare_command(options,add_login_params,additional_params):
	res=options["-e"]

	if (add_login_params):
		if (vmware_internal_type==VMWARE_TYPE_ESX):
			res+=" --server '%s' --username '%s' --password '%s' "%(quote_for_run(options["-a"]),
										quote_for_run(options["-l"]),
										quote_for_run(options["-p"]))
		elif (vmware_internal_type==VMWARE_TYPE_SERVER2):
			res+=" -h 'https://%s/sdk' -u '%s' -p '%s' -T server "%(quote_for_run(options["-a"]),
										quote_for_run(options["-l"]),
										quote_for_run(options["-p"]))
		elif (vmware_internal_type==VMWARE_TYPE_SERVER1):
			host_name_array=options["-a"].split(':')

			res+=" -h '%s' -u '%s' -p '%s' -T server1 "%(quote_for_run(host_name_array[0]),
								     quote_for_run(options["-l"]),
								     quote_for_run(options["-p"]))
			if (len(host_name_array)>1):
				res+="-P '%s' "%(quote_for_run(host_name_array[1]))

	if ((options.has_key("-s")) and (vmware_internal_type==VMWARE_TYPE_ESX)):
		res+="--datacenter '%s' "%(quote_for_run(options["-s"]))

	if (additional_params!=""):
		res+=additional_params

	return res

# Log message if user set verbose option
def vmware_log(options, message):
	if options["log"] >= LOG_MODE_VERBOSE:
		options["debug_fh"].write(message+"\n")

# Run command with timeout and parameters. Internaly uses vmware_prepare_command. Returns string
# with output from vmrun command. If something fails (command not found, exit code is not 0), fail_usage
# function is called (and never return).
def vmware_run_command(options,add_login_params,additional_params,additional_timeout):
	command=vmware_prepare_command(options,add_login_params,additional_params)

	try:
		vmware_log(options,command)

		(res_output,res_code)=pexpect.run(command,SHELL_TIMEOUT+LOGIN_TIMEOUT+additional_timeout,True)

		if (res_code==None):
			fail(EC_TIMED_OUT)
		if ((res_code!=0) and (add_login_params)):
			vmware_log(options,res_output)
			fail_usage("%s returned %s"%(options["-e"],res_output))
		else:
			vmware_log(options,res_output)

	except pexpect.ExceptionPexpect:
		fail_usage("Cannot run command %s"%(options["-e"]))

	return res_output

# Get outlet list with status as hash table. If you will use add_vm_name, only VM with vmname is
# returned. This is used in get_status function
def vmware_get_outlets_vi(conn, options, add_vm_name):
	outlets={}

	if (add_vm_name):
		all_machines=vmware_run_command(options,True,("--operation status --vmname '%s'"%(quote_for_run(options["-n"]))),0)
	else:
		all_machines=vmware_run_command(options,True,"--operation list",POWER_TIMEOUT)

	all_machines_array=all_machines.splitlines()

	for machine in all_machines_array:
		machine_array=dsv_split(machine)
		if (len(machine_array)==4):
			if (machine_array[0] in outlets):
				fail_usage("Failed. More machines with same name %s found!"%(machine_array[0]))

			if (vmware_disconnected_hack):
				outlets[machine_array[0]]=("",(
						((machine_array[2].lower() in ["poweredon"]) and
						 (machine_array[3].lower()=="connected"))
						and "on" or "off"))
			else:
				outlets[machine_array[0]]=("",((machine_array[2].lower() in ["poweredon"]) and "on" or "off"))
	return outlets

# Get outlet list with status as hash table.
def vmware_get_outlets_vix(conn,options):
	outlets={}

	running_machines=vmware_run_command(options,True,"list",0)
	running_machines_array=running_machines.splitlines()[1:]

	if (vmware_internal_type==VMWARE_TYPE_SERVER2):
		all_machines=vmware_run_command(options,True,"listRegisteredVM",0)
		all_machines_array=all_machines.splitlines()[1:]
	elif (vmware_internal_type==VMWARE_TYPE_SERVER1):
		all_machines_array=running_machines_array

	for machine in all_machines_array:
		if (machine!=""):
			outlets[machine]=("",((machine in running_machines_array) and "on" or "off"))

	return outlets

def get_outlets_status(conn, options):
	if (vmware_internal_type==VMWARE_TYPE_ESX):
		return vmware_get_outlets_vi(conn,options,False)
	if ((vmware_internal_type==VMWARE_TYPE_SERVER1) or (vmware_internal_type==VMWARE_TYPE_SERVER2)):
		return vmware_get_outlets_vix(conn,options)

def get_power_status(conn,options):
	if (vmware_internal_type==VMWARE_TYPE_ESX):
		outlets=vmware_get_outlets_vi(conn,options,True)
	else:
		outlets=get_outlets_status(conn,options,False)

	if ((vmware_internal_type==VMWARE_TYPE_SERVER2) or (vmware_internal_type==VMWARE_TYPE_ESX)):
		if (not (options["-n"] in outlets)):
			fail_usage("Failed: You have to enter existing name of virtual machine!")
		else:
			return outlets[options["-n"]][1]
	elif (vmware_internal_type==VMWARE_TYPE_SERVER1):
		return ((options["-n"] in outlets) and "on" or "off")

def set_power_status(conn, options):
	if (vmware_internal_type==VMWARE_TYPE_ESX):
		additional_params="--operation %s --vmname '%s'"%((options["-o"]=="on" and "on" or "off"),quote_for_run(options["-n"]))
	elif ((vmware_internal_type==VMWARE_TYPE_SERVER1) or (vmware_internal_type==VMWARE_TYPE_SERVER2)):
		additional_params="%s '%s'"%((options["-o"]=="on" and "start" or "stop"),quote_for_run(options["-n"]))
		if (options["-o"]=="off"):
			additional_params+=" hard"

	vmware_run_command(options,True,additional_params,POWER_TIMEOUT)

# Returns True, if user uses supported vmrun version (currently >=2.0.0) otherwise False.
def vmware_is_supported_vmrun_version(options):
	vmware_help_str=vmware_run_command(options,False,"",0)
	version_re=re.search("vmrun version (\d\.(\d[\.]*)*)",vmware_help_str.lower())
	if (version_re==None):
		    return False   # Looks like this "vmrun" is not real vmrun

	version_array=version_re.group(1).split(".")

	try:
		if (int(version_array[0])<VMRUN_MINIMUM_REQUIRED_VERSION):
			return False
	except Exception:
		return False

	return True

# Define new options
def vmware_define_defaults():
	all_opt["vmware_type"]["default"]=VMWARE_DEFAULT_TYPE

# Check vmware type, set vmware_internal_type to one of VMWARE_TYPE_ value and
# options["-e"] to path (if not specified)
def vmware_check_vmware_type(options):
	global vmware_internal_type

	options["-d"]=options["-d"].lower()

	if (options["-d"]=="esx"):
		vmware_internal_type=VMWARE_TYPE_ESX
		if (not options.has_key("-e")):
			options["-e"]=VMHELPER_COMMAND
	elif (options["-d"]=="server2"):
		vmware_internal_type=VMWARE_TYPE_SERVER2
		if (not options.has_key("-e")):
			options["-e"]=VMRUN_COMMAND
	elif (options["-d"]=="server1"):
		vmware_internal_type=VMWARE_TYPE_SERVER1
		if (not options.has_key("-e")):
			options["-e"]=VMRUN_COMMAND
	else:
		fail_usage("vmware_type can be esx,server2 or server1!")

# Main agent method
def main():
	device_opt = [ "help", "version", "agent", "quiet", "verbose", "debug",
		       "action", "ipaddr", "login", "passwd", "passwd_script",
		       "test", "port", "separator", "exec", "vmware_type",
		       "vmware_datacenter", "secure" ]

	atexit.register(atexit_handler)

	vmware_define_defaults()

	options = check_input(device_opt, process_input(device_opt))

	# Default is secure connection
	options["-x"] = 1

	show_docs(options)

	# Check vmware type and set path
	vmware_check_vmware_type(options)

	# Test user vmrun command version
	if ((vmware_internal_type==VMWARE_TYPE_SERVER1) or (vmware_internal_type==VMWARE_TYPE_SERVER2)):
		if (not (vmware_is_supported_vmrun_version(options))):
			fail_usage("Unsupported version of vmrun command! You must use at least version %d!"%(VMRUN_MINIMUM_REQUIRED_VERSION))

	# Operate the fencing device
	fence_action(None, options, set_power_status, get_power_status, get_outlets_status)

if __name__ == "__main__":
	main()
