#!/usr/bin/python -tt

from fencing import *

def main():
	for key in all_opt.keys():
		if all_opt[key].has_key("getopt") and all_opt[key].has_key("longopt"):
			print "s/options\[\"-" + all_opt[key]["getopt"].rstrip(":") + "\"\]/options[\"--" + \
				all_opt[key]["longopt"] + "\"]/g"
			print "s/options.has_key(\"-" + all_opt[key]["getopt"].rstrip(":") + "\")/options.has_key(" + \
				"\"--" + all_opt[key]["longopt"] + "\")/g"



if __name__ == "__main__":
	main()