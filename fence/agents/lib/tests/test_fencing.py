#!/usr/bin/python

import unittest
import sys
sys.path.append("..")
import fencing
import copy

class Test_join2(unittest.TestCase):
	def test_single(self):
		words = ["Mike"]
		self.assertEqual(fencing._join2(words), "Mike")
		self.assertEqual(fencing._join2(words, last_separator=" xor "), "Mike")
		self.assertEqual(fencing._join2(words, normal_separator=" xor "), "Mike")

	def test_double(self):
		words = ["Mike", "John"]
		self.assertEqual(fencing._join2(words), "Mike and John")
		self.assertEqual(fencing._join2(words, last_separator=" xor "), "Mike xor John")
		self.assertEqual(fencing._join2(words, normal_separator=" xor "), "Mike and John")

	def test_triple(self):
		words = ["Mike", "John", "Adam"]
		self.assertEqual(fencing._join2(words), "Mike, John and Adam")
		self.assertEqual(fencing._join2(words, last_separator=" xor "), "Mike, John xor Adam")
		self.assertEqual(fencing._join2(words, normal_separator=" xor "), "Mike xor John and Adam")

	def test_quadruple(self):
		words = ["Eve", "Mike", "John", "Adam"]
		self.assertEqual(fencing._join2(words), "Eve, Mike, John and Adam")
		self.assertEqual(fencing._join2(words, last_separator=" xor "), "Eve, Mike, John xor Adam")
		self.assertEqual(fencing._join2(words, normal_separator=" xor "), "Eve xor Mike xor John and Adam")

class Test_add_dependency_options(unittest.TestCase):
	basic_set = fencing.DEPENDENCY_OPT["default"]

	def test_add_nothing(self):
		self.assertEqual(set(fencing._add_dependency_options([])), set(self.basic_set))
		self.assertEqual(set(fencing._add_dependency_options(["not-exist"])), set(self.basic_set))

	def test_add_single(self):
		self.assertEqual(set(fencing._add_dependency_options(["passwd"])), set(self.basic_set + ["passwd_script"]))

	def test_add_tuple(self):
		self.assertEqual(set(fencing._add_dependency_options(["ssl", "passwd"])), \
			set(self.basic_set + ["passwd_script", "ssl_secure", "ssl_insecure", "gnutlscli_path"]))

class Test_set_default_values(unittest.TestCase):
	original_all_opt = None

	def setUp(self):
		# all_opt[*]["default"] can be changed during tests
		self.original_all_opt = copy.deepcopy(fencing.all_opt)

	def tearDown(self):
		fencing.all_opt = copy.deepcopy(self.original_all_opt)

	def _prepare_options(self, device_opts, args = {}):
		device_opts = fencing._add_dependency_options(device_opts) + device_opts

		arg_opts = args
		options = dict(arg_opts)
		options["device_opt"] = device_opts
		fencing._update_metadata(options)
		return fencing._set_default_values(options)

	def test_status_io(self):
		options = self._prepare_options([])

		self.assertEqual(options["--action"], "reboot")
		self.assertIsNone(options.get("--not-exist", None))

	def test_status_fabric(self):
		options = self._prepare_options(["fabric_fencing"])
		self.assertEqual(options["--action"], "off")

	def test_ipport_nothing(self):
		# should fail because connection method (telnet/ssh/...) is not set at all
		self.assertRaises(IndexError, self._prepare_options, ["ipaddr"])

	def test_ipport_set(self):
		options = self._prepare_options(["ipaddr", "telnet"], {"--ipport" : "999"})
		self.assertEqual(options["--ipport"], "999")

	def test_ipport_telnet(self):
		options = self._prepare_options(["ipaddr", "telnet"])
		self.assertEqual(options["--ipport"], "23")

	def test_ipport_ssh(self):
		options = self._prepare_options(["ipaddr", "secure"], {"--ssh" : "1"})
		self.assertEqual(options["--ipport"], "22")

	def test_ipport_sshtelnet_use_telnet(self):
		options = self._prepare_options(["ipaddr", "secure", "telnet"])
		self.assertEqual(options["--ipport"], "23")

	def test_ipport_sshtelnet_use_ssh(self):
		options = self._prepare_options(["ipaddr", "secure", "telnet"], {"--ssh" : "1"})
		self.assertEqual(options["--ipport"], "22")

	def test_ipport_ssl(self):
		options = self._prepare_options(["ipaddr", "ssl"], {"--ssl-secure" : "1"})
		self.assertEqual(options["--ipport"], "443")

	def test_ipport_ssl_insecure_as_default(self):
		fencing.all_opt["ssl_insecure"]["default"] = "1"
		options = self._prepare_options(["ipaddr", "ssl"])
		self.assertEqual(options["--ipport"], "443")

	def test_ipport_snmp(self):
		options = self._prepare_options(["ipaddr", "community"])
		self.assertEqual(options["--ipport"], "161")

	def test_ipport_web(self):
		options = self._prepare_options(["ipaddr", "web", "ssl"])
		self.assertEqual(options["--ipport"], "80")

	def test_path_telnet(self):
		options = self._prepare_options(["ipaddr", "telnet"])
		self.assertTrue("--telnet-path" in options)

if __name__ == '__main__':
	unittest.main()
