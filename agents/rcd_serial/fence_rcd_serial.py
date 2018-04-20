#!@PYTHON@ -tt

# Copyright 2015 Infoxchange, Danielle Madeley, Sam McLeod-Jones

# Controls an RCD serial device
# Ported from stonith/rcd_serial.c

# The Following Agent Has Been Tested On:
# CentOS Linux release 7.1.1503

# Resource example:
# primitive stonith_node_1 ocf:rcd_serial_py params port="/dev/ttyS0" time=1000 hostlist=stonith_node_1 stonith-timeout=5s

import sys
import atexit
import os
import struct
import logging
import time
from fcntl import ioctl
from termios import TIOCMBIC, TIOCMBIS, TIOCM_RTS, TIOCM_DTR
from time import sleep

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

class RCDSerial(object):
	"""Control class for serial device"""

	def __init__(self, port='/dev/ttyS0'):
		self.fd = fd = os.open(port, os.O_RDONLY | os.O_NDELAY)
		logging.debug("Opened %s on fd %i", port, fd)
		ioctl(fd, TIOCMBIC, struct.pack('I', TIOCM_RTS | TIOCM_DTR))

	def close(self):
		"""Close the serial device"""
		logging.debug("Closing serial device")
		ret = os.close(self.fd)

		return ret

	def toggle_pin(self, pin=TIOCM_DTR, time=1000):
		"""Toggle the pin high for the time specified"""

		logging.debug("Set pin high")
		ioctl(self.fd, TIOCMBIS, struct.pack('I', pin))

		sleep(float(time) / 1000.)

		logging.debug("Set pin low")
		ioctl(self.fd, TIOCMBIC, struct.pack('I', pin))

def reboot_device(conn, options):
	conn.toggle_pin(time=options["--power-wait"])
	return True

def main():
	device_opt = ["serial_port", "no_status", "no_password", "no_login", "method", "no_on", "no_off"]

	atexit.register(atexit_handler)

	all_opt["serial_port"] = {
		"getopt" : ":",
		"longopt" : "serial-port",
		"help":"--serial-port=[port]           Port of the serial device (e.g. /dev/ttyS0)",
		"required" : "1",
		"shortdesc" : "Port of the serial device",
		"default" : "/dev/ttyS0",
		"order": 1
	}

	all_opt["method"]["default"] = "cycle"
	all_opt["power_wait"]["default"] = "2"
	all_opt["method"]["help"] = "-m, --method=[method]          Method to fence (onoff|cycle) (Default: cycle)"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "rcd_serial fence agent"
	docs["longdesc"] = "fence_rcd_serial operates a serial cable that toggles a \
reset of an opposing server using the reset switch on its motherboard. The \
cable itself is simple with no power, network or moving parts. An example of \
the cable is available here: https://smcleod.net/rcd-stonith/ and the circuit \
design is available in the fence-agents src as SVG"
	docs["vendorurl"] = "http://www.scl.co.uk/rcd_serial/"
	show_docs(options, docs)

	if options["--action"] in ["off", "reboot"]:
		time.sleep(int(options["--delay"]))

	## Operate the fencing device
	conn = RCDSerial(port=options["--serial-port"])
	result = fence_action(conn, options, None, None, reboot_cycle_fn=reboot_device)
	conn.close()

	sys.exit(result)

if __name__ == "__main__":
	main()

