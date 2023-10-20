#!@PYTHON@ -tt

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see
# <http://www.gnu.org/licenses/>.

# The Following agent has been tested on:
#   Lindy PDU model 32657
#   Firmware release s4.82-091012-1cb08s
#   Probably works on different models with same MIB .. but is better test on them
#
#  (C) 2021 Daimonlab -- Damiano Scaramuzza (cesello) cesello@daimonlab.it

import sys
import atexit
import logging
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage
from fencing_snmp import FencingSnmp

### CONSTANTS ###
# oid defining fence device
OID_SYS_OBJECT_ID = '.1.3.6.1.2.1.1.2.0'

### GLOBAL VARIABLES ###
# Device - see Lindy PDU
device = None

# Port ID
port_id = None
# Switch ID
switch_id = None

# Classes describing Device params
# Here I follow the MIBS specs that use "switch" and "plug" concepts but
# the pdu really have one switch only and 8-16 plugs.
# Probably the "switch" term is used for future uses or more advanced pdus
class LindyPDU(object):
	# PDU
	status_oid =       '.1.3.6.1.4.1.17420.1.2.9.%d.13.0'
	control_oid =      '.1.3.6.1.4.1.17420.1.2.9.%d.13.0'
	outlet_table_oid = '.1.3.6.1.4.1.17420.1.2.9.%d.14'
	pdu_table_oid = '.1.3.6.1.4.1.17420.1.2.9'
	attached_pdus = '.1.3.6.1.4.1.17420.1.2.5.0'
	ident_str = "Lindy  32657 PDU"
	state_on = 1
	state_off = 0
	turn_on = 1
	turn_off = 0
	has_switches = True

### FUNCTIONS ###
def lpdu_set_device(conn, options):
	global device

	agents_dir = {'.1.3.6.1.4.1.17420':LindyPDU}

	# First resolve type of PDU device
	pdu_type = conn.walk(OID_SYS_OBJECT_ID)

	if not ((len(pdu_type) == 1) and (pdu_type[0][1] in agents_dir)):
		pdu_type = [[None, None]]

	device = agents_dir[pdu_type[0][1]]

	logging.debug("Trying %s"%(device.ident_str))

def lpdu_resolv_port_id(conn, options):
	
	if device == None:
		lpdu_set_device(conn, options)

	port_id=switch_id=None
	# Now we resolv port_id/switch_id
	if options["--plug"].isdigit() and ((not device.has_switches) or (options["--switch"].isdigit())):
		port_id = int(options["--plug"])

		if device.has_switches:
			switch_id = int(options["--switch"])
	else:
		table = conn.walk(device.pdu_table_oid, 30)

		for x in table:
			if x[1].strip('"').split(',')[0] == options["--plug"]:
				t = x[0].split('.')
				if device.has_switches:
					port_id = int(t[len(t)-1])
					switch_id = int(t[len(t)-3])
				else:
					port_id = int(t[len(t)-1])

	if port_id == None:
		fail_usage("Can't find port with name %s!"%(options["--plug"]))

	return (switch_id,port_id)

def get_power_status(conn, options):

	(switch_id,port_id)=lpdu_resolv_port_id(conn, options)

	oid = ((device.has_switches) and device.status_oid%(switch_id) or device.status_oid%(port_id))

	
	try:
		(oid, status) = conn.get(oid)
		# status is a comma separated string 
		# one line only as "1,1,1,0,1,1,1,1".
		state=status.strip('"').split(',')[port_id-1]
		if state == str(device.state_on):
			return "on"
		elif state == str(device.state_off):
			return "off"
		else:
			return None
	except Exception:
		return None

def set_power_status(conn, options):

	(switch_id,port_id)=lpdu_resolv_port_id(conn, options)

	oid = ((device.has_switches) and device.control_oid%(switch_id) or device.control_oid%(port_id))

	(oid, status) = conn.get(oid)
	# status is a comma separated string 
	state=status.strip('"').split(',')
	state[port_id-1]=str((options["--action"] == "on" and device.turn_on or device.turn_off))
	conn.set(oid, ",".join(state))


def get_outlets_status(conn, options):
	result = {}
	pdu_id=[]

	if device == None:
		lpdu_set_device(conn, options)
	
	if (device.has_switches and options["--switch"].isdigit()):
		pdu_id.append(options["--switch"])
		
	elif (device.has_switches):
		#search for all pdu
		pdus=conn.walk(device.attached_pdus, 30)
		pdus_info=pdus[0][1].strip('"').split(',')
		pdu_id=pdus_info[1:]
	else:
		#I really don't know what to do with this case. I haven't a different lindy pdu to test
		table_oid=device.pdu_table_oid
	
	
	for switch in pdu_id:
		table_oid = device.outlet_table_oid % int(switch)
		res_ports = conn.walk(table_oid, 30)
		status_oid=device.status_oid % int(switch)
		port_status=conn.walk(status_oid, 30)
		state=port_status[0][1].strip('"').split(',')
		for x in res_ports:
			t = x[0].split('.')
			port_num = ((device.has_switches) and "%s:%s"%(t[len(t)-4], t[len(t)-2]) or "%s"%(t[len(t)-2]))
			port_name = x[1].strip('"').split(',')[0]
			result[port_num] = (port_name, "on" if state[int(t[len(t)-2])-1]=='1' else "off")

	return result

# Main agent method
def main():
	global device

	device_opt = ["ipaddr", "login", "passwd", "no_login", "no_password", \
		       "port", "snmp_version", "snmp","switch"]

	atexit.register(atexit_handler)

	all_opt["snmp_version"]["default"] = "1"
	all_opt["community"]["default"] = "public"
	all_opt["switch"]["default"] = "1"
	device = LindyPDU

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Lindy over SNMP"
	docs["longdesc"] = "fence_lindypdu is a Power Fencing agent \
which can be used with the Lindy PDU network power switch. It logs \
into a device via SNMP and reboots a specified outlet. It supports \
SNMP v1 with all combinations of authenticity/privacy settings."
	docs["vendorurl"] = "http://www.lindy.co.uk"
	show_docs(options, docs)

	# Operate the fencing device
	result = fence_action(FencingSnmp(options), options, set_power_status, get_power_status, get_outlets_status)

	sys.exit(result)
if __name__ == "__main__":
	main()
