## Check if fence agent uses only options["--??"] which are defined in fencing library or
## fence agent itself
##
## Usage: ./check_used_options.py fence-agent (e.g. lpar/fence_lpar.py)
##

import sys, re
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import all_opt

def main():
	agent = sys.argv[1]

	available = {}

	## all_opt from fencing library are imported
	for k in list(all_opt.keys()):
		if "longopt" in all_opt[k]:
			available["--" + all_opt[k]["longopt"]] = True

	## add UUID which is derived automatically from --plug if possible
	available["--uuid"] = True

	## all_opt defined in fence agent are found
	agent_file = open(agent)
	opt_re = re.compile(r"\s*all_opt\[\"([^\"]*)\"\] = {")
	opt_longopt_re = re.compile(r"\"longopt\"\s*:\s*\"([^\"]*)\"")

	in_opt = False
	for line in agent_file:
		if opt_re.search(line) != None:
			in_opt = True
		if in_opt and opt_longopt_re.search(line) != None:
			available["--" + opt_longopt_re.search(line).group(1)] = True
			in_opt = False

	## check if all options are defined
	agent_file = open(agent)
	option_use_re = re.compile(r"options\[\"(-[^\"]*)\"\]")
	option_has_re = re.compile(r"options.has_key\(\"(-[^\"]*)\"\)")

	counter = 0
	without_errors = True
	for line in agent_file:
		counter += 1

		for option in option_use_re.findall(line):
			if option not in available:
				print("ERROR on line %d in %s: option %s is not defined" % (counter, agent, option_use_re.search(line).group(1)))
				without_errors = False

		for option in option_has_re.findall(line):
			if option not in available:
				print("ERROR on line %d in %s: option %s is not defined" % (counter, agent, option_has_re.search(line).group(1)))
				without_errors = False

	if without_errors:
		sys.exit(0)
	else:
		sys.exit(1)

if __name__ == "__main__":
	main()
