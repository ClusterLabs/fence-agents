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
do_action_monitor (void)
{
    const char cmdline_path[] = "/proc/cmdline";
    FILE *procFile;
    size_t sz = 0;
    char *lines = NULL;
    int result = 1;

    procFile = fopen(cmdline_path, "r");

    if (procFile == NULL) {
        log_error (0, "Unable to open file %s (%s)\n", cmdline_path, strerror (errno));
        return 1;
    }

    while (!feof (procFile)) {
        ssize_t rv = getline (&lines, &sz, procFile);
        if ((rv != -1) && (strstr(lines, "crashkernel=") != NULL)) {
            result = 0;
        }
    }

    free (lines);
    fclose (procFile);

    return result;
}

static int
do_action_off (const fence_kdump_opts_t *opts)
{
    int error;
    fd_set rfds;
    fence_kdump_msg_t msg;
    fence_kdump_node_t *node;
    struct timeval timeout;
    struct addrinfo hints;
    fence_kdump_node_t *check_node;
    char addr[NI_MAXHOST];
    char port[NI_MAXSERV];
    struct sockaddr_storage ss;
    socklen_t size = sizeof (ss);

    if (list_empty (&opts->nodes)) {
        return (1);
    } else {
        node = list_first_entry (&opts->nodes, fence_kdump_node_t, list);
    }

    timeout.tv_sec = opts->timeout;
    timeout.tv_usec = 0;

    FD_ZERO (&rfds);
    FD_SET (node->socket, &rfds);

    // create listening socket
    memset (&hints, 0, sizeof (hints));

    hints.ai_family = opts->family;
    hints.ai_socktype = SOCK_DGRAM;
    hints.ai_protocol = IPPROTO_UDP;
    hints.ai_flags = AI_NUMERICSERV;

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

    error = bind (node->socket, node->info->ai_addr, node->info->ai_addrlen);
    if (error != 0) {
        log_error (2, "bind (%s)\n", strerror (errno));
        free_node (node);
        return (1);
    }

    list_for_each_entry (check_node, &opts->nodes, list) {
        log_debug (0, "waiting for message from '%s'\n", check_node->addr);
	if (node->info->ai_family != check_node->info->ai_family) {
            log_error (0, "mixing IPv4 and IPv6 nodes is not supported\n");
            return (1);
	}
    }

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

        error = recvfrom (node->socket, &msg, sizeof (msg), 0, (struct sockaddr *) &ss, &size);
        if (error < 0) {
            log_error (2, "recvfrom (%s)\n", strerror (errno));
            continue;
        }

        error = getnameinfo ((struct sockaddr *) &ss, size,
                             addr, sizeof (addr),
                             port, sizeof (port),
                             NI_NUMERICHOST | NI_NUMERICSERV);
        if (error != 0) {
            log_error (2, "getnameinfo (%s)\n", gai_strerror (error));
            continue;
        }

        if (msg.magic != FENCE_KDUMP_MAGIC) {
            log_debug (1, "invalid magic number '0x%X'\n", msg.magic);
            continue;
        }

        // check if we have matched messages from any known node
        list_for_each_entry (check_node, &opts->nodes, list) {
            error = strcasecmp (check_node->addr, addr);
            if (error == 0 ) {
                switch (msg.version) {
                case FENCE_KDUMP_MSGV1:
                    log_debug (0, "received valid message from '%s'\n", addr);
                    return (0);
                default:
                    log_debug (1, "invalid message version '0x%X'\n", msg.version);
                    continue;
                }
            }
        }
    log_debug (1, "discard message from '%s'\n", addr);

    }

    return (1);
}

static int
do_action_metadata (const char *self)
{
    fprintf (stdout, "<?xml version=\"1.0\" ?>\n");
    fprintf (stdout, "<resource-agent name=\"%s\"", basename (self));
    fprintf (stdout, " shortdesc=\"fencing agent for use with kdump crash recovery service\">\n");
    fprintf (stdout, "<longdesc>");
    fprintf (stdout, "fence_kdump is an I/O fencing agent to be used with the kdump\n"
                     "crash recovery service. When the fence_kdump agent is invoked,\n"
                     "it will listen for a message from the failed node that acknowledges\n"
                     "that the failed node it executing the kdump crash kernel.\n"
                     "Note that fence_kdump is not a replacement for traditional\n"
                     "fencing methods. The fence_kdump agent can only detect that a\n"
                     "node has entered the kdump crash recovery service. This allows the\n"
                     "kdump crash recovery service complete without being preempted by\n"
                     "traditional power fencing methods.\n\n"
                     "Note: the \"off\" action listen for message from failed node that\n"
                     "acknowledges node has entered kdump crash recovery service. If a valid\n"
                     "message is received from the failed node, the node is considered to be\n"
                     "fenced and the agent returns success. Failure to receive a valid\n"
                     "message from the failed node in the given timeout period results in\n"
                     "fencing failure. When multiple node names/IP addresses are specified\n"
                     "a single valid message is sufficient for success. This is useful when\n"
                     "single node can send message via several different IP addresses.\n");
    fprintf (stdout, "</longdesc>\n");
    fprintf (stdout, "<vendor-url>http://www.kernel.org/pub/linux/utils/kernel/kexec/</vendor-url>\n");

    fprintf (stdout, "<parameters>\n");

    fprintf (stdout, "\t<parameter name=\"nodename\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-n, --nodename=NODE[,NODE...]\" />\n");
    fprintf (stdout, "\t\t<content type=\"string\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "List of names or IP addresses of node to be fenced. This option is\n"
	     "required for the \"off\" action. Multiple values separated by commas\n"
	     "can be specified. All values must be of same IP network family." );
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"ipport\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-p, --ipport=PORT\" />\n");
    fprintf (stdout, "\t\t<content type=\"string\" default=\"7410\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "IP port number that the fence_kdump agent will use to listen for\n"
             "messages.");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"family\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-f, --family=FAMILY\" />\n");
    fprintf (stdout, "\t\t<content type=\"string\" default=\"auto\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "IP network family. Force the fence_kdump agent to use a specific\n"
             "family. The value for FAMILY can be \"auto\", \"ipv4\", or\n"
             "\"ipv6\".");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"action\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-o, --action=ACTION\" />\n");
    fprintf (stdout, "\t\t<content type=\"string\" default=\"off\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "Fencing action to perform. The value for ACTION can be either\n"
             "\"off\" or \"metadata\".");
    fprintf (stdout, "\t</parameter>\n");

    fprintf (stdout, "\t<parameter name=\"timeout\" unique=\"0\" required=\"0\">\n");
    fprintf (stdout, "\t\t<getopt mixed=\"-t, --timeout=TIMEOUT\" />\n");
    fprintf (stdout, "\t\t<content type=\"string\" default=\"60\" />\n");
    fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
             "Number of seconds to wait for message from failed node. If no message\n"
             "is received within TIMEOUT seconds, the fence_kdump agent\n"
             "returns failure.");
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
    fprintf (stdout, "\t<action name=\"monitor\" />\n");
    fprintf (stdout, "\t<action name=\"metadata\" />\n");
    fprintf (stdout, "\t<action name=\"validate-all\" />\n");
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
             "  -n, --nodename=NODE[,NODE...]List of names or IP addresses of node to be fenced");
    fprintf (stdout, "%s\n",
             "  -p, --ipport=PORT            IP port number (default: 7410)");
    fprintf (stdout, "%s\n",
             "  -f, --family=FAMILY          Network family: ([auto], ipv4, ipv6)");
    fprintf (stdout, "%s\n",
             "  -o, --action=ACTION          Fencing action: ([off], monitor, metadata, validate-all)");
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

    strncpy (node->name, opts->nodename, sizeof (node->name) - 1);
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
    char *ptr;
    char *node_list;

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
        node_list = (char *)malloc(strlen(opts.nodename)+1);

        strcpy(node_list, opts.nodename); //make local copy of nodename on which we can safely iterate
        // iterate through node_list
        for (ptr = strtok(node_list, ","); ptr != NULL; ptr = strtok(NULL, ",")) {
            set_option_nodename (&opts, ptr); //overwrite nodename for next function
            if (get_options_node (&opts) != 0) {
                log_error (0, "failed to get node '%s'\n", opts.nodename);
                exit (1);
            }
        }
        free(node_list);
    }

    if (verbose != 0) {
        //clear nodename to avoid showing just last nodename here
        free(opts.nodename);
        opts.nodename = NULL;
        print_options (&opts);
    }

    switch (opts.action) {
    case FENCE_KDUMP_ACTION_OFF:
        error = do_action_off (&opts);
        break;
    case FENCE_KDUMP_ACTION_METADATA:
        error = do_action_metadata (argv[0]);
        break;
    case FENCE_KDUMP_ACTION_MONITOR:
        error = do_action_monitor ();
        break;
    case FENCE_KDUMP_ACTION_VALIDATE:
	error = 0;
	break;
    default:
        break;
    }

    free_options (&opts);

    return (error);
}
