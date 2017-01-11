#!/usr/bin/env python2
'''
View a log file with an optional time dilation.
See --help for usage.
'''

import sys
import mitmproxy


def main():
    '''
    Call the log viewer
    '''
    (opts, _) = mitmproxy.viewer_option_parser()

    if opts.inputfile is None:
        print "Need to specify an input file."
        sys.exit(1)
    else:
        mitmproxy.logviewer(opts.inputfile, opts.delaymod)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
