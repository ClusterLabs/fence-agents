#!/usr/bin/python

from fence_testing import test_action

def main():
	## @todo: utility1 - run single 'agent' 'action' 'method'
	## @todo: utility2 - run complex tests (using utility1?) -> file with test suites
	
	AGENTDEF = "devices.d/true.cfg"
	DUMMYDEF = "devices.d/dummy.cfg"

	ACT_STATUS = "actions.d/status.cfg"
	ACT_ONOFF = "actions.d/power-on-off.cfg"

#	test_action(AGENTDEF, ACTIONDEF, "stdin")
#	test_action(AGENTDEF, ACTIONDEF, "getopt")
	test_action(DUMMYDEF, ACT_STATUS, "getopt")
	test_action(DUMMYDEF, ACT_ONOFF, "getopt")

if __name__ == "__main__":
	main()