#!/usr/bin/python

import sys
import os
import subprocess
import logging
import json
import time

INPUT_FILE = os.environ["BINMITM_INPUT"]\
	if "BINMITM_INPUT" in os.environ else None
OUTPUT_FILE = os.environ["BINMITM_OUTPUT"]\
	if "BINMITM_OUTPUT" in os.environ else None
COUNTER_FILE = os.environ["BINMITM_COUNTER_FILE"]\
	if "BINMITM_COUNTER_FILE" in os.environ else ".binmitm_counter"
ENV_VARS = os.environ["BINMITM_ENV"].split(",")\
	if "BINMITM_ENV" in os.environ else []
IGNORE_TIMING = "BINMITM_IGNORE_TIMING" in os.environ
DEBUG = "BINMITM_DEBUG" in os.environ


def log_debug(msg):
	if DEBUG:
		logging.error(msg)


def _exit(ret):
	if COUNTER_FILE and os.path.isfile(COUNTER_FILE):
		try:
			os.remove(COUNTER_FILE)
		except Exception as e:
			log_debug("Unable to delete counter file ({0}): {1}".format(
				COUNTER_FILE, e.message
			))
			try:
				with open(COUNTER_FILE, "w") as f:
					f.write("0\n")
				log_debug(
					"0 written into counter file ({0})".format(COUNTER_FILE)
				)
			except Exception as e:
				log_debug("Unable to write 0 to counter file ({0}): {1}".format(
					COUNTER_FILE, e.message
				))
	sys.exit(ret)


def get_count(max_count):
	count = 0
	if os.path.isfile(COUNTER_FILE):
		try:
			with open(COUNTER_FILE, "r+") as f:
				count = int(f.readline().strip())
				f.seek(0)
				f.truncate()
				f.write("{0}\n".format((count+1) % max_count))
		except Exception as e:
			log_debug("Unable to read/write from/to '{0}': {1}".format(
				COUNTER_FILE, e.message
			))
	else:
		if max_count != 1:
			try:
				with open(COUNTER_FILE, "w") as f:
					f.write("1\n")
			except Exception as e:
				log_debug("Unable to write to '{0}': {1}".format(
					COUNTER_FILE, e.message
				))
	return count


def record(argv):
	output = OUTPUT_FILE and not INPUT_FILE
	env = os.environ.copy()

	cur_output = {
		"request": {
			"argv": argv,
			"env": {}
		},
		"response": {},
		"time": {}
	}

	for e in ENV_VARS:
		if e in env:
			cur_output["request"]["env"][e] = env[e]

	proc_start_time = time.time()
	process = None

	try:
		process = subprocess.Popen(
			argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
		)
	except OSError as e:
		log_debug("Unable to run command '{0}': {1}".format(
			" ".join(argv), e.message
		))
		_exit(127)

	status = process.wait()
	cur_output["time"]["perform_duration"] = time.time() - proc_start_time

	(pipe_stdout, pipe_stderr) = process.communicate()
	process.stdout.close()
	process.stderr.close()

	cur_output["response"]["stderr"] = pipe_stderr
	cur_output["response"]["stdout"] = pipe_stdout
	cur_output["response"]["return_code"] = status

	sys.stderr.write(pipe_stderr)
	sys.stdout.write(pipe_stdout)

	if output:
		try:
			if os.path.isfile(OUTPUT_FILE):
				with open(OUTPUT_FILE, "r+") as f:
					output_values = []

					try:
						output_values = json.load(f)
					except:
						log_debug(
							"Parsing output file '{0}' failed. It is "
							"considered as empty.".format(OUTPUT_FILE)
						)

					output_values.append(cur_output)
					f.truncate()
					f.seek(0)
					json.dump(output_values, f, indent=4)
			else:
				with open(OUTPUT_FILE, "w") as f:
					json.dump([cur_output], f, indent=4)
		except (IOError, ValueError) as e:
			log_debug("Unable to store data to file '{0}': {1}".format(
				OUTPUT_FILE, e.message
			))
	sys.exit(status)


def replay(argv):
	start_time = time.time()
	env = os.environ.copy()
	input_values = []

	try:
		with open(INPUT_FILE) as f:
			input_values = json.load(f)
	except (ValueError, IOError) as e:
		log_debug("Unable to parse input file '{0}': {1}".format(
			OUTPUT_FILE, e.message
		))

	if not input_values:
		log_debug("Empty input")
		_exit(127)

	input_number = get_count(len(input_values))
	if input_number >= len(input_values):
		log_debug("Unable to get current input")
		_exit(127)

	cur_input = input_values[input_number]
	if cur_input["request"]["argv"] != argv:
		log_debug(
			"Expected different command (Expected: '{0}', Given: '{1}')".format(
				" ".join(cur_input["request"]["argv"]),
				" ".join(argv)
			)
		)
		_exit(127)

	env.update(cur_input["request"]["env"])
	sys.stderr.write(cur_input["response"]["stderr"])
	sys.stdout.write(cur_input["response"]["stdout"])

	if not IGNORE_TIMING:
		time_left = cur_input["time"]["perform_duration"] - (
			time.time() - start_time
		)

		if time_left > 0:
			log_debug("Sleeping for {0} s".format(time_left))
			time.sleep(time_left)
		else:
			log_debug("Uooops! We are running {0} s longer.".format(
				abs(time_left)
			))

	sys.exit(cur_input["response"]["return_code"])


def main(argv):
	if not argv:
		print "No command to run"
		_exit(127)
	if INPUT_FILE:
		replay(argv)
	else:
		record(argv)


if __name__ == "__main__":
	main(sys.argv[1:])
