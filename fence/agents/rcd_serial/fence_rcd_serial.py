#!/usr/bin/python -tt

# Copyright 2015 Infoxchange, Danielle Madeley, Sam McLeod-Jones

# Controls an RCD serial device
# Ported from stonith/rcd_serial.c

# The Following Agent Has Been Tested On:
# CentOS Linux release 7.1.1503

from __future__ import print_function

# Resource example:
# primitive stonith_node_1 ocf:rcd_serial_py params port="/dev/ttyS0" time=1000 hostlist=stonith_node_1 stonith-timeout=5s

import sys
import atexit
import os
import struct
from fcntl import ioctl
from termios import TIOCMBIC, TIOCMBIS, TIOCM_RTS, TIOCM_DTR
from time import sleep

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="rcd_serial (serial reset) fence agent"
REDHAT_COPYRIGHT=""
BUILD_DATE="22 Jul 2015"
#END_VERSION_GENERATION


class RCDSerial(object):
  """Control class for serial device"""

  def __init__(self, port='/dev/ttyS0'):
    self.fd = fd = os.open(port, os.O_RDONLY | os.O_NDELAY)
    print("Opened %s on fd %i" % (port, fd))
    ioctl(fd, TIOCMBIC, struct.pack('I', TIOCM_RTS | TIOCM_DTR))

  def close(self):
    """Close the serial device"""
    ret = os.close(self.fd)

    return ret

  def toggle_pin(self, pin=TIOCM_DTR, time=1000):
    """Toggle the pin high for the time specified"""

    # set pin high
    ioctl(self.fd, TIOCMBIS, struct.pack('I', pin))
    sleep(time / 1000.)
    # set the pin low
    ioctl(self.fd, TIOCMBIC, struct.pack('I', pin))

def get_power_status(conn, options):
  return "on"

def set_power_status(conn, options):
  conn.toggle_pin(time=options["--time"])
  return "off"

def main():
  device_opt = ["port", "time"]

  atexit.register(atexit_handler)

  all_opt["port"] = {
    "getopt" : ":",
    "longopt" : "port",
    "help":"--port=[port]                  Example: /dev/ttyS0",
    "required" : "1",
    "shortdesc" : "port of the serial device",
    "default" : "/dev/ttyS0",
    "order": 1
    }

  all_opt["time"] = {
    "getopt" : ":",
    "longopt" : "time",
    "help":"--time=[milliseconds] Issue the reset between 1 and [milliseconds]",
    "required" : "1",
    "shortdesc" : "Issue a sleep between 1 and X milliseconds.",
    "default" : "1000",
    "order": 1
    }

  options = check_input(device_opt, process_input(device_opt))

  docs = {}
  docs["shortdesc"] = "rcd_serial fence agent"
  docs["longdesc"] = "fence_rcd_serial"
  docs["vendorurl"] = "http://www.scl.co.uk/rcd_serial/"
  show_docs(options, docs)

  ## Operate the fencing device
  conn = RCDSerial(port=options["--port"])
  result = fence_action(conn, options, set_power_status, get_power_status, None)
  conn.close()

  sys.exit(result)

if __name__ == "__main__":
  main()

