#!/usr/bin/python

import pexpect
import re
import logging
import time
import sys
import fencing

import fence_apc
import fence_bladecenter
import fence_brocade
import fence_rsa

def check_agent(conn, options, found_prompt, prompts, test_fn, eol=None):
    options["--action"] = "list"
    options["--command-prompt"] = found_prompt
    if any(x in options["--command-prompt"][0] for x in prompts):
        options["--command-prompt"] = prompts

        return test_fn(conn, options)
    return False

def get_list(conn, options, found_prompt, prompts, list_fn, eol=None):
    def test_fn(conn, options):
        if len(list_fn(conn, options)) > 0:
            return True
        else:
            return False

    return check_agent(conn, options, found_prompt, prompts, test_fn, eol)

""" *************************** MAIN ******************************** """


def detect_login_telnet(options):
    options["--ipport"] = 23
    re_login_string = r"([\r\n])((?!Last )login\s*:)|((?!Last )Login Name:  )|(username: )|(User Name :)"
    re_login = re.compile(re_login_string, re.IGNORECASE)
    re_pass = re.compile("(password)|(pass phrase)", re.IGNORECASE)

    options["eol"] = "\r\n"
    conn = fencing.fspawn(options, options["--telnet-path"])
    conn.send("set binary\n")
    conn.send("open %s -%s\n"%(options["--ip"], options["--ipport"]))

    conn.log_expect(re_login, int(options["--login-timeout"]))
    conn.send_eol(options["--username"])

    ## automatically change end of line separator
    screen = conn.read_nonblocking(size=100, timeout=int(options["--shell-timeout"]))
    if re_login.search(screen) != None:
        options["eol"] = "\n"
        conn.send_eol(options["--username"])
        conn.log_expect(re_pass, int(options["--login-timeout"]))
    elif re_pass.search(screen) == None:
        conn.log_expect(re_pass, int(options["--shell-timeout"]))

    try:
        conn.send_eol(options["--password"])
        valid_password = conn.log_expect([re_login] + \
                [pexpect.TIMEOUT], int(options["--shell-timeout"]))
        if valid_password == 0:
            ## password is invalid or we have to change EOL separator
            options["eol"] = "\r"
            conn.send_eol("")
            screen = conn.read_nonblocking(size=100, timeout=int(options["--shell-timeout"]))
            ## after sending EOL the fence device can either show 'Login' or 'Password'
            if re_login.search(conn.after + screen) != None:
                conn.send_eol("")
            conn.send_eol(options["--username"])
            conn.log_expect(re_pass, int(options["--login-timeout"]))
            conn.send_eol(options["--password"])
            conn.log_expect(pexpect.TIMEOUT, int(options["--login-timeout"]))
    except KeyError:
        fencing.fail(fencing.EC_PASSWORD_MISSING)

    found_cmd_prompt = guess_prompt(conn, options, conn.before)
    return (found_cmd_prompt, conn)

def guess_prompt(conn, options, before=""):
    time.sleep(2)
    conn.send_eol("")
    conn.send_eol("")

    conn.log_expect(pexpect.TIMEOUT, int(options["--login-timeout"]))
    lines = re.split(r'\r|\n', before + conn.before)
    logging.info("Cmd-prompt candidate: %s" % (lines[-1]))
    if lines.count(lines[-1]) >= 3:
        found_cmd_prompt = ["\n" + lines[-1]]
    else:
        if lines.count(lines[-1]) == 2:
            conn.log_expect(lines[-1], int(options["--shell-timeout"]))
            conn.log_expect(lines[-1], int(options["--shell-timeout"]))
            options["eol"] = "\r"
            conn.send_eol("")
            time.sleep(0.1)
            conn.send_eol("")
            time.sleep(0.1)
            conn.send_eol("")
            time.sleep(0.1)
            conn.log_expect(pexpect.TIMEOUT, int(options["--login-timeout"]))
            lines = re.split(r'\r|\n', conn.before)
            logging.info("Cmd-prompt candidate: %s" % (lines[1]))
            if lines.count(lines[-1]) >= 3:
                found_cmd_prompt = ["\n" + lines[-1]]
            else:
                print "Unable to obtain command prompt automatically"
                sys.exit(1)
        else:
            print "Unable to obtain command prompt automatically"
            print lines[-1]
            print conn.before
            sys.exit(1)

    conn.log_expect(found_cmd_prompt, int(options["--shell-timeout"]))
    conn.log_expect(found_cmd_prompt, int(options["--shell-timeout"]))
    conn.log_expect(found_cmd_prompt, int(options["--shell-timeout"]))

    # Handle situation when CR/LF is interpreted as ENTER, ENTER
    # In such case we will have get two additional command prompts to get on right position
    res = conn.log_expect([pexpect.TIMEOUT] + found_cmd_prompt, int(options["--shell-timeout"]))
    if res > 0:
        # @note: store that information?
        print "CMD twice"
        conn.log_expect(found_cmd_prompt, int(options["--shell-timeout"]))
    return found_cmd_prompt

def detect_login_ssh(options, version=2):
    options["--ipport"] = 22
    if version == "1":
        command = '%s %s@%s -p %s -1 -c blowfish -o PubkeyAuthentication=no' % (options["--ssh-path"], options["--username"], options["--ip"], options["--ipport"])
    else:
        command = '%s %s@%s -p %s -o PubkeyAuthentication=no' % (options["--ssh-path"], options["--username"], options["--ip"], options["--ipport"])

    conn = fencing.fspawn(options, command)
    result = conn.log_expect(["ssword:", "Are you sure you want to continue connecting (yes/no)?"], int(options["--login-timeout"]))
    if result == 1:
        conn.send("yes\n")
        conn.log_expect("ssword:", int(options["--login-timeout"]))

    conn.send(options["--password"] + "\n")

    found_cmd_prompt = guess_prompt(conn, options, conn.before)
    return (found_cmd_prompt, conn)

def detect_device(conn, options, found_cmd_prompt):
    if get_list(conn, options, found_cmd_prompt, prompts=["\n>", "\napc>"], list_fn=fence_apc.get_power_status):
        fencing.fence_logout(conn, "4")
        return "fence_apc # older serie"

    if get_list(conn, options, found_cmd_prompt, prompts=["\n>", "\napc>"], list_fn=fence_apc.get_power_status5):
        fencing.fence_logout(conn, "exit")
        return "fence_apc # v5+"

    ## Test fence_lpar with list action (HMC version 3 and 4)
    def test_lpar(conn, options):
        conn.send_eol("lssyscfg; echo $?")
        conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
        if "\n0\r\n" in conn.before:
            return True
        else:
            return False

    if check_agent(conn, options, found_cmd_prompt, [r":~>", r"]\$", r"\$ "], test_lpar):
        fencing.fence_logout(conn, "quit")
        return "fence_lpar # 2"

    if get_list(conn, options, found_cmd_prompt, prompts=["system>"], list_fn=fence_bladecenter.get_blades_list):
        fencing.fence_logout(conn, "exit")
        return "fence_bladecenter #2"

    if get_list(conn, options, found_cmd_prompt, prompts=["> "], list_fn=fence_brocade.get_power_status, eol="\n"):
        fencing.fence_logout(conn, "exit")
        return "fence_brocade #2"

    if get_list(conn, options, found_cmd_prompt, prompts=["> "], list_fn=fence_rsa.get_power_status):
        fencing.fence_logout(conn, "exit")
        return "fence_rsa"

    return None

# Test fence ilo moonshot
#cmd_possible = ["MP>", "hpiLO->"]
#options["--action"] = "list"
#options["--command-prompt"] = found_cmd_prompt
#options["eol"] = "\n"
#if any(x in options["--command-prompt"][0] for x in cmd_possible):
#    options["--command-prompt"] = cmd_possible
#
#    plugs = fence_ilo_moonshot.get_power_status(conn, options)
#    if len(plugs) > 0:
#        print "fence_ilo_moonshot # "
#        fencing.fence_logout(conn, "exit")
#        sys.exit(0)

def xxx():
    ## login mechanism as in fencing.py.py - differences is that we do not know command prompt
    #logging.getLogger().setLevel(logging.DEBUG)
    options = {}
    options["--ssh-path"] = "/usr/bin/ssh"
    options["--telnet-path"] = "/usr/bin/telnet"

    # virtual machine
    #options["--username"] = "marx"
    #options["--ip"] = "localhost"
    #options["--password"] = "batalion"

    # APC
    #options["--username"] = "labuser"
    #options["--ip"] = "pdu-bar.englab.brq.redhat.com"
    #options["--password"] = "labuser"

    # LPAR
    options["--username"] = "rhts"
    options["--ip"] = "ppc-hmc-01.mgmt.lab.eng.bos.redhat.com"
    #options["--ip"] = "ibm-js22-vios-02.rhts.eng.bos.redhat.com"
    options["--password"] = "100yard-"

    # Bladecenter
    options["--ip"] = "blade-mm.englab.brq.redhat.com"

    # Brocade
    #options["--ip"] = "hp-fcswitch-01.lab.bos.redhat.com"
    #options["--password"] = "password"
    #options["--username"] = "admin"

    # iLO Moonshot - chova sa to divne
    #options["--password"] = "Access@gis"
    #options["--username"] = "rcuser"
    #options["--ip"] = "hp-m1500-mgmt.gsslab.pnq.redhat.com"

    #options["--ip"] = "ibm-x3755-01-rsa.ovirt.rhts.eng.bos.redhat.com"
    #options["--username"] = "USERID"
    #options["--password"] = "PASSW0RD"

    options["--login-timeout"] = "10"
    options["--shell-timeout"] = "5"
    options["--power-timeout"] = "10"

    options["eol"] = "\r\n"

    (found_cmd_prompt, conn) = detect_login_telnet(options)
    #(found_cmd_prompt, conn) = detect_login_ssh(options)

    res = detect_device(conn, options, found_cmd_prompt)
    if not res is None:
        print res
        sys.exit(0)
    else:
        ## Nothing found
        sys.exit(2)

if __name__ == "__main__":
    xxx()
