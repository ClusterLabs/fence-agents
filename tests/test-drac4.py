#!/usr/bin/python

from fence_testing import test_action

def main():
	DRAC4 = "devices.d/dell-drac-4I.cfg"

	ACT_STATUS = "actions.d/status.cfg"
	ACT_ONOFF = "actions.d/power-on-off.cfg"

	test_action(DRAC4, ACT_STATUS, "getopt")
	test_action(DRAC4, ACT_ONOFF, "stdin")

if __name__ == "__main__":
	main()