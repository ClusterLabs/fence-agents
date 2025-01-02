#!@PYTHON@ -tt

import logging
import sys
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import EC_STATUS

"""
Raritan PX3 family is totaly different the PX family (PX2 seem to be
compatible with PX3 and seem to share the same BIOS, so this fence should
work with PX2 as well).
It has another command line prompt and totally other commands
and output.

It follows the concept of separating outlets and outletgroups (if created).
You can reach outlets via a fixed, not changeble "plug" number
(from 1-20 on my device).
Additionally one can, but does not need to assign names to each plug.

Plugs/outlets can be combined to outletgroups.
There can be zero to N (N = No. outlets) outletgroups.

While it's possible to create outletgroups with one plug, this does not
make sense and might slow things down.

--plug=X paramter can be:
1. X == outlet No
2. X == outlet Name (if one got assigned)
3. X == outlet group Name

-> One cannot reach a group by number
-> Groups need an extra call (first single outlet devices are
   searched for given No/Name, then OutletGroups
"""


class FenceRaritanPX3:
	outlets={}
	# Plug id of outlet
	plug=None
	outletgroups={}
	# Group name if outlet plug id/name have not been found
	group_name=None

def px3_get_outlet_group(conn, options):

	conn.send_eol("show outletgroups")
	conn.expect(options["--command-prompt"], int(options["--shell-timeout"]))
	for line in conn.after.splitlines():
		split_line = line.split(" ")
		"""
		Groups always have a name assigned:
		```
		Outlet Group 1 - test:
		Member outlets: 10-11
		State:          2 on
		```
		"""
		if len(split_line) == 5 and split_line[0] == "Outlet" and split_line[1] == "Group":
			group_no = split_line[2]
			group_name = split_line[4][:-1]

		if len(split_line) > 0 and split_line[0] == "State:":
			group_state = split_line[-1]
			FenceRaritanPX3.outletgroups[group_no] = [ group_name, group_state ]
	logging.debug("Outletgroups found:\n%s", FenceRaritanPX3.outletgroups)
	return FenceRaritanPX3.outletgroups

def px3_get_outlet_list(conn, options):

	conn.send_eol("show outlets")
	conn.expect(options["--command-prompt"], int(options["--shell-timeout"]))
	for line in conn.after.splitlines():
		split_line = line.split(" ")
		"""
		Plug with no name assigned:
		```
		Outlet 1:
		Power state: On
		```
		"""
		if len(split_line) == 2 and split_line[0] == "Outlet":
			outlet_no = split_line[1][:-1]
			outlet_name = ""
		"""
		Plug with name assigned:
		```
		Outlet 8 - Test:
		Power state: On
		```
		"""
		if len(split_line) == 4 and split_line[0] == "Outlet":
			outlet_no = split_line[1]
			outlet_name = split_line[3][:-1]

		# fetch state of previously parsed outlet from next line/iter
		if len(split_line) == 3 and split_line[0] == "Power" and split_line[1] == "state:":
			outlet_state = split_line[2]
			FenceRaritanPX3.outlets[outlet_no] = [outlet_name, outlet_state]
	logging.debug("Outlets found:\n%s", FenceRaritanPX3.outlets)
	return FenceRaritanPX3.outlets

def get_power_status(conn, options):

	if FenceRaritanPX3.plug:
		return FenceRaritanPX3.outlets[str(FenceRaritanPX3.plug)][1].lower()
	elif FenceRaritanPX3.group_name:
		return FenceRaritanPX3.outletgroups[FenceRaritanPX3.group_name][1].lower()
	sys.exit(EC_STATUS)

def set_power_status(conn, options):
	action = {
		"on" : "on",
		"off" : "off",
		"reboot" : "cycle",
	}[options["--action"]]

	if FenceRaritanPX3.plug:
		conn.send_eol("power outlets %s %s" % (FenceRaritanPX3.plug, action))
		# Do you wish to turn outlet 5 off? [y/n]
	elif FenceRaritanPX3.group_name:
		conn.send_eol("power outletgroup %s %s" % (FenceRaritanPX3.group_name, action))
		# Do you wish to turn on all 2 outlets in group 1? [y/n]
	conn.log_expect("Do you wish to turn.*", int(options["--shell-timeout"]))
	conn.send_eol("y")
	print("YYYYY")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	print("XXXXXXXX")

def disconnect(conn):
    conn.sendline("EXIT")
    conn.close()

def main():
	device_opt = ["ipaddr", "login", "passwd", "port", "telnet", "cmd_prompt", "secure"]

	atexit.register(atexit_handler)

	opt = process_input(device_opt)
	all_opt["cmd_prompt"]["default"] = r".*\[My PDU\] #"
	all_opt["ipport"]["default"] = "23"
	all_opt["shell_timeout"]["default"] = "8"

	opt["eol"] = "\r\n"
	options = check_input(device_opt, opt)

	docs = {}
	docs["shortdesc"] = "Power Fencing agent for Raritan Dominion PX2 and PX3"
	docs["longdesc"] = "fence_raritan_px3 is a Power Fencing agent which can be \
used with the Raritan PX2 and PX3 Power Distribution Unit series. It logs into \
device via telnet or ssh and reboots a specified outlet. Single outlets and \
grouped outlets are supported. The fence is tested on this model: PX3-5466V. \
There have been issues seen with the telnet prompt on 3.4.x and 3.5.x Raritan \
firmware versions. It's recommended to update to at least version 3.6.x"
	docs["vendorurl"] = "http://www.raritan.com/"
	show_docs(options, docs)

	conn = fence_login(options, re_login_string=r"Username.*")

	px3_get_outlet_list(conn, options)
	try:
		FenceRaritanPX3.plug = int(options["--plug"])
		if FenceRaritanPX3.plug > len(FenceRaritanPX3.outlets):
			logging.error("Plug no exceeds no of outlets")
			sys.exit(EC_STATUS)
	except ValueError:
		for no, values in FenceRaritanPX3.outlets.items():
			if values[0] == options["--plug"]:
				FenceRaritanPX3.plug = no
				break
	if not FenceRaritanPX3.plug:
		px3_get_outlet_group(conn, options)
		for no, values in FenceRaritanPX3.outletgroups.items():
			if values[0] == options["--plug"]:
				FenceRaritanPX3.group_name = no
				break
		if not FenceRaritanPX3.group_name:
			logging.error("Plug %s not found", options["--plug"])
			sys.exit(EC_STATUS)

	logging.debug("\nSingle outlet: %s\nGroup outlet: %s" % (FenceRaritanPX3.plug, FenceRaritanPX3.group_name))

	result = 0
	if options["--action"] != "monitor":
		result = fence_action(conn, options, set_power_status, get_power_status,
				      get_outlet_list=px3_get_outlet_list, reboot_cycle_fn=set_power_status)

	atexit.register(disconnect, conn)

	sys.exit(result)

if __name__ == "__main__":
	main()
