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
 * @file fence_virtd.c: Implementation of server daemon for Xen virtual
 * machine fencing.  This uses SA AIS CKPT b.1.0 checkpointing API to 
 * store virtual machine states.
 *
 * Author: Lon Hohberger <lhh at redhat.com>
 */
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

/* Local includes */
#include "xvm.h"
#include "options.h"
#include "debug.h"
#include <client.h>


int
main(int argc, char **argv)
{
	fence_virt_args_t args;
	const char *my_options;
	int ret = 0;

	args_init(&args);
	if (!strcmp(basename(argv[0]), "fence_xvm")) {
       		my_options = "di:a:p:r:C:c:k:M:H:uo:t:?hVw:";
		args.mode = MODE_MULTICAST;
	} else {
       		my_options = "dD:P:A:p:M:H:o:t:?hVT:C:c:k:w:";
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
#ifdef FENCE_RELEASE_NAME
		printf("fence release %s\n", FENCE_RELEASE_NAME);
#endif
		exit(0);
	}

	args_finalize(&args);
	dset(args.debug);
	
	if (args.debug > 0) 
		args_print(&args);

	/* Additional validation here */
	if (!args.domain && (args.op != FENCE_DEVSTATUS &&
			     args.op != FENCE_HOSTLIST &&
			     args.op != FENCE_METADATA)) {
		printf("No domain specified!\n");
		args.flags |= F_ERR;
	}

	if (args.net.ipaddr) {
		args.mode = MODE_TCP;
	}

	if (args.flags & F_ERR) {
		args_usage(argv[0], my_options, (argc == 1));
		exit(1);
	}

	if (args.op == FENCE_METADATA) {
		args_metadata(argv[0], my_options);
		return 0;
	}

	if (args.delay > 0)
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
	default:
		return 1;
	}

	switch(ret) {
	case RESP_OFF:
	case 0:
		break;
	case RESP_FAIL:
		printf("Operation failed\n");
		break;
	case RESP_PERM:
		printf("Permission denied\n");
		break;
	default:
		printf("Unknown response (%d)\n", ret);
		break;
	}

	return ret;
}
