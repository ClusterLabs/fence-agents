#!/usr/bin/python

# For example of use please see fence_cisco_mds

import re, pexpect
from fencing import *

## do not add code here.
#BEGIN_VERSION_GENERATION
RELEASE_VERSION = ""
REDHAT_COPYRIGHT = ""
BUILD_DATE = ""
#END_VERSION_GENERATION

# Fix for RHBZ#527844
def snmp_define_defaults ():
	all_opt["udpport"]["default"] = "161"
	all_opt["ipport"]["default"] = "161"

class FencingSnmp:
	def __init__(self, options):
		self.options = options

	# Log message if user set verbose option
	def log_command(self, message):
		if self.options["log"] >= LOG_MODE_VERBOSE:
			self.options["debug_fh"].write(message+"\n")

	def quote_for_run(self, string):
		return ''.join(map(lambda x:x==r"'" and "'\\''" or x, string))

	def complete_missed_params(self):
		mapping = [
			[['snmp-priv-passwd','password','!snmp-sec-level'],'self.options["--snmp-sec-level"]="authPriv"'],
			[['!snmp-version','community','!username','!snmp-priv-passwd','!password'],'self.options["--snmp-version"]="2c"']
			]

		for val in mapping:
			e = val[0]

			res = True

			for item in e:
				if ((item[0]=='!') and (self.options.has_key("--"+item[1:]))):
					res = False
					break

				if ((item[0]!='!') and (not self.options.has_key("--"+item[0:]))):
					res = False
					break

			if res:
				exec(val[1])

	def prepare_cmd(self, command):
		cmd = "@SNMPBIN@/%s -m '' -Oeqn "% (command)

		self.complete_missed_params()

		#mapping from our option to snmpcmd option
		mapping = (('snmp-version', 'v'),('community', 'c'))

		for item in mapping:
			if (self.options.has_key("--" + item[0])):
				cmd += " -%s '%s'"% (item[1], self.quote_for_run(self.options["--" + item[0]]))

		# Some options make sense only for v3 (and for v1/2c can cause "problems")
		if (self.options.has_key("--snmp-version")) and (self.options["--snmp-version"] == "3"):
			# Mapping from our options to snmpcmd options for v3
			mapping_v3 = (('snmp-auth-prot','a'), ('snmp-sec-level','l'), ('snmp-priv-prot','x'), \
				('snmp-priv-passwd','X'),('password','A'),('username','u'))
			for item in mapping_v3:
				if (self.options.has_key("--"+item[0])):
					cmd += " -%s '%s'"% (item[1], self.quote_for_run(self.options["--" + item[0]]))

		force_ipvx = ""

		if (self.options.has_key("--inet6-only")):
			force_ipvx = "udp6:"

		if (self.options.has_key("--inet4-only")):
			force_ipvx = "udp:"

		cmd += " '%s%s%s'"% (force_ipvx, self.quote_for_run(self.options["--ip"]),
				self.options.has_key("--udpport") and self.quote_for_run(":" + str (self.options["--udpport"])) or "")
		return cmd

	def run_command(self, command, additional_timemout=0):
		try:
			self.log_command(command)

			(res_output, res_code) = pexpect.run(command, int(self.options["--shell-timeout"]) + int(self.options["--login-timeout"]) + additional_timemout, True)

			if (res_code==None):
				fail(EC_TIMED_OUT)

			self.log_command(res_output)

			if (res_code!=0) or (re.search("^Error ", res_output, re.MULTILINE) != None):
				fail_usage("Returned %d: %s"% (res_code, res_output))
		except pexpect.ExceptionPexpect:
			fail_usage("Cannot run command %s"%(command))

		return res_output

	def get(self, oid, additional_timemout=0):
		cmd = "%s '%s'"% (self.prepare_cmd("snmpget"), self.quote_for_run(oid))

		output = self.run_command(cmd, additional_timemout).splitlines()

		return output[len(output)-1].split(None, 1)

	def set(self, oid, value, additional_timemout=0):
		mapping = ((int, 'i'), (str, 's'))

		type_of_value = ''

		for item in mapping:
			if (isinstance(value, item[0])):
				type_of_value = item[1]
				break

		cmd = "%s '%s' %s '%s'"% (self.prepare_cmd("snmpset"), self.quote_for_run(oid), type_of_value, self.quote_for_run(str(value)))

		self.run_command(cmd, additional_timemout)

	def walk(self, oid, additional_timemout=0):
		cmd = "%s '%s'"% (self.prepare_cmd("snmpwalk"), self.quote_for_run(oid))

		output = self.run_command(cmd, additional_timemout).splitlines()

		return map(lambda x:x.split(None, 1), filter(lambda y:len(y)>0 and y[0]=='.', output))
