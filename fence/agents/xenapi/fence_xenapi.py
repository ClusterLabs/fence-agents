#!/usr/bin/python -tt
#
#############################################################################
# Copyright 2011 Matthew Clark
# This file is part of fence-xenserver
#
# fence-xenserver is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# fence-xenserver is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Please let me know if you are using this script so that I can work out
# whether I should continue support for it. mattjclark0407 at hotmail dot com
#############################################################################

#############################################################################
# It's only just begun...
# Current status: completely usable. This script is now working well and,
# has a lot of functionality as a result of the fencing.py library and the
# XenAPI libary.

#############################################################################
# Please let me know if you are using this script so that I can work out
# whether I should continue support for it. mattjclark0407 at hotmail dot com

import sys
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import run_delay
import XenAPI

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

EC_BAD_SESSION = 1
# Find the status of the port given in the -U flag of options.
def get_power_fn(session, options):
	if options.has_key("--verbose"):
		verbose = True
	else:
		verbose = False

	try:
		# Get a reference to the vm specified in the UUID or vm_name/port parameter
		vm = return_vm_reference(session, options)
		# Query the VM for its' associated parameters
		record = session.xenapi.VM.get_record(vm)
		# Check that we are not trying to manipulate a template or a control
		# domain as they show up as VM's with specific properties.
		if not record["is_a_template"] and not record["is_control_domain"]:
			status = record["power_state"]
			if verbose:
				print "UUID:", record["uuid"], "NAME:", record["name_label"], "POWER STATUS:", record["power_state"]
			# Note that the VM can be in the following states (from the XenAPI document)
			# Halted: VM is offline and not using any resources.
			# Paused: All resources have been allocated but the VM itself is paused and its vCPUs are not running
			# Running: Running
			# Paused: VM state has been saved to disk and it is nolonger running. Note that disks remain in-Use while
			# We want to make sure that we only return the status "off" if the machine is actually halted as the status
			# is checked before a fencing action. Only when the machine is Halted is it not consuming resources which
			# may include whatever you are trying to protect with this fencing action.
			return status == "Halted" and "off" or "on"
	except Exception, exn:
		print str(exn)

	return "Error"

# Set the state of the port given in the -U flag of options.
def set_power_fn(session, options):
	try:
		# Get a reference to the vm specified in the UUID or vm_name/port parameter
		vm = return_vm_reference(session, options)
		# Query the VM for its' associated parameters
		record = session.xenapi.VM.get_record(vm)
		# Check that we are not trying to manipulate a template or a control
		# domain as they show up as VM's with specific properties.
		if not record["is_a_template"] and not record["is_control_domain"]:
			if options["--action"] == "on":
				# Start the VM
				session.xenapi.VM.start(vm, False, True)
			elif options["--action"] == "off":
				# Force shutdown the VM
				session.xenapi.VM.hard_shutdown(vm)
			elif options["--action"] == "reboot":
				# Force reboot the VM
				session.xenapi.VM.hard_reboot(vm)
	except Exception, exn:
		print str(exn)

# Function to populate an array of virtual machines and their status
def get_outlet_list(session, options):
	result = {}
	if options.has_key("--verbose"):
		verbose = True
	else:
		verbose = False

	try:
		# Return an array of all the VM's on the host
		vms = session.xenapi.VM.get_all()
		for vm in vms:
			# Query the VM for its' associated parameters
			record = session.xenapi.VM.get_record(vm)
			# Check that we are not trying to manipulate a template or a control
			# domain as they show up as VM's with specific properties.
			if not record["is_a_template"] and not record["is_control_domain"]:
				name = record["name_label"]
				uuid = record["uuid"]
				status = record["power_state"]
				result[uuid] = (name, status)
				if verbose:
					print "UUID:", record["uuid"], "NAME:", name, "POWER STATUS:", record["power_state"]
	except Exception, exn:
		print str(exn)

	return result

# Function to initiate the XenServer session via the XenAPI library.
def connect_and_login(options):
	url = options["--session-url"]
	username = options["--username"]
	password = options["--password"]

	try:
		# Create the XML RPC session to the specified URL.
		session = XenAPI.Session(url)
		# Login using the supplied credentials.
		session.xenapi.login_with_password(username, password)
	except Exception, exn:
		print str(exn)
		# http://sources.redhat.com/cluster/wiki/FenceAgentAPI says that for no connectivity
		# the exit value should be 1. It doesn't say anything about failed logins, so
		# until I hear otherwise it is best to keep this exit the same to make sure that
		# anything calling this script (that uses the same information in the web page
		# above) knows that this is an error condition, not a msg signifying a down port.
		sys.exit(EC_BAD_SESSION)
	return session

# return a reference to the VM by either using the UUID or the vm_name/port. If the UUID is set then
# this is tried first as this is the only properly unique identifier.
# Exceptions are not handled in this function, code that calls this must be ready to handle them.
def return_vm_reference(session, options):
	if options.has_key("--verbose"):
		verbose = True
	else:
		verbose = False

	# Case where the UUID has been specified
	if options.has_key("--uuid"):
		uuid = options["--uuid"].lower()
		# When using the -n parameter for name, we get an error message (in verbose
		# mode) that tells us that we didn't find a VM. To immitate that here we
		# need to catch and re-raise the exception produced by get_by_uuid.
		try:
			return session.xenapi.VM.get_by_uuid(uuid)
		except Exception:
			if verbose:
				print "No VM's found with a UUID of \"%s\"" % uuid
			raise

	# Case where the vm_name/port has been specified
	if options.has_key("--plug"):
		vm_name = options["--plug"]
		vm_arr = session.xenapi.VM.get_by_name_label(vm_name)
		# Need to make sure that we only have one result as the vm_name may
		# not be unique. Average case, so do it first.
		if len(vm_arr) == 1:
			return vm_arr[0]
		else:
			if len(vm_arr) == 0:
				if verbose:
					print "No VM's found with a name of \"%s\"" % vm_name
				# NAME_INVALID used as the XenAPI throws a UUID_INVALID if it can't find
				# a VM with the specified UUID. This should make the output look fairly
				# consistent.
				raise Exception("NAME_INVALID")
			else:
				if verbose:
					print "Multiple VM's have the name \"%s\", use UUID instead" % vm_name
				raise Exception("MULTIPLE_VMS_FOUND")

	# We should never get to this case as the input processing checks that either the UUID or
	# the name parameter is set. Regardless of whether or not a VM is found the above if
	# statements will return to the calling function (either by exception or by a reference
	# to the VM).
	raise Exception("VM_LOGIC_ERROR")

def main():

	device_opt = ["login", "passwd", "port", "no_login", "no_password", "session_url", "web"]

	atexit.register(atexit_handler)

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Citrix XenServer over XenAPI"
	docs["longdesc"] = "\
fence_cxs is an I/O Fencing agent used on Citrix XenServer hosts. \
It uses the XenAPI, supplied by Citrix, to establish an XML-RPC sesssion \
to a XenServer host. Once the session is established, further XML-RPC \
commands are issued in order to switch on, switch off, restart and query \
the status of virtual machines running on the host."
	docs["vendorurl"] = "http://www.xenproject.org"
	show_docs(options, docs)

	run_delay(options)

	xen_session = connect_and_login(options)
	result = fence_action(xen_session, options, set_power_fn, get_power_fn, get_outlet_list)

	sys.exit(result)

if __name__ == "__main__":
	main()
