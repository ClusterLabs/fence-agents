#!/usr/bin/python

import unittest
import autodetect as detect

class TestDetectDevice(unittest.TestCase):
    options = {}

    def setUp(self):
        self.options = {}
        self.options["--ssh-path"] = "/usr/bin/ssh"
        self.options["--telnet-path"] = "/usr/bin/telnet"
        self.options["--login-timeout"] = "10"
        self.options["--shell-timeout"] = "5"
        self.options["--power-timeout"] = "10"
        self.options["eol"] = "\r\n"

    def test_bladecenter(self):
        self.options["--username"] = "rhts"
        self.options["--password"] = "100yard-"
        self.options["--ip"] = "blade-mm.englab.brq.redhat.com"

        (found_cmd_prompt, conn) = detect.detect_login_telnet(self.options)
        res = detect.detect_device(conn, self.options, found_cmd_prompt)
        self.assertEqual('fence_bladecenter', res)

    def test_apc5(self):
        self.assertEqual('foo', 'foo')
        self.options["c"] = "c"
        print self.options

if __name__ == "__main__":
    unittest.main()
