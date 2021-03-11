#!@PYTHON@ -tt

# Copyright (c) 2020 Red Hat
#
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

import atexit
import logging
import sys
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import (all_opt, atexit_handler, check_input,  # noqa: E402
                     fence_action, process_input, run_command, run_delay,
                     show_docs)

logger = logging.getLogger(__name__)
logger.setLevel("WARNING")


def get_power_status(conn, options):
    logger.debug("get_power_status(): %s" % options)
    ip = options['--crosscableip']
    timeout = options['--timeout']
    # This returns 'off' if not a single ICMP packet gets answered during the
    # whole timeout window. (the ping executable will return 1 in such case and
    # 0 if even a single packet gets replied to)
    (status, stdout, stderr) = run_command(options, "ping -w%s -n %s" %
                                           (timeout, ip))
    logger.debug("get_power_status(): %s - Stdout: %s - Stderr: %s" %
                 (status, stdout, stderr))
    if status == 0:
        return "on"
    else:
        return "off"


def set_power_status(conn, options):
    logger.debug("set_power_status(): %s" % options)
    # If we got here it means the previous call to get_power_status() returned
    # on At this point we've been invoked but the node is still reachable over
    # the cross connect, so we can just error out.
    ip = options['--crosscableip']
    if options['--action'] == 'off':
        logger.error("We've been asked to turn off the node at %s but the "
                     "cross-cable link is up so erroring out" % ip)
        sys.exit(1)
    elif options['--action'] == 'on':
        logger.error("We've been asked to turn on the node at %s but the "
                     "cross-cable link is off so erroring out" % ip)
        sys.exit(1)
    else:
        logger.error("set_power_status() was called with action %s which "
                     "is not supported" % options['--action'])
        sys.exit(1)


def define_new_opts():
    all_opt["crosscableip"] = {
        "getopt": "a:",
        "longopt": "crosscableip",
        "help": "-a, --crosscableip=[IP]      IP over the cross-cable link",
        "required": "1",
        "shortdesc": "Cross-cable IP",
        "order": 1
    }
    all_opt["timeout"] = {
        "getopt": "T:",
        "longopt": "timeout",
        "help": "-T, --timeout=[seconds]      timeout in seconds",
        "required": "0",
        "shortdesc": "No ICMP reply in 5 seconds -> Node is considered dead",
        "default": "5",
        "order": 1
    }


def main():
    atexit.register(atexit_handler)

    device_opt = ["crosscableip", "timeout", "no_password", "no_login", "port"]
    define_new_opts()

    options = check_input(device_opt, process_input(device_opt))

    docs = {}
    docs["shortdesc"] = "Fence agent for cross-link two-node clusters"
    docs["longdesc"] = "This agent helps two-node clusters to tackle the " \
                       "situation where one node lost power, cannot be " \
                       "fenced by telling pacemaker that if the node is not " \
                       "reachable over the crosslink cable, we can assume " \
                       "it is dead"
    docs["vendorurl"] = ""
    show_docs(options, docs)

    run_delay(options)

    result = fence_action(None, options, set_power_status, get_power_status)
    sys.exit(result)


if __name__ == "__main__":
    main()
