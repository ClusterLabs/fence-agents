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

#ifndef _FENCE_KDUMP_OPTIONS_H
#define _FENCE_KDUMP_OPTIONS_H

#include "list.h"

#define FENCE_KDUMP_NAME_LEN 256
#define FENCE_KDUMP_ADDR_LEN 46
#define FENCE_KDUMP_PORT_LEN 6

enum {
    FENCE_KDUMP_ACTION_OFF      = 0,
    FENCE_KDUMP_ACTION_ON       = 1,
    FENCE_KDUMP_ACTION_REBOOT   = 2,
    FENCE_KDUMP_ACTION_STATUS   = 3,
    FENCE_KDUMP_ACTION_LIST     = 4,
    FENCE_KDUMP_ACTION_MONITOR  = 5,
    FENCE_KDUMP_ACTION_METADATA = 6,
};

enum {
    FENCE_KDUMP_FAMILY_AUTO = AF_UNSPEC,
    FENCE_KDUMP_FAMILY_IPV6 = AF_INET6,
    FENCE_KDUMP_FAMILY_IPV4 = AF_INET,
};

#define FENCE_KDUMP_DEFAULT_IPPORT   7410
#define FENCE_KDUMP_DEFAULT_FAMILY   0
#define FENCE_KDUMP_DEFAULT_ACTION   0
#define FENCE_KDUMP_DEFAULT_COUNT    0
#define FENCE_KDUMP_DEFAULT_INTERVAL 10
#define FENCE_KDUMP_DEFAULT_TIMEOUT  60
#define FENCE_KDUMP_DEFAULT_VERBOSE  0

typedef struct fence_kdump_opts {
    char *nodename;
    int ipport;
    int family;
    int action;
    int count;
    int interval;
    int timeout;
    int verbose;
    struct list_head nodes;
} fence_kdump_opts_t;

typedef struct fence_kdump_node {
    char name[FENCE_KDUMP_NAME_LEN];
    char addr[FENCE_KDUMP_ADDR_LEN];
    char port[FENCE_KDUMP_PORT_LEN];
    int socket;
    struct addrinfo *info;
    struct list_head list;
} fence_kdump_node_t;

static inline void
init_node (fence_kdump_node_t *node)
{
    node->info = NULL;
}

static inline void
free_node (fence_kdump_node_t *node)
{
    freeaddrinfo (node->info);
    free (node);
}

static inline void
print_node (const fence_kdump_node_t *node)
{
    fprintf (stdout, "[debug]: node {       \n");
    fprintf (stdout, "[debug]:     name = %s\n", node->name);
    fprintf (stdout, "[debug]:     addr = %s\n", node->addr);
    fprintf (stdout, "[debug]:     port = %s\n", node->port);
    fprintf (stdout, "[debug]:     info = %p\n", node->info);
    fprintf (stdout, "[debug]: }            \n");
}

static inline void
init_options (fence_kdump_opts_t *opts)
{
    opts->nodename = NULL;
    opts->ipport   = FENCE_KDUMP_DEFAULT_IPPORT;
    opts->family   = FENCE_KDUMP_DEFAULT_FAMILY;
    opts->action   = FENCE_KDUMP_DEFAULT_ACTION;
    opts->count    = FENCE_KDUMP_DEFAULT_COUNT;
    opts->interval = FENCE_KDUMP_DEFAULT_INTERVAL;
    opts->timeout  = FENCE_KDUMP_DEFAULT_TIMEOUT;
    opts->verbose  = FENCE_KDUMP_DEFAULT_VERBOSE;

    INIT_LIST_HEAD (&opts->nodes);
}

static inline void
free_options (fence_kdump_opts_t *opts)
{
    fence_kdump_node_t *node;
    fence_kdump_node_t *safe;

    list_for_each_entry_safe (node, safe, &opts->nodes, list) {
        list_del (&node->list);
        free_node (node);
    }

    free (opts->nodename);
}

static inline void
print_options (fence_kdump_opts_t *opts)
{
    fence_kdump_node_t *node;

    fprintf (stdout, "[debug]: options {        \n");
    fprintf (stdout, "[debug]:     nodename = %s\n", opts->nodename);
    fprintf (stdout, "[debug]:     ipport   = %d\n", opts->ipport);
    fprintf (stdout, "[debug]:     family   = %d\n", opts->family);
    fprintf (stdout, "[debug]:     count    = %d\n", opts->count);
    fprintf (stdout, "[debug]:     interval = %d\n", opts->interval);
    fprintf (stdout, "[debug]:     timeout  = %d\n", opts->timeout);
    fprintf (stdout, "[debug]:     verbose  = %d\n", opts->verbose);
    fprintf (stdout, "[debug]: }                \n");

    list_for_each_entry (node, &opts->nodes, list) {
        print_node (node);
    }
}

static inline void
set_option_nodename (fence_kdump_opts_t *opts, const char *arg)
{
    if (opts->nodename != NULL) {
        free (opts->nodename);
    }

    opts->nodename = strdup (arg);
}

static inline void
set_option_ipport (fence_kdump_opts_t *opts, const char *arg)
{
    opts->ipport = atoi (arg);

    if ((opts->ipport < 1) || (opts->ipport > 65535)) {
        fprintf (stderr, "[error]: invalid ipport '%s'\n", arg);
        exit (1);
    }
}

static inline void
set_option_family (fence_kdump_opts_t *opts, const char *arg)
{
    if (!strcasecmp (arg, "auto")) {
        opts->family = FENCE_KDUMP_FAMILY_AUTO;
    } else if (!strcasecmp (arg, "ipv6")) {
        opts->family = FENCE_KDUMP_FAMILY_IPV6;
    } else if (!strcasecmp (arg, "ipv4")) {
        opts->family = FENCE_KDUMP_FAMILY_IPV4;
    } else {
        fprintf (stderr, "[error]: unsupported family '%s'\n", arg);
        exit (1);
    }
}

static inline void
set_option_action (fence_kdump_opts_t *opts, const char *arg)
{
    if (!strcasecmp (arg, "off")) {
        opts->action = FENCE_KDUMP_ACTION_OFF;
    } else if (!strcasecmp (arg, "metadata")) {
        opts->action = FENCE_KDUMP_ACTION_METADATA;
    } else if (!strcasecmp (arg, "monitor")) {
        opts->action = FENCE_KDUMP_ACTION_MONITOR;
    } else {
        fprintf (stderr, "[error]: unsupported action '%s'\n", arg);
        exit (1);
    }
}

static inline void
set_option_count (fence_kdump_opts_t *opts, const char *arg)
{
    opts->count = atoi (arg);

    if (opts->count < 0) {
        fprintf (stderr, "[error]: invalid count '%s'\n", arg);
        exit (1);
    }
}

static inline void
set_option_interval (fence_kdump_opts_t *opts, const char *arg)
{
    opts->interval = atoi (arg);

    if (opts->interval < 1) {
        fprintf (stderr, "[error]: invalid interval '%s'\n", arg);
        exit (1);
    }
}

static inline void
set_option_timeout (fence_kdump_opts_t *opts, const char *arg)
{
    opts->timeout = atoi (arg);

    if (opts->timeout < 1) {
        fprintf (stderr, "[error]: invalid timeout '%s'\n", arg);
        exit (1);
    }
}

static inline void
set_option_verbose (fence_kdump_opts_t *opts, const char *arg)
{
    if (arg != NULL) {
        opts->verbose = atoi (arg);
    } else {
        opts->verbose += 1;
    }
}

#endif /* _FENCE_KDUMP_OPTIONS_H */
