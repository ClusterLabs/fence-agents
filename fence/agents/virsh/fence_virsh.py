#!/usr/bin/python

# The Following Agent Has Been Tested On:
#
# Virsh 0.3.3 on RHEL 5.2 with xen-3.0.3-51
#

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="Virsh fence agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_outlets_status(conn, options):
	try:
		conn.sendline("virsh list --all")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

	result={}

        #This is status of mini finite automata. 0 = we didn't found Id and Name, 1 = we did
        fa_status=0

        for line in conn.before.splitlines():
	        domain=re.search("^\s*(\S+)\s+(\S+)\s+(\S+).*$",line)

                if (domain!=None):
			if ((fa_status==0) and (domain.group(1).lower()=="id") and (domain.group(2).lower()=="name")):
				fa_status=1
			elif (fa_status==1):
				result[domain.group(2)]=("",(domain.group(3).lower() in ["running","blocked","idle","no state","paused"] and "on" or "off"))
	return result

def get_power_status(conn, options):
	outlets=get_outlets_status(conn,options)

        if (not (options["-n"] in outlets)):
                fail_usage("Failed: You have to enter existing name of virtual machine!")
        else:
                return outlets[options["-n"]][1]

def set_power_status(conn, options):
	try:
		conn.sendline("virsh %s "%(options["-o"] == "on" and "start" or "destroy")+options["-n"])

		conn.log_expect(options, options["-c"], int(options["-g"]))
                time.sleep(1)

	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"secure", "identity_file", "test", "port", "separator",
			"inet4_only", "inet6_only", "ipport",
			"power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)

	pinput = process_input(device_opt)
	pinput["-x"] = 1
	options = check_input(device_opt, pinput)

	## Defaults for fence agent
	if 0 == options.has_key("-c"):
		options["-c"] = "\[EXPECT\]#\ "

	options["ssh_options"]="-t '/bin/bash -c \"PS1=\[EXPECT\]#\  /bin/bash --noprofile --norc\"'"

	docs = { }
	docs["shortdesc"] = "Fence agent for virsh"
	docs["longdesc"] = "fence_virsh is an I/O Fencing agent \
which can be used with the virtual machines managed by libvirt. \
It logs via ssh to a dom0 and there run virsh command, which does \
all work. \
\n.P\n\
By default, virsh needs root account to do properly work. So you \
must allow ssh login in your sshd_config."
	show_docs(options, docs)

	## Operate the fencing device
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_outlets_status)

	## Logout from system
	try:
		conn.sendline("quit")
		conn.close()
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass

	sys.exit(result)
if __name__ == "__main__":
	main()
