#!/usr/bin/python

import unittest
import fence_testing

class TestPrepareCommand(unittest.TestCase):
	DEVICE_MISSING_OPTION = "devices.d/invalid-missing_option.cfg"
	DEVICE_CORRECT = "devices.d/true.cfg"
	DEVICE_CORRECT_WITH_ACTION = "devices.d/true-with_action.cfg"

	def test_missing_device(self):
		self.assertRaises(fence_testing._prepare_command, None, "getopt")

	def test_missing_option(self):
		self.assertRaises(AssertionError, fence_testing._prepare_command, self.DEVICE_MISSING_OPTION, "stdin")

	def test_valid_methods(self):
		fence_testing._prepare_command(self.DEVICE_CORRECT, "getopt")
		fence_testing._prepare_command(self.DEVICE_CORRECT, "longopt")
		fence_testing._prepare_command(self.DEVICE_CORRECT, "stdin")

	def test_invalid_method(self):
		self.assertRaises(AssertionError, fence_testing._prepare_command, self.DEVICE_CORRECT, "invalid")

	def test_is_action_ignored(self):
		(command1, _) = fence_testing._prepare_command(self.DEVICE_CORRECT, "getopt")
		(command2, _) = fence_testing._prepare_command(self.DEVICE_CORRECT_WITH_ACTION, "getopt")
		self.assertEqual(command1, command2)

	def test_is_stdin_empty(self):
		(_, stdin) = fence_testing._prepare_command(self.DEVICE_CORRECT, "getopt")
		self.assertEqual(None, stdin)
		(_, stdin) = fence_testing._prepare_command(self.DEVICE_CORRECT, "longopt")
		self.assertEqual(None, stdin)

	def test_prepared_command_getopt(self):
		## Test also fallback to longopt if short is not present
		(command, _) = fence_testing._prepare_command(self.DEVICE_CORRECT, "getopt")
		self.assertEqual("/bin/true -l foo -p bar -a fence.example.com --plug 1", command)

	def test_prepared_command_longopt(self):
		(command, _) = fence_testing._prepare_command(self.DEVICE_CORRECT, "longopt")
		self.assertEqual("/bin/true --username foo --password bar --ip fence.example.com --plug 1", command)

	def test_prepared_command_stdin(self):
		(command, stdin) = fence_testing._prepare_command(self.DEVICE_CORRECT, "stdin")
		self.assertEqual("/bin/true", command)
		self.assertEqual("login=foo\npasswd=bar\nipaddr=fence.example.com\nport=1\n", stdin)

class TestTestAction(unittest.TestCase):
	def test_valid_actions(self):
		pass

	def test_invalid_actions(self):
		pass

	def test_valid_return_code(self):
		pass

	def test_invalid_return_code(self):
		pass

	def test_valid_re_contains(self):
		pass

	def test_invalid_re_contains(self):
		pass

if __name__ == '__main__':
	unittest.main()
