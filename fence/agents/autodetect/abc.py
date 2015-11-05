#!/usr/bin/python

import pexpect
import re
import logging
import time
import sys
import fencing

import fence_apc
import fence_lpar
import fence_bladecenter
import fence_brocade
import fence_ilo_moonshot

def _fix_additional_newlines():
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

def get_list(conn, options, found_prompt, prompts, list_fn):
	options["--action"] = "list"
	options["--command-prompt"] = found_cmd_prompt
	if any(x in options["--command-prompt"][0] for x in prompts):
		options["--command-prompt"] = prompts
	
		if len(list_fn(conn, options)) > 0:
			return True
	return False

""" *************************** MAIN ******************************** """

## login mechanism as in fencing.py.py - differences is that we do not know command prompt
#logging.getLogger().setLevel(logging.DEBUG)

options = {}
options["--ssh-path"] = "/usr/bin/ssh"

# virtual machine
#options["--username"] = "marx"
#options["--ip"] = "localhost"
#options["--password"] = "batalion"

# APC
options["--username"] = "labuser"
options["--ip"] = "pdu-bar.englab.brq.redhat.com"
options["--password"] = "labuser"

# LPAR
options["--username"] = "rhts"
options["--ip"] = "ppc-hmc-01.mgmt.lab.eng.bos.redhat.com"
#options["--ip"] = "ibm-js22-vios-02.rhts.eng.bos.redhat.com"
options["--password"] = "100yard-"

# Bladecenter
options["--ip"] = "blade-mm.englab.brq.redhat.com"

# Brocade
#options["--ip"] = "hp-fcswitch-01.lab.bos.redhat.com"
#options["--password"] = "password"
#options["--username"] = "admin"

# iLO Moonshot
#options["--password"] = "Access@gis"
#options["--username"] = "rcuser"
#options["--ip"] = "hp-m1500-mgmt.gsslab.pnq.redhat.com"

options["--login-timeout"] = "10"
options["--shell-timeout"] = "5"
options["--power-timeout"] = "10"
options["--ipport"] = "22"

options["eol"] = "\r\n"

re_login_string=r"(login\s*: )|((?!Last )Login Name:  )|(username: )|(User Name :)"
re_login = re.compile(re_login_string, re.IGNORECASE)
re_pass = re.compile("(password)|(pass phrase)", re.IGNORECASE)

command = '%s %s@%s -p %s -1 -c blowfish -o PubkeyAuthentication=no' % (options["--ssh-path"], options["--username"], options["--ip"], options["--ipport"])
command = '%s %s@%s -p %s -o PubkeyAuthentication=no' % (options["--ssh-path"], options["--username"], options["--ip"], options["--ipport"])

conn = fencing.fspawn(options, command)
result = conn.log_expect(["ssword:", "Are you sure you want to continue connecting (yes/no)?"], int(options["--login-timeout"]))
if result == 1:
	conn.send("yes\n")
	conn.log_expect("ssword:", int(options["--login-timeout"]))

conn.send(options["--password"] + "\n")

time.sleep(2)
conn.send_eol("")
conn.send_eol("")

idx = conn.log_expect(pexpect.TIMEOUT, int(options["--login-timeout"]))
lines = re.split(r'\r|\n', conn.before)
cmd_prompt = None
logging.info("Cmd-prompt candidate: %s" % (lines[1]))
if lines.count(lines[-1]) >= 3:
	found_cmd_prompt = ["\n" + lines[-1]]
else:
	print "Unable to obtain command prompt automatically"
	sys.exit(1)

conn.log_expect(found_cmd_prompt, int(options["--shell-timeout"]))
conn.log_expect(found_cmd_prompt, int(options["--shell-timeout"]))
conn.log_expect(found_cmd_prompt, int(options["--shell-timeout"]))

## Test fence_apc with list action (old vs v5+ firmware)
cmd_possible = ["\n>", "\napc>"]
options["--action"] = "list"
options["--command-prompt"] = found_cmd_prompt
if any(options["--command-prompt"][0].startswith(x) for x in cmd_possible):
	options["--command-prompt"] = cmd_possible
	plugs = fence_apc.get_power_status5(conn, options)
	if len(plugs) > 0:
		print "fence_apc # APC - old firmware found"
		fencing.fence_logout(conn, "4")
		sys.exit(0)
	plugs = fence_apc.get_power_status(conn, options)
	if len(plugs) > 0:
		print "fence_apc # APC - v5 found"
		fencing.fence_logout(conn, "4")
		sys.exit(0)

## Test fence_lpar with list action (HMC version 3 and 4)
cmd_possible = [r":~>", r"]\$", r"\$ "]
options["--action"] = "list"
options["--command-prompt"] = found_cmd_prompt
if any(x in options["--command-prompt"][0] for x in cmd_possible):
	options["--command-prompt"] = cmd_possible
#	options["--hmc-version"] = "3"
#	plugs = fence_lpar.get_lpar_list(conn, options)
#	if len(plugs) > 0:
#		print "fence_lpar # v3"
#		fence_logout("quit")
#		sys.exit(0)
	options["eol"] = "\n"
	_fix_additional_newlines()
	conn.send_eol("lssyscfg > /dev/null | echo $?")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	if "\n0\n" in conn.before:
		print "fence_lpar # v4"
		fencing.fence_logout(conn, "quit")
		sys.exit(0)

if get_list(conn, options, found_cmd_prompt, prompts=["system>"], list_fn=fence_bladecenter.get_blades_list):
	print "fence_bladecenter #"
	sys.exit(0)

## Test fence_bladecenter
cmd_possible = ["system>"]
options["--action"] = "list"
options["--command-prompt"] = found_cmd_prompt
if any(x in options["--command-prompt"][0] for x in cmd_possible):
	options["--command-prompt"] = cmd_possible
	
	plugs = fence_bladecenter.get_blades_list(conn, options)
	if len(plugs) > 0:
		print "fence_bladeceter # "
		fencing.fence_logout(conn, "exit")
		sys.exit(0)

## Test fence_brocade
cmd_possible = ["> "]
options["--action"] = "list"
options["--command-prompt"] = found_cmd_prompt
options["eol"] = "\n"
if any(x in options["--command-prompt"][0] for x in cmd_possible):
	options["--command-prompt"] = cmd_possible

	_fix_additional_newlines()

	plugs = fence_brocade.get_power_status(conn, options)
	if len(plugs) > 0:
		print "fence_brocade # "
		fencing.fence_logout(conn, "exit")
		sys.exit(0)

# Test fence ilo moonshot
cmd_possible = ["MP>", "hpiLO->"]
options["--action"] = "list"
options["--command-prompt"] = found_cmd_prompt
options["eol"] = "\n"
if any(x in options["--command-prompt"][0] for x in cmd_possible):
	options["--command-prompt"] = cmd_possible

	fix_additional_newlines()

	plugs = fence_ilo_moonshot.get_power_status(conn, options)
	if len(plugs) > 0:
		print "fence_ilo_moonshot # "
		fencing.fence_logout(conn, "exit")
		sys.exit(0)

## Nothing found
sys.exit(2)