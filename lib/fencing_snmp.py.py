#!@PYTHON@ -tt

# For example of use please see fence_cisco_mds

import re, pexpect
import logging
from fencing import *
from fencing import fail, fail_usage, EC_TIMED_OUT, run_delay, frun

__all__ = ['FencingSnmp']

## do not add code here.
class FencingSnmp:
	def __init__(self, options):
		self.options = options
		run_delay(options)

	def quote_for_run(self, string):
		return string.replace(r"'", "'\\''")

	def complete_missed_params(self):
		mapping = [[
					['snmp-priv-passwd', 'password', '!snmp-sec-level'],
					'self.options["--snmp-sec-level"]="authPriv"'
				], [
					['!snmp-version', 'community', '!username', '!snmp-priv-passwd', '!password'],
					'self.options["--snmp-version"]="2c"'
				]]

		for val in mapping:
			e = val[0]

			res = True

			for item in e:
				if item[0] == '!' and "--" + item[1:] in self.options:
					res = False
					break

				if item[0] != '!' and "--" + item[0:] not in self.options:
					res = False
					break

			if res:
				exec(val[1])

	def prepare_cmd(self, command):
		cmd = "%s -m '' -Oeqn "% (command)

		self.complete_missed_params()

		#mapping from our option to snmpcmd option
		mapping = (('snmp-version', 'v'), ('community', 'c'))

		for item in mapping:
			if "--" + item[0] in self.options:
				cmd += " -%s '%s'"% (item[1], self.quote_for_run(self.options["--" + item[0]]))

		# Some options make sense only for v3 (and for v1/2c can cause "problems")
		if ("--snmp-version" in self.options) and (self.options["--snmp-version"] == "3"):
			# Mapping from our options to snmpcmd options for v3
			mapping_v3 = (('snmp-auth-prot', 'a'), ('snmp-sec-level', 'l'), ('snmp-priv-prot', 'x'), \
				('snmp-priv-passwd', 'X'), ('password', 'A'), ('username', 'u'))
			for item in mapping_v3:
				if "--"+item[0] in self.options:
					cmd += " -%s '%s'"% (item[1], self.quote_for_run(self.options["--" + item[0]]))

		force_ipvx = ""

		if "--inet6-only" in self.options:
			force_ipvx = "udp6:"

		if "--inet4-only" in self.options:
			force_ipvx = "udp:"

		cmd += " '%s%s%s'"% (force_ipvx, self.quote_for_run(self.options["--ip"]),
				"--ipport" in self.options and self.quote_for_run(":" + str(self.options["--ipport"])) or "")
		return cmd

	def run_command(self, command, additional_timeout=0):
		try:
			logging.debug("%s\n", command)

			(res_output, res_code) = frun(command,
					int(self.options["--shell-timeout"]) +
					int(self.options["--login-timeout"]) +
					additional_timeout, True)

			if res_code == None:
				fail(EC_TIMED_OUT)

			logging.debug("%s\n", res_output)

			if (res_code != 0) or (re.search("^Error ", res_output, re.MULTILINE) != None):
				fail_usage("Returned %d: %s"% (res_code, res_output))
		except pexpect.ExceptionPexpect:
			fail_usage("Cannot run command %s"%(command))

		return res_output

	def get(self, oid, additional_timeout=0):
		cmd = "%s '%s'"% (self.prepare_cmd(self.options["--snmpget-path"]), self.quote_for_run(oid))

		output = self.run_command(cmd, additional_timeout).splitlines()

		return output[len(output)-1].split(None, 1)

	def set(self, oid, value, additional_timeout=0):
		mapping = ((int, 'i'), (str, 's'))

		type_of_value = ''

		for item in mapping:
			if isinstance(value, item[0]):
				type_of_value = item[1]
				break

		cmd = "%s '%s' %s '%s'" % (self.prepare_cmd(self.options["--snmpset-path"]),
				self.quote_for_run(oid), type_of_value, self.quote_for_run(str(value)))

		self.run_command(cmd, additional_timeout)

	def walk(self, oid, additional_timeout=0):
		cmd = "%s '%s'"% (self.prepare_cmd(self.options["--snmpwalk-path"]), self.quote_for_run(oid))

		output = self.run_command(cmd, additional_timeout).splitlines()

		return [x.split(None, 1) for x in output if x.startswith(".")]
