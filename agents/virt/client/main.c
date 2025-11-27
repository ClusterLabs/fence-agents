/*
  Copyright Red Hat, Inc. 2006

  This program is free software; you can redistribute it and/or modify it
  under the terms of the GNU General Public License as published by the
  Free Software Foundation; either version 2, or (at your option) any
  later version.

  This program is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; see the file COPYING.  If not, write to the
  Free Software Foundation, Inc.,  675 Mass Ave, Cambridge,
  MA 02139, USA.
*/
/*
 * Author: Lon Hohberger <lhh at redhat.com>
 */

#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/ioctl.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <netinet/in.h>
#include <sys/time.h>
#include <errno.h>
#include <pthread.h>
#include <libgen.h>
#include <syslog.h>

/* Local includes */
#include "xvm.h"
#include "options.h"
#include "debug.h"
#include "client.h"


int
main(int argc, char **argv)
{
	fence_virt_args_t args;
	const char *my_options;
	int ret = 0;

	args_init(&args);
	if (!strcmp(basename(argv[0]), "fence_xvm")) {
		my_options = "di:a:p:r:C:c:k:M:n:H:uo:t:?hVw:";
		args.mode = MODE_MULTICAST;
	} else {
		my_options = "dD:P:A:p:M:n:H:o:t:?hVT:S::C:c:k:w:";
		args.mode = MODE_SERIAL;
	}

	if (argc == 1) {
		args_get_stdin(my_options, &args);
	} else {
		args_get_getopt(argc, argv, my_options, &args);
	}

	if (args.flags & F_HELP) {
		args_usage(argv[0], my_options, 0);

                printf("With no command line argument, arguments are "
                       "read from standard input.\n");
                printf("Arguments read from standard input take "
                       "the form of:\n\n");
                printf("    arg1=value1\n");
                printf("    arg2=value2\n\n");

		args_usage(argv[0], my_options, 1);
		exit(0);
	}

	if (args.flags & F_VERSION) {
		printf("%s %s\n", basename(argv[0]), XVM_VERSION);
#ifdef VERSION
		printf("fence release %s\n", VERSION);
#endif
		exit(0);
	}

	openlog(basename(argv[0]), LOG_NDELAY | LOG_PID, LOG_DAEMON);

	args_finalize(&args);
	dset(args.debug);

	if (args.debug > 0)
		args_print(&args);

	/* Additional validation here */
	if (!args.domain && (args.op != FENCE_DEVSTATUS &&
			     args.op != FENCE_HOSTLIST &&
			     args.op != FENCE_METADATA)) {
		fprintf(stderr, "No domain specified!\n");
		syslog(LOG_ERR, "No domain specified");
		args.flags |= F_ERR;
	}

	if (args.net.ipaddr)
		args.mode = MODE_TCP;

	if (args.net.cid >= 2)
		args.mode = MODE_VSOCK;

	if (args.flags & F_ERR) {
		if (args.op != FENCE_VALIDATEALL)
			args_usage(argv[0], my_options, (argc == 1));
		exit(1);
	}

	if (args.op == FENCE_VALIDATEALL)
		exit(0);

	if (args.op == FENCE_METADATA) {
		args_metadata(argv[0], my_options);
		exit(0);
	}

	if (args.delay > 0 &&
	    args.op != FENCE_STATUS &&
	    args.op != FENCE_DEVSTATUS &&
	    args.op != FENCE_HOSTLIST)
		sleep(args.delay);

	switch(args.mode) {
	case MODE_MULTICAST:
		ret = mcast_fence_virt(&args);
		break;
	case MODE_SERIAL:
		ret = serial_fence_virt(&args);
		break;
	case MODE_TCP:
		ret = tcp_fence_virt(&args);
		break;
	case MODE_VSOCK:
		ret = vsock_fence_virt(&args);
		break;
	default:
		ret = 1;
		goto out;
	}

	switch(ret) {
	case RESP_OFF:
		if (args.op == FENCE_STATUS)
			printf("Status: OFF\n");
		else if (args.domain)
			syslog(LOG_NOTICE, "Domain \"%s\" is OFF", args.domain);
		break;
	case 0:
		if (args.op == FENCE_STATUS)
			printf("Status: ON\n");
		else if (args.domain)
			syslog(LOG_NOTICE, "Domain \"%s\" is ON", args.domain);
		break;
	case RESP_FAIL:
		if (args.domain) {
			syslog(LOG_ERR, "Fence operation failed for domain \"%s\"",
				args.domain);
		} else
			syslog(LOG_ERR, "Fence operation failed");
		fprintf(stderr, "Operation failed\n");
		break;
	case RESP_PERM:
		if (args.domain) {
			syslog(LOG_ERR,
				"Permission denied for Fence operation for domain \"%s\"",
				args.domain);
		} else
			syslog(LOG_ERR, "Permission denied for fence operation");
		fprintf(stderr, "Permission denied\n");
		break;
	default:
		if (args.domain) {
			syslog(LOG_ERR, "Unknown response (%d) for domain \"%s\"",
				ret, args.domain);
		} else
			syslog(LOG_ERR, "Unknown response (%d)", ret);
		fprintf(stderr, "Unknown response (%d)\n", ret);
		break;
	}

out:
	closelog();
	exit(ret);
}
