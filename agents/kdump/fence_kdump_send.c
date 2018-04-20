/* -*- mode: C; c-basic-offset: 4; indent-tabs-mode: nil -*-
 *
 * Copyright (c) Ryan O'Hara (rohara@redhat.com)
 * Copyright (c) Red Hat, Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 *
 */

#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <getopt.h>
#include <unistd.h>
#include <syslog.h>
#include <ctype.h>
#include <errno.h>
#include <netdb.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>

#include "options.h"
#include "message.h"
#include "version.h"

static int verbose = 0;

#define log_debug(lvl, fmt, args...)               \
do {                                               \
    if (lvl <= verbose)                            \
        fprintf (stdout, "[debug]: " fmt, ##args); \
} while (0);

#define log_error(lvl, fmt, args...)               \
do {                                               \
    if (lvl <= verbose)                            \
        fprintf (stderr, "[error]: " fmt, ##args); \
} while (0);

static int
send_message (const fence_kdump_node_t *node, void *msg, int len)
{
    int error;

    error = sendto (node->socket, msg, len, 0, node->info->ai_addr, node->info->ai_addrlen);
    if (error < 0) {
        log_error (2, "sendto (%s)\n", strerror (errno));
        goto out;
    }

    log_debug (1, "message sent to node '%s'\n", node->addr);

out:
    return (error);
}

static void
print_usage (const char *self)
{
    fprintf (stdout, "Usage: %s [options] [nodes]\n", basename (self));
    fprintf (stdout, "\n");
    fprintf (stdout, "Options:\n");
    fprintf (stdout, "\n");
    fprintf (stdout, "%s\n",
             "  -p, --ipport=PORT            Port number (default: 7410)");
    fprintf (stdout, "%s\n",
             "  -f, --family=FAMILY          Network family ([auto], ipv4, ipv6)");
    fprintf (stdout, "%s\n",
             "  -c, --count=COUNT            Number of messages to send (default: 0)");
    fprintf (stdout, "%s\n",
             "  -i, --interval=INTERVAL      Interval in seconds (default: 10)");
    fprintf (stdout, "%s\n",
             "  -v, --verbose                Print verbose output");
    fprintf (stdout, "%s\n",
             "  -V, --version                Print version");
    fprintf (stdout, "%s\n",
             "  -h, --help                   Print usage");
    fprintf (stdout, "\n");

    return;
}

static int
get_options_node (fence_kdump_opts_t *opts)
{
    int error;
    struct addrinfo hints;
    fence_kdump_node_t *node;

    node = malloc (sizeof (fence_kdump_node_t));
    if (!node) {
        log_error (2, "malloc (%s)\n", strerror (errno));
        return (1);
    }

    memset (node, 0, sizeof (fence_kdump_node_t));
    memset (&hints, 0, sizeof (hints));

    hints.ai_family = opts->family;
    hints.ai_socktype = SOCK_DGRAM;
    hints.ai_protocol = IPPROTO_UDP;
    hints.ai_flags = AI_NUMERICSERV;

    strncpy (node->name, opts->nodename, sizeof (node->name));
    snprintf (node->port, sizeof (node->port), "%d", opts->ipport);

    node->info = NULL;
    error = getaddrinfo (node->name, node->port, &hints, &node->info);
    if (error != 0) {
        log_error (2, "getaddrinfo (%s)\n", gai_strerror (error));
        free_node (node);
        return (1);
    }

    error = getnameinfo (node->info->ai_addr, node->info->ai_addrlen,
                         node->addr, sizeof (node->addr),
                         node->port, sizeof (node->port),
                         NI_NUMERICHOST | NI_NUMERICSERV);
    if (error != 0) {
        log_error (2, "getnameinfo (%s)\n", gai_strerror (error));
        free_node (node);
        return (1);
    }

    node->socket = socket (node->info->ai_family,
                           node->info->ai_socktype,
                           node->info->ai_protocol);
    if (node->socket < 0) {
        log_error (2, "socket (%s)\n", strerror (errno));
        free_node (node);
        return (1);
    }

    list_add_tail (&node->list, &opts->nodes);

    return (0);
}

static void
get_options (int argc, char **argv, fence_kdump_opts_t *opts)
{
    int opt;

    struct option options[] = {
        { "ipport",   required_argument, NULL, 'p' },
        { "family",   required_argument, NULL, 'f' },
        { "count",    required_argument, NULL, 'c' },
        { "interval", required_argument, NULL, 'i' },
        { "verbose",  optional_argument, NULL, 'v' },
        { "version",  no_argument,       NULL, 'V' },
        { "help",     no_argument,       NULL, 'h' },
        { 0, 0, 0, 0 }
    };

    while ((opt = getopt_long (argc, argv, "p:f:c:i:v::Vh", options, NULL)) != EOF) {
        switch (opt) {
        case 'p':
            set_option_ipport (opts, optarg);
            break;
        case 'f':
            set_option_family (opts, optarg);
            break;
        case 'c':
            set_option_count (opts, optarg);
            break;
        case 'i':
            set_option_interval (opts, optarg);
            break;
        case 'v':
            set_option_verbose (opts, optarg);
            break;
        case 'V':
            print_version (argv[0]);
            exit (0);
        case 'h':
            print_usage (argv[0]);
            exit (0);
        default:
            print_usage (argv[0]);
            exit (1);
        }
    }

    verbose = opts->verbose;

    return;
}

int
main (int argc, char **argv)
{
    int count = 1;
    fence_kdump_msg_t msg;
    fence_kdump_opts_t opts;
    fence_kdump_node_t *node;

    init_options (&opts);

    if (argc > 1) {
        get_options (argc, argv, &opts);
    } else {
        print_usage (argv[0]);
        exit (1);
    }

    for (; optind < argc; optind++) {
        opts.nodename = argv[optind];
        if (get_options_node (&opts) != 0) {
            log_error (1, "failed to get node '%s'\n", opts.nodename);
        }
        opts.nodename = NULL;
    }

    if (list_empty (&opts.nodes)) {
        print_usage (argv[0]);
        exit (1);
    }

    if (verbose != 0) {
        print_options (&opts);
    }

    init_message (&msg);

    for (;;) {
        list_for_each_entry (node, &opts.nodes, list) {
            send_message (node, &msg, sizeof (msg));
        }

        if ((opts.count != 0) && (++count > opts.count)) {
            break;
        }

        sleep (opts.interval);
    }

    free_options (&opts);

    return (0);
}
