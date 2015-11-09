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

def check_agent(conn, options, found_prompt, prompts, test_fn, eol=None):
	options["--action"] = "list"
	options["--command-prompt"] = found_cmd_prompt
	if any(x in options["--command-prompt"][0] for x in prompts):
		if not (eol == options["eol"] or eol is None):
			options["eol"] = eol
			# At the beginning eol is CRLF what could lead to twice as many enters as expected
			# we need to parse all previous one so list_fn can work as expected

			# @note: This should be done only once per session
			# @note: after sequence crlf -> lf -> crlf = strange things can occur
			conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
			conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

		options["--command-prompt"] = prompts

		if test_fn(conn, options):
			return True
	return False

def get_list(conn, options, found_prompt, prompts, list_fn, eol=None):
	def test_fn(conn, options):
		if len(list_fn(conn, options)) > 0:
			return True
		else:
			return False
		
	return check_agent(conn, options, found_prompt, prompts, test_fn, eol)

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
#options["--ip"] = "blade-mm.englab.brq.redhat.com"

# Brocade
#options["--ip"] = "hp-fcswitch-01.lab.bos.redhat.com"
#options["--password"] = "password"
#options["--username"] = "admin"

# iLO Moonshot - chova sa to divne
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
#command = '%s %s@%s -p %s -o PubkeyAuthentication=no' % (options["--ssh-path"], options["--username"], options["--ip"], options["--ipport"])

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

if get_list(conn, options, found_cmd_prompt, prompts=["\n>", "\napc>"], list_fn=fence_apc.get_power_status):
	print "fence_apc # older series"
	fencing.fence_logout(conn, "4")
	sys.exit(0)

if get_list(conn, options, found_cmd_prompt, prompts=["\n>", "\napc>"], list_fn=fence_apc.get_power_status5):
	print "fence_apc # v5+"
	fencing.fence_logout(conn, "exit")
	sys.exit(0)

## Test fence_lpar with list action (HMC version 3 and 4)
def test_lpar(conn, options):
	# bug - eol?
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.send_eol("lssyscfg; echo $?")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	if "\n0\r\n" in conn.before:
		return True
	else:
		return False

if check_agent(conn, options, found_cmd_prompt, [r":~>", r"]\$", r"\$ "], test_lpar):
	print "fence_lpar # 2"
	fencing.fence_logout(conn, "quit")
	sys.exit(0)

if get_list(conn, options, found_cmd_prompt, prompts=["system>"], list_fn=fence_bladecenter.get_blades_list):
	print "fence_bladecenter #2"
	fencing.fence_logout(conn, "exit")
	sys.exit(0)

if get_list(conn, options, found_cmd_prompt, prompts=["> "], list_fn=fence_brocade.get_power_status, eol="\n"):
	print "fence_brocade #2"
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