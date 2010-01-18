#!/usr/bin/python

##
## The Following Agent Has Been Tested On - LDOM 1.0.3
## The interface is backward compatible so it will work 
## with 1.0, 1.0.1 and .2 too.
## 
#####

import sys, re, pexpect
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="Logical Domains (LDoms) fence Agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

COMMAND_PROMPT_REG="\[PEXPECT\]$"
COMMAND_PROMPT_NEW="[PEXPECT]"

# Start comunicating after login. Prepare good environment.
def start_communication(conn, options):
	conn.sendline ("PS1='"+COMMAND_PROMPT_NEW+"'")
	res=conn.expect([pexpect.TIMEOUT, COMMAND_PROMPT_REG],int(options["-Y"]))
	if res==0:
		#CSH stuff
		conn.sendline("set prompt='"+COMMAND_PROMPT_NEW+"'")
		conn.log_expect(options, COMMAND_PROMPT_REG,int(options["-Y"]))
	

def get_power_status(conn, options):
	try:
		start_communication(conn,options)
		
		conn.sendline("ldm ls")
		    
		conn.log_expect(options,COMMAND_PROMPT_REG,int(options["-Y"]))

		result={}

		#This is status of mini finite automata. 0 = we didn't found NAME and STATE, 1 = we did
		fa_status=0
		
		for line in conn.before.splitlines():
			domain=re.search("^(\S+)\s+(\S+)\s+.*$",line)

			if (domain!=None):
				if ((fa_status==0) and (domain.group(1)=="NAME") and (domain.group(2)=="STATE")):
					fa_status=1
				elif (fa_status==1):
					result[domain.group(1)]=("",(domain.group(2).lower()=="bound" and "off" or "on"))

	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

	if (not (options["-o"] in ['monitor','list'])):
		if (not (options["-n"] in result)):
			fail_usage("Failed: You have to enter existing logical domain!")
		else:
			return result[options["-n"]][1]
	else:
		return result

def set_power_status(conn, options):
	try:
		start_communication(conn,options)
         	
		cmd_line="ldm "+(options["-o"]=="on" and "start" or "stop -f")+" \""+options["-n"]+"\""
            	
		conn.sendline(cmd_line)
		    
		conn.log_expect(options,COMMAND_PROMPT_REG,int(options["-g"]))
		
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)
		
def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"secure",  "identity_file", "test" , "port", "cmd_prompt",
			"separator", "inet4_only", "inet6_only", "ipport",
			"power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)

	pinput = process_input(device_opt)
	pinput["-x"] = 1
	options = check_input(device_opt, pinput)

	## 
	## Fence agent specific defaults
	#####
	if (not options.has_key("-c")):
		options["-c"] = "\ $"
	
	docs = { }
	docs["shortdesc"] = "Fence agent for Sun LDOM"
	docs["longdesc"] = "fence_ldom is an I/O Fencing agent \
which can be used with LDoms virtual machines. This agent works \
so, that run ldm command on host machine. So ldm must be directly \
runnable.\
\n.P\n\
Very useful parameter is -c (or cmd_prompt in stdin mode). This \
must be set to something, what is displayed after successful login \
to host machine. Default string is space on end of string (default \
for root in bash). But (for example) csh use ], so in that case you \
must use parameter -c with argument ]. Very similar situation is, \
if you use bash and login to host machine with other user than \
root. Than prompt is $, so again, you must use parameter -c."
	docs["vendorurl"] = "http://www.sun.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	####
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status,get_power_status)

	##
	## Logout from system
	######
	try:
		conn.sendline("logout")
		conn.close()
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass

	sys.exit(result)		

if __name__ == "__main__":
	main()
