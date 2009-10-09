#!/usr/bin/python

# For example of use please see fence_cisco_mds

import re,pexpect
from fencing import *

## do not add code here.
#BEGIN_VERSION_GENERATION
RELEASE_VERSION = ""
REDHAT_COPYRIGHT = ""
BUILD_DATE = ""
#END_VERSION_GENERATION

# Fix for RHBZ#527844
def snmp_define_defaults ():
	all_opt["udpport"]["default"]="161"
	all_opt["ipport"]["default"]="161"

class FencingSnmp:
	def __init__(self,options):
		self.options=options

	# Log message if user set verbose option
	def log_command(self, message):
		if self.options["log"] >= LOG_MODE_VERBOSE:
			self.options["debug_fh"].write(message+"\n")

	def quote_for_run(self,str):
		return ''.join(map(lambda x:x==r"'" and "'\\''" or x,str))

	def complete_missed_params(self):
		mapping=[
			[['P','p','!E'],'self.options["-E"]="authPriv"'],
			[['!d','c','!l','!P','!p'],'self.options["-d"]="2c"']
			]

		for val in mapping:
			e=val[0]

			res=True

			for item in e:
				if ((item[0]=='!') and (self.options.has_key("-"+item[1]))):
					res=False
					break

				if ((item[0]!='!') and (not self.options.has_key("-"+item[0]))):
					res=False
					break

			if res:
				exec(val[1])

	def prepare_cmd(self,command):
		cmd="@SNMPBIN@/%s -m '' -Oeqn "%(command)

		self.complete_missed_params()

		#mapping from our option to snmpcmd option
		mapping=(('d','v'), ('c','c'),('b','a'),('E','l'),('B','x'),('P','X'),('p','A'),('l','u'))

		for item in mapping:
			if (self.options.has_key("-"+item[0])):
				cmd+=" -%s '%s'"%(item[1],self.quote_for_run(self.options["-"+item[0]]))

		force_ipvx=""

		if (self.options.has_key("-6")):
			force_ipvx="udp6:"

		if (self.options.has_key("-4")):
			force_ipvx="udp:"

		cmd+=" '%s%s%s'"%(force_ipvx, self.quote_for_run(self.options["-a"]),
				self.options.has_key("-u") and self.quote_for_run(":" + str (self.options["-u"])) or "")
		return cmd

	def run_command(self,command,additional_timemout=0):
		try:
			self.log_command(command)

			(res_output,res_code)=pexpect.run(command,int(options["-Y"])+int(options["-y"])+additional_timemout,True)

			if (res_code==None):
				fail(EC_TIMED_OUT)

			self.log_command(res_output)
			if (res_code!=0):
				fail_usage("Returned %d: %s"%(res_code,res_output))
		except pexpect.ExceptionPexpect:
			fail_usage("Cannot run command %s"%(command))

		return res_output

	def get(self,oid,additional_timemout=0):
		cmd="%s '%s'"%(self.prepare_cmd("snmpget"),self.quote_for_run(oid))

		output=self.run_command(cmd,additional_timemout).splitlines()

		return output[len(output)-1].split(None,1)

	def set(self,oid,value,additional_timemout=0):
		mapping=((int,'i'),(str,'s'))

		type=''

		for item in mapping:
			if (isinstance(value,item[0])):
				type=item[1]
				break

		cmd="%s '%s' %s '%s'"%(self.prepare_cmd("snmpset"),self.quote_for_run(oid),type,self.quote_for_run(str(value)))

		self.run_command(cmd,additional_timemout)

	def walk(self,oid,additional_timemout=0):
		cmd="%s '%s'"%(self.prepare_cmd("snmpwalk"),self.quote_for_run(oid))

		output=self.run_command(cmd,additional_timemout).splitlines()

		return map(lambda x:x.split(None,1),filter(lambda y:len(y)>0 and y[0]=='.',output))
