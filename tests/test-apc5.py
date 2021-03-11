#!/usr/bin/python

from fence_testing import test_action

def main():
	DEVICE = "devices.d/apc-v5.cfg"

	ACT_STATUS = "actions.d/status.cfg"
	ACT_ONOFF = "actions.d/power-on-off.cfg"
	ACT_LIST = "actions.d/list.cfg"

	test_action(DEVICE, ACT_STATUS, "getopt", verbose=1)
#	test_action(DEVICE, ACT_ONOFF, "stdin")
	test_action(DEVICE, ACT_LIST, "getopt")

if __name__ == "__main__":
	main()