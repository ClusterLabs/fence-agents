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

#include "options.h"
#include "message.h"
#include "version.h"

static int verbose = 0;

#define log_debug(lvl, fmt, args...)               \
do {                                               \
    if (lvl <= verbose) {                          \
        fprintf (stdout, "[debug]: " fmt, ##args); \
        syslog (LOG_INFO, fmt, ##args);            \
    }                                              \
} while (0);

#define log_error(lvl, fmt, args...)               \
do {                                               \
    if (lvl <= verbose) {                          \
        fprintf (stderr, "[error]: " fmt, ##args); \
        syslog (LOG_ERR, fmt, ##args);             \
    }                                              \
} while (0);

static int
trim (char *str)
{
    char *p;
    int len;

    if (!str) return (0);

    len = strlen (str);

    while (len--) {
        if (isspace (str[len])) {
            str[len] = 0;
        } else {
            break;
        }
    }

    for (p = str; *p && isspace (*p); p++);

    memmove (str, p, strlen (p) + 1);

    return (strlen (str));
}

static int
read_message (const fence_kdump_node_t *node, void *msg, int len)
{
    int error;
    char addr[NI_MAXHOST];
    char port[NI_MAXSERV];
    struct sockaddr_storage ss;
    socklen_t size = sizeof (ss);

    error = recvfrom (node->socket, msg, len, 0, (struct sockaddr *) &ss, &size);
    if (error < 0) {
        log_error (2, "recvfrom (%s)\n", strerror (errno));
        goto out;
    }

    error = getnameinfo ((struct sockaddr *) &ss, size,
                         addr, sizeof (addr),
                         port, sizeof (port),
                         NI_NUMERICHOST | NI_NUMERICSERV);
    if (error != 0) {
        log_error (2, "getnameinfo (%s)\n", gai_strerror (error));
        goto out;
    }

    error = strcasecmp (node->addr, addr);
    if (error != 0) {
        log_debug (1, "discard message from '%s'\n", addr);
    }

out:
    return (error);
}

static int
do_action_off (const fence_kdump_opts_t *opts)
{
    int error;
    fd_set rfds;
    fence_kdump_msg_t msg;
    fence_kdump_node_t *node;
    struct timeval timeout;

    if (list_empty (&opts->nodes)) {
        return (1);
    } else {
        node = list_first_entry (&opts->nodes, fence_kdump_node_t, list);
    }

    timeout.tv_sec = opts->timeout;
    timeout.tv_usec = 0;

    FD_ZERO (&rfds);
    FD_SET (node->socket, &rfds);

    log_debug (0, "waiting for message from '%s'\n", node->addr);

    for (;;) {
        error = select (node->socket + 1, &rfds, NULL, NULL, &timeout);
        if (error < 0) {
            log_error (2, "select (%s)\n", strerror (errno));
            break;
        }
        if (error == 0) {
            log_debug (0, "timeout after %d seconds\n", opts->timeout);
            break;
        }

        if (read_message (node, &msg, sizeof (msg)) != 0) {
            continue;
        }

        if (msg.magic != FENCE_KDUMP_MAGIC) {
            log_debug (1, "invalid magic number '0x%X'\n", msg.magic);
            continue;
        }

        switch (msg.version) {
        case FENCE_KDUMP_MSGV1:
            log_debug (0, "received valid message from '%s'\n", node->addr);
            return (0);
        default:
            log_debug (1, "invalid message version '0x%X'\n", msg.version);
            continue;
        }
    }

    return (1);
}

static int
do_action_metadata (const char *self)
{
    fprintf (stdout, "<?xml version=\"1.0\" ?>\n");
    fprintf (stdout, "<resource-agent name=\"%s\"", basename (self));
    fprintf (stdout, " shortdesc=\"Fence agent for use with kdump\">\n");
    fprintf (stdout, "<longdesc>");
    fprintf (stdout, "The fence_kdump agent is intended to be used with with kdump service.");
    fprintf (stdout, "</longdesc>\n");
    fprintf (stdout, "<vendor-url>http://www.kernel.org/pub/linux/utils/kernel/kexec/</vendor-url>\n");

    fprintf (stdout, "<parameters>\n");

    fprintf (stdout, "\t<parameter name=\"nodename\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-n, --nodename\" />\n");
    fprintf (stdout, "\t\t<content type=\"string\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "Name or IP address of node to be fenced");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"ipport\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-p, --ipport\" />\n");
    fprintf (stdout, "\t\t<content type=\"string\" default=\"7410\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "Port number");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"family\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-f, --family\" />\n");
    fprintf (stdout, "\t\t<content type=\"string\" default=\"auto\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "Network family");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"action\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-o, --action\" />\n");
    fprintf (stdout, "\t\t<content type=\"string\" default=\"off\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "Fencing action");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"timeout\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-t, --timeout\" />\n");
    fprintf (stdout, "\t\t<content type=\"string\" default=\"60\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "Timeout in seconds");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"verbose\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-v, --verbose\" />\n");
    fprintf (stdout, "\t\t<content type=\"boolean\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "Print verbose output");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"version\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-V, --version\" />\n");
    fprintf (stdout, "\t\t<content type=\"boolean\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "Print version");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"usage\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-h, --help\" />\n");
    fprintf (stdout, "\t\t<content type=\"boolean\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "Print usage");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "</parameters>\n");

    fprintf (stdout, "<actions>\n");
    fprintf (stdout, "\t<action name=\"off\" />\n");
    fprintf (stdout, "\t<action name=\"metadata\" />\n");
    fprintf (stdout, "</actions>\n");

    fprintf (stdout, "</resource-agent>\n");

    return (0);
}

static void
print_usage (const char *self)
{
    fprintf (stdout, "Usage: %s [options]\n", basename (self));
    fprintf (stdout, "\n");
    fprintf (stdout, "Options:\n");
    fprintf (stdout, "\n");
    fprintf (stdout, "%s\n",
             "  -n, --nodename=NODE          Name or IP address of node to be fenced");
    fprintf (stdout, "%s\n",
             "  -p, --ipport=PORT            IP port number (default: 7410)");
    fprintf (stdout, "%s\n",
             "  -f, --family=FAMILY          Network family: ([auto], ipv4, ipv6)");
    fprintf (stdout, "%s\n",
             "  -o, --action=ACTION          Fencing action: ([off], metadata)");
    fprintf (stdout, "%s\n",
             "  -t, --timeout=TIMEOUT        Timeout in seconds (default: 60)");
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

    hints.ai_family = node->info->ai_family;
    hints.ai_flags |= AI_PASSIVE;

    freeaddrinfo (node->info);

    node->info = NULL;
    error = getaddrinfo (NULL, node->port, &hints, &node->info);
    if (error != 0) {
        log_error (2, "getaddrinfo (%s)\n", gai_strerror (error));
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

    error = bind (node->socket, node->info->ai_addr, node->info->ai_addrlen);
    if (error != 0) {
        log_error (2, "bind (%s)\n", strerror (errno));
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
        { "nodename", required_argument, NULL, 'n' },
        { "ipport",   required_argument, NULL, 'p' },
        { "family",   required_argument, NULL, 'f' },
        { "action",   required_argument, NULL, 'o' },
        { "timeout",  required_argument, NULL, 't' },
        { "verbose",  optional_argument, NULL, 'v' },
        { "version",  no_argument,       NULL, 'V' },
        { "help",     no_argument,       NULL, 'h' },
        { 0, 0, 0, 0 }
    };

    while ((opt = getopt_long (argc, argv, "n:p:f:o:t:v::Vh", options, NULL)) != EOF) {
        switch (opt) {
        case 'n':
            set_option_nodename (opts, optarg);
            break;
        case 'p':
            set_option_ipport (opts, optarg);
            break;
        case 'f':
            set_option_family (opts, optarg);
            break;
        case 'o':
            set_option_action (opts, optarg);
            break;
        case 't':
            set_option_timeout (opts, optarg);
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

static void
get_options_stdin (fence_kdump_opts_t *opts)
{
    char buf[1024];
    char *opt;
    char *arg;

    while (fgets (buf, sizeof (buf), stdin) != 0) {
        if (trim (buf) == 0) {
            continue;
        }
        if (buf[0] == '#') {
            continue;
        }

        opt = buf;

        if ((arg = strchr (opt, '=')) != 0) {
            *arg = 0;
            arg += 1;
        } else {
            continue;
        }

        if (!strcasecmp (opt, "nodename")) {
            set_option_nodename (opts, arg);
            continue;
        }
        if (!strcasecmp (opt, "ipport")) {
            set_option_ipport (opts, arg);
            continue;
        }
        if (!strcasecmp (opt, "family")) {
            set_option_family (opts, arg);
            continue;
        }
        if (!strcasecmp (opt, "action")) {
            set_option_action (opts, arg);
            continue;
        }
        if (!strcasecmp (opt, "timeout")) {
            set_option_timeout (opts, arg);
            continue;
        }
        if (!strcasecmp (opt, "verbose")) {
            set_option_verbose (opts, arg);
            continue;
        }
    }

    verbose = opts->verbose;

    return;
}

int
main (int argc, char **argv)
{
    int error = 1;
    fence_kdump_opts_t opts;

    init_options (&opts);

    if (argc > 1) {
        get_options (argc, argv, &opts);
    } else {
        get_options_stdin (&opts);
    }

    openlog ("fence_kdump", LOG_CONS|LOG_PID, LOG_DAEMON);

    if (opts.action == FENCE_KDUMP_ACTION_OFF) {
        if (opts.nodename == NULL) {
            log_error (0, "action 'off' requires nodename\n");
            exit (1);
        }
        if (get_options_node (&opts) != 0) {
            log_error (0, "failed to get node '%s'\n", opts.nodename);
            exit (1);
        }
    }

    if (verbose != 0) {
        print_options (&opts);
    }

    switch (opts.action) {
    case FENCE_KDUMP_ACTION_OFF:
        error = do_action_off (&opts);
        break;
    case FENCE_KDUMP_ACTION_METADATA:
        error = do_action_metadata (argv[0]);
        break;
    default:
        break;
    }

    free_options (&opts);

    return (error);
}
