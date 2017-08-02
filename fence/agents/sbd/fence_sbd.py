#!@PYTHON@ -tt

import sys, stat
import logging
import os
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import fail_usage, run_command, fence_action, all_opt
from fencing import atexit_handler, check_input, process_input, show_docs
from fencing import run_delay

DEVICE_INIT = 1
DEVICE_NOT_INIT = -3
PATH_NOT_EXISTS = -1
PATH_NOT_BLOCK = -2

def is_block_device(filename):
    """Checks if a given path is a valid block device

    Key arguments:
    filename -- the file to check

    Return codes:
    True if it's a valid block device
    False, otherwise
    """

    try:
        mode = os.lstat(filename).st_mode
    except OSError:
        return False
    else:
        return stat.S_ISBLK(mode)

def is_link(filename):
    """Checks if a given path is a link.

    Key arguments:
    filename -- the file to check

    Return codes:
    True if it's a link
    False, otherwise
    """

    try:
        mode = os.lstat(filename).st_mode
    except OSError:
        return False
    else:
        return stat.S_ISLNK(mode)

def check_sbd_device(options, device_path):
    """checks that a given sbd device exists and is initialized

    Key arguments:
    options -- options dictionary
    device_path -- device path to check

    Return Codes:
    1 / DEVICE_INIT if the device exists and is initialized
    -1 / PATH_NOT_EXISTS if the path does not exists
    -2 / PATH_NOT_BLOCK if the path exists but is not a valid block device
    -3 / DEVICE_NOT_INIT if the sbd device is not initialized
    """

    # First of all we need to check if the device is valid
    if not os.path.exists(device_path):
        return PATH_NOT_EXISTS

    # We need to check if device path is a symbolic link. If so we resolve that
    # link.
    if is_link(device_path):
        link_target = os.readlink(device_path)
        device_path = os.path.join(os.path.dirname(device_path), link_target)

    # As second step we make sure it's a valid block device
    if not is_block_device(device_path):
        return PATH_NOT_BLOCK

    cmd = "%s -d %s dump" % (options["--sbd-path"], device_path)

    (return_code, out, err) = run_command(options, cmd)

    for line in out.split("\n"):
        if len(line) == 0:
            continue

        # If we read "NOT dumped" something went wrong, e.g. the device is not
        # initialized.
        if "NOT dumped" in line:
            return DEVICE_NOT_INIT

    return DEVICE_INIT

def generate_sbd_command(options, command, arguments=None):
    """Generates a sbd command based on given arguments.

    Return Value:
    generated sbd command (string)
    """
    cmd = options["--sbd-path"]

    # add "-d" for each sbd device
    for device in parse_sbd_devices(options):
        cmd += " -d %s" % device

    cmd += " %s %s" % (command, arguments)

    return cmd

def send_sbd_message(conn, options, plug, message):
    """Sends a message to all sbd devices.

    Key arguments:
    conn -- connection structure
    options -- options dictionary
    plug -- plug to sent the message to
    message -- message to send

    Return Value:
    (return_code, out, err) Tuple containing the error code,
    """

    del conn

    arguments = "%s %s" % (plug, message)
    cmd = generate_sbd_command(options, "message", arguments)

    (return_code, out, err) = run_command(options, cmd)

    return (return_code, out, err)

def get_msg_timeout(options):
    """Reads the configured sbd message timeout from each device.

    Key arguments:
    options -- options dictionary

    Return Value:
    msg_timeout (integer, seconds)
    """

    # get the defined msg_timeout
    msg_timeout = -1 # default sbd msg timeout

    cmd = generate_sbd_command(options, "dump")

    (return_code, out, err) = run_command(options, cmd)

    for line in out.split("\n"):
        if len(line) == 0:
            continue

        if "msgwait" in line:
            tmp_msg_timeout = int(line.split(':')[1])
            if -1 != msg_timeout and tmp_msg_timeout != msg_timeout:
                logging.warn(\
                        "sbd message timeouts differ in different devices")
            # we only save the highest timeout
            if tmp_msg_timeout > msg_timeout:
                msg_timeout = tmp_msg_timeout

    return msg_timeout

def set_power_status(conn, options):
    """send status to sbd device (poison pill)

    Key arguments:
    conn -- connection structure
    options -- options dictionary

    Return Value:
    return_code -- action result (bool)
    """

    target_status = options["--action"]
    plug = options["--plug"]
    return_code = 99
    out = ""
    err = ""

    # Map fencing actions to sbd messages
    if "on" == target_status:
        (return_code, out, err) = send_sbd_message(conn, options, plug, "clear")
    elif "off" == target_status:
        (return_code, out, err) = send_sbd_message(conn, options, plug, "off")
    elif "reboot" == target_status:
        (return_code, out, err) = send_sbd_message(conn, options, plug, "reset")

    if 0 != return_code:
        logging.error("sending message to sbd device(s) \
                failed with return code %d", return_code)
        logging.error("DETAIL: output on stdout was \"%s\"", out)
        logging.error("DETAIL: output on stderr was \"%s\"", err)

    return not bool(return_code)

def reboot_cycle(conn, options):
    """" trigger reboot by sbd messages

    Key arguments:
    conn -- connection structure
    options -- options dictionary

    Return Value:
    return_code -- action result (bool)
    """

    plug = options["--plug"]
    return_code = 99
    out = ""
    err = ""

    (return_code, out, err) = send_sbd_message(conn, options, plug, "reset")
    return not bool(return_code)

def get_power_status(conn, options):
    """Returns the status of a specific node.

    Key arguments:
    conn -- connection structure
    options -- option dictionary

    Return Value:
    status -- status code (string)
    """

    status = "UNKWNOWN"
    plug = options["--plug"]

    nodelist = get_node_list(conn, options)

    # We need to check if the specified plug / node a already a allocated slot
    # on the device.
    if plug not in nodelist:
        logging.error("node \"%s\" not found in node list", plug)
    else:
        status = nodelist[plug][1]


    return status

def translate_status(sbd_status):
    """Translates the sbd status to fencing status.

    Key arguments:
    sbd_status -- status to translate (string)

    Return Value:
    status -- fencing status (string)
    """

    status = "UNKNOWN"


    # Currently we only accept "clear" to be marked as online. Eventually we
    # should also check against "test"
    online_status = ["clear"]

    offline_status = ["reset", "off"]

    if any(online_status_element in sbd_status \
            for online_status_element in online_status):
        status = "on"

    if any(offline_status_element in sbd_status \
            for offline_status_element in offline_status):
        status = "off"

    return status

def get_node_list(conn, options):
    """Returns a list of hostnames, registerd on the sbd device.

    Key arguments:
    conn -- connection options
    options -- options

    Return Value:
    nodelist -- dictionary wich contains all node names and there status
    """

    del conn

    nodelist = {}

    cmd = generate_sbd_command(options, "list")

    (return_code, out, err) = run_command(options, cmd)

    for line in out.split("\n"):
        if len(line) == 0:
            continue

        # if we read "unreadable" something went wrong
        if "NOT dumped" in line:
            return nodelist

        words = line.split()
        port = words[1]
        sbd_status = words[2]
        nodelist[port] = (port, translate_status(sbd_status))

    return nodelist

def parse_sbd_devices(options):
    """Returns an array of all sbd devices.

    Key arguments:
    options -- options dictionary

    Return Value:
    devices -- array of device paths
    """

    devices = [str.strip(dev) \
            for dev in str.split(options["--devices"], ",")]

    return devices

def define_new_opts():
    """Defines the all opt list
    """
    all_opt["devices"] = {
        "getopt" : ":",
        "longopt" : "devices",
        "help":"--devices=[device_a,device_b] \
Comma separated list of sbd devices",
        "required" : "1",
        "shortdesc" : "SBD Device",
        "order": 1
        }

    all_opt["sbd_path"] = {
        "getopt" : ":",
        "longopt" : "sbd-path",
        "help" : "--sbd-path=[path]              Path to SBD binary",
        "required" : "0",
        "default" : "@SBD_PATH@",
        "order": 200
        }

def main():
    """Main function
    """
    # We need to define "no_password" otherwise we will be ask about it if
    # we don't provide any password.
    device_opt = ["no_password", "devices", "port", "method", "sbd_path"]

    # close stdout if we get interrupted
    atexit.register(atexit_handler)

    define_new_opts()

    all_opt["method"]["default"] = "cycle"
    all_opt["method"]["help"] = "-m, --method=[method]          Method to fence (onoff|cycle) (Default: cycle)"

    options = check_input(device_opt, process_input(device_opt))

    # fill the needed variables to generate metadata and help text output
    docs = {}
    docs["shortdesc"] = "Fence agent for sbd"
    docs["longdesc"] = "fence_sbd is I/O Fencing agent \
which can be used in environments where sbd can be used (shared storage)."
    docs["vendorurl"] = ""
    show_docs(options, docs)

    # We need to check if --devices is given and not empty.
    if "--devices" not in options:
        fail_usage("No SBD devices specified. \
                At least one SBD device is required.")

    run_delay(options)

    # We need to check if the provided sbd_devices exists. We need to do
    # that for every given device.
    for device_path in parse_sbd_devices(options):
        logging.debug("check device \"%s\"", device_path)

        return_code = check_sbd_device(options, device_path)
        if PATH_NOT_EXISTS == return_code:
            logging.error("\"%s\" does not exist", device_path)
        elif PATH_NOT_BLOCK == return_code:
            logging.error("\"%s\" is not a valid block device", device_path)
        elif DEVICE_NOT_INIT == return_code:
            logging.error("\"%s\" is not initialized", device_path)
        elif DEVICE_INIT != return_code:
            logging.error("UNKNOWN error while checking \"%s\"", device_path)

        # If we get any error while checking the device we need to exit at this
        # point.
        if DEVICE_INIT != return_code:
            exit(return_code)

    # we check against the defined timeouts. If the pacemaker timeout is smaller
    # then that defined within sbd we should report this.
    power_timeout = int(options["--power-timeout"])
    sbd_msg_timeout = get_msg_timeout(options)
    if power_timeout <= sbd_msg_timeout:
        logging.warn("power timeout needs to be \
                greater then sbd message timeout")

    result = fence_action(\
                None, \
                options, \
                set_power_status, \
                get_power_status, \
                get_node_list, \
                reboot_cycle)

    sys.exit(result)

if __name__ == "__main__":
    main()
