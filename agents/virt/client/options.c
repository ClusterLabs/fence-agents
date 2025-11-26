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

#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/un.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/ioctl.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <netinet/in.h>
#include <netdb.h>
#include <sys/time.h>
#include <fcntl.h>
#include <errno.h>
#include <libgen.h>

/* Local includes */
#include "xvm.h"
#include "simple_auth.h"
#include "mcast.h"
#include "tcp_listener.h"
#include "options.h"

#define SCHEMA_COMPAT '\xfe'


/* Assignment functions */

static inline void
assign_debug(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (!value) {
		/* GNU getopt sets optarg to NULL for options w/o a param
		   We rely on this here... */
		args->debug++;
		return;
	}

	args->debug = atoi(value);
	if (args->debug < 0) {
		args->debug = 1;
	}
}


static inline void
assign_family(fence_virt_args_t *args, struct arg_info *arg,
	      char *value)
{
	if (!value)
		return;

	if (!strcasecmp(value, "ipv4")) {
		args->net.family = PF_INET;
	} else if (!strcasecmp(value, "ipv6")) {
		args->net.family = PF_INET6;
	} else if (!strcasecmp(value, "auto")) {
		args->net.family = 0;
	} else {
		fprintf(stderr, "Unsupported family: '%s'\n", value);
		args->flags |= F_ERR;
	}
}


static inline void
assign_address(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (!value)
		return;

	if (args->net.addr)
		free(args->net.addr);
	args->net.addr = strdup(value);
}

static inline void
assign_ip_address(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (!value)
		return;

	if (args->net.ipaddr)
		free(args->net.ipaddr);
	args->net.ipaddr = strdup(value);
}

static inline void
assign_channel_address(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (!value)
		return;

	if (args->serial.address)
		free(args->serial.address);
	args->serial.address = strdup(value);
}


static inline void
assign_port(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	char *p;
	int ret;

	if (!value)
		return;

	ret = strtol(value, &p, 0);
	if (ret <= 0 || ret >= 65536 || *p != '\0') {
		fprintf(stderr, "Invalid port: '%s'\n", value);
		args->flags |= F_ERR;
	} else
		args->net.port = ret;
}

static inline void
assign_cid(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	char *p;
	unsigned long ret;

	if (!value) {
		args->net.cid = 2;
		return;
	}

	ret = strtoul(value, &p, 0);
	if (!p || *p != '\0' || ret < 2 || ret >= 0xffffffff) {
		fprintf(stderr, "Invalid CID: '%s'\n", value);
		args->flags |= F_ERR;
	} else
		args->net.cid = ret;
}

static inline void
assign_interface(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	int ret;

	if (!value)
		return;

	ret = if_nametoindex(value);
	if (ret <= 0) {
		fprintf(stderr, "Invalid interface: %s: %s\n", value, strerror(errno));
		args->net.ifindex = 0;
	}

	args->net.ifindex = ret;
}


static inline void
assign_retrans(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	char *p;
	int ret;

	if (!value)
		return;

	ret = strtol(value, &p, 0);
	if (ret <= 0 || *p != '\0') {
		fprintf(stderr, "Invalid retransmit time: '%s'\n", value);
		args->flags |= F_ERR;
	} else
		args->retr_time = ret;
}

static inline void
assign_hash(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (!value)
		return;

	if (!strcasecmp(value, "none")) {
		args->net.hash = HASH_NONE;
	} else if (!strcasecmp(value, "sha1")) {
		args->net.hash = HASH_SHA1;
	} else if (!strcasecmp(value, "sha256")) {
		args->net.hash = HASH_SHA256;
	} else if (!strcasecmp(value, "sha512")) {
		args->net.hash = HASH_SHA512;
	} else {
		fprintf(stderr, "Unsupported hash: %s\n", value);
		args->flags |= F_ERR;
	}
}


static inline void
assign_auth(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (!value)
		return;

	if (!strcasecmp(value, "none")) {
		args->net.auth = AUTH_NONE;
	} else if (!strcasecmp(value, "sha1")) {
		args->net.auth = AUTH_SHA1;
	} else if (!strcasecmp(value, "sha256")) {
		args->net.auth = AUTH_SHA256;
	} else if (!strcasecmp(value, "sha512")) {
		args->net.auth = AUTH_SHA512;
	} else {
		fprintf(stderr, "Unsupported auth type: %s\n", value);
		args->flags |= F_ERR;
	}
}

static inline void
assign_key(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	struct stat st;

	if (!value)
		return;

	if (args->net.key_file)
		free(args->net.key_file);
	args->net.key_file = strdup(value);

	if (stat(value, &st) == -1) {
		fprintf(stderr, "Invalid key file: '%s' (%s)\n", value,
		       strerror(errno));
		args->flags |= F_ERR;
	}
}


static inline void
assign_op(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (!value)
		return;

	if (!strcasecmp(value, "null")) {
		args->op = FENCE_NULL;
	} else if (!strcasecmp(value, "on")) {
		args->op = FENCE_ON;
	} else if (!strcasecmp(value, "off")) {
		args->op = FENCE_OFF;
	} else if (!strcasecmp(value, "reboot")) {
		args->op = FENCE_REBOOT;
	} else if (!strcasecmp(value, "status")) {
		args->op = FENCE_STATUS;
	} else if (!strcasecmp(value, "monitor")) {
		args->op = FENCE_DEVSTATUS;
	} else if (!strcasecmp(value, "list") || !strcasecmp(value, "list-status")) {
		args->op = FENCE_HOSTLIST;
	} else if (!strcasecmp(value, "metadata")) {
		args->op = FENCE_METADATA;
	} else if (!strcasecmp(value, "validate-all")) {
		args->op = FENCE_VALIDATEALL;
	} else {
		fprintf(stderr, "Unsupported operation: %s\n", value);
		args->flags |= F_ERR;
	}
}


static inline void
assign_device(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (!value)
		return;

	args->serial.device = strdup(value);
}


static inline void
assign_params(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (!value)
		return;

	args->serial.speed = strdup(value);
}


static inline void
assign_domain(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (args->domain) {
		fprintf(stderr, "Domain/UUID may not be specified more than once\n");
		args->flags |= F_ERR;
		return;
	}

	if (!value)
		return;

	args->domain = strdup(value);

	if (strlen(value) <= 0) {
		fprintf(stderr, "Invalid domain name\n");
		args->flags |= F_ERR;
	}

	if (strlen(value) >= MAX_DOMAINNAME_LENGTH) {
		errno = ENAMETOOLONG;
		fprintf(stderr, "Invalid domain name: '%s' (%s)\n",
		       value, strerror(errno));
		args->flags |= F_ERR;
	}
}


static inline void
assign_uuid_lookup(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	if (!value) {
		/* GNU getopt sets optarg to NULL for options w/o a param
		   We rely on this here... */
		args->flags |= F_USE_UUID;
		return;
	}

	args->flags |= ( !!atoi(value) ? F_USE_UUID : 0);
}


static inline void
assign_timeout(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	char *p;
	int ret;

	if (!value)
		return;

	ret = strtol(value, &p, 0);
	if (ret <= 0 || *p != '\0') {
		fprintf(stderr, "Invalid timeout: '%s'\n", value);
		args->flags |= F_ERR;
	} else
		args->timeout = ret;
}

static inline void
assign_delay(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	char *p;
	int ret;

	if (!value)
		return;

	ret = strtol(value, &p, 0);
	if (ret < 0 || *p != '\0') {
		fprintf(stderr, "Invalid delay: '%s'\n", value);
		args->flags |= F_ERR;
	} else
		args->delay = ret;
}

static inline void
assign_help(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	args->flags |= F_HELP;
}


static inline void
assign_version(fence_virt_args_t *args, struct arg_info *arg, char *value)
{
	args->flags |= F_VERSION;
}


static void
print_desc_xml(const char *desc)
{
	const char *d;

	for (d = desc; *d; d++) {
		switch (*d) {
		case '<':
			printf("&lt;");
			break;
		case '>':
			printf("&gt;");
			break;
		default:
			printf("%c", *d);
		}
	}
}


/** ALL valid command line and stdin arguments for this fencing agent */
static struct arg_info _arg_info[] = {
	{ '\xff', NULL, "agent",
	  NULL, 0, 0, "string", NULL,
	  "Not user serviceable",
	  NULL },

	{ '\xff', NULL, "self",
	  NULL, 0, 0, "string", NULL,
	  "Not user serviceable",
	  NULL },

	{ '\xff', NULL, "nodename",
	  NULL, 0, 0, "string", NULL,
	  "Not user serviceable",
	  NULL },

	{ 'd', "-d", "debug",
	  NULL, 0, 0, "boolean", NULL,
	  "Specify (stdin) or increment (command line) debug level",
	  assign_debug },

	{ 'i', "-i <family>", "ip_family",
	  NULL, 0, 0, "string", "auto",
	  "IP Family ([auto], ipv4, ipv6)",
	  assign_family },

	{ 'a', "-a <address>", "multicast_address",
	  NULL, 0, 0, "string", NULL,
	  "Multicast address (default=" IPV4_MCAST_DEFAULT " / " IPV6_MCAST_DEFAULT ")",
	  assign_address },

	{ 'T', "-T <address>", "ipaddr",
          NULL, 0, 0, "string", "127.0.0.1",
	  "IP address to connect to in TCP mode (default=" IPV4_TCP_ADDR_DEFAULT " / " IPV6_TCP_ADDR_DEFAULT ")",
	  assign_ip_address },

	{ 'S', "-S <cid>", "vsock",
          NULL, 0, 0, "integer", "2",
	  "vm socket CID to connect to in vsock mode",
	  assign_cid },

	{ 'A', "-A <address>", "channel_address",
          NULL, 0, 0, "string", "10.0.2.179",
	  "VM Channel IP address (default=" DEFAULT_CHANNEL_IP ")",
	  assign_channel_address },

	{ 'p', "-p <port>", "ipport",
          NULL, 0, 0, "string", "1229",
	  "TCP, Multicast, VMChannel, or VM socket port (default=1229)",
	  assign_port },

	{ 'I', "-I <interface>", "interface",
	  NULL, 0, 0, "string", NULL,
	  "Network interface name to listen on",
	  assign_interface },

	{ 'r', "-r <retrans>", "retrans",
	  NULL, 0, 0, "string", "20",
	  "Multicast retransmit time (in 1/10sec; default=20)",
	  assign_retrans },

	{ 'c', "-c <hash>", "hash",
	  NULL, 0, 0, "string", "sha256",
	  "Packet hash strength (none, sha1, [sha256], sha512)",
	  assign_hash },

	{ 'C', "-C <auth>", "auth",
	  NULL, 0, 0, "string", "sha256",
	  "Authentication (none, sha1, [sha256], sha512)",
	  assign_auth },

	{ 'k', "-k <file>", "key_file",
	  NULL, 0, 0, "string", DEFAULT_KEY_FILE,
	  "Shared key file (default=" DEFAULT_KEY_FILE ")",
	  assign_key },

	{ 'D', "-D <device>", "serial_device",
	  NULL, 0, 0, "string", DEFAULT_SERIAL_DEVICE,
	  "Serial device (default=" DEFAULT_SERIAL_DEVICE  ")",
	  assign_device },

	{ 'P', "-P <param>", "serial_params",
	  NULL, 0, 0, "string", DEFAULT_SERIAL_SPEED,
	  "Serial Parameters (default=" DEFAULT_SERIAL_SPEED ")",
	  assign_params },

	{ '\xff', NULL, "option",
	  /* Deprecated */
	  NULL, 0, 0, "string", "reboot",
	  "Fencing option (null, off, on, [reboot], status, list, list-status, monitor, validate-all, metadata)",
	  assign_op },

	{ 'o', "-o <operation>", "action",
	  NULL, 0, 0, "string", "reboot",
	  "Fencing action (null, off, on, [reboot], status, list, list-status, monitor, validate-all, metadata)",
	  assign_op },

	{ 'n', "-n <domain>", "plug",
	  "port", 0, 0, "string", NULL,
	  "Virtual Machine (domain name) to fence",
	  assign_domain },

	{ 'H', "-H <domain>", "port",
	  NULL, 1, 0, "string", NULL,
	  "Virtual Machine (domain name) to fence",
	  assign_domain },

	{ SCHEMA_COMPAT, NULL, "domain",
	  NULL, 0, 0, "string", NULL,
	  "Virtual Machine (domain name) to fence (deprecated; use port)",
	  assign_domain },

	{ 'u', "-u", "use_uuid",
	  NULL, 0, 0, "string", "0",
	  "Treat [domain] as UUID instead of domain name. This is provided for compatibility with older fence_xvmd installations.",
	  assign_uuid_lookup },

	{ 't', "-t <timeout>", "timeout",
	  NULL, 0, 0, "string", "30",
	  "Fencing timeout (in seconds; default=30)",
	  assign_timeout },

	{ 'h', "-h", NULL,
	  NULL, 0, 0, "boolean", "0",
	  "Help",
	  assign_help },

	{ '?', "-?", NULL,
	  NULL, 0, 0, "boolean", "0",
	  "Help (alternate)",
	  assign_help },

	{ 'w', "-w <delay>", "delay",
	  NULL, 0, 0, "string", "0",
	  "Fencing delay (in seconds; default=0)",
	  assign_delay },

	{ 'V', "-V", NULL,
	  NULL, 0, 0, "boolean", "0",
	  "Display version and exit",
	  assign_version },

	/* Terminator */
	{ 0, NULL, NULL, NULL, 0, 0, NULL, NULL, NULL, NULL }
};


static struct arg_info *
find_arg_by_char(char arg)
{
	int x = 0;

	for (x = 0; _arg_info[x].opt != 0; x++) {
		if (_arg_info[x].opt == arg)
			return &_arg_info[x];
	}

	return NULL;
}


static struct arg_info *
find_arg_by_string(char *arg)
{
	int x = 0;

	for (x = 0; _arg_info[x].opt != 0; x++) {
		if (!_arg_info[x].stdin_opt)
			continue;
		if (!strcasecmp(_arg_info[x].stdin_opt, arg))
			return &_arg_info[x];
	}

	return NULL;
}


/* ============================================================= */

/**
  Initialize an args structure.

  @param args		Pointer to args structure to initialize.
 */
void
args_init(fence_virt_args_t *args)
{
	args->domain = NULL;
	//args->uri = NULL;
	args->op = FENCE_REBOOT;
	args->net.key_file = strdup(DEFAULT_KEY_FILE);
	args->net.hash = DEFAULT_HASH;
	args->net.auth = DEFAULT_AUTH;
	args->net.addr = NULL;
	args->net.ipaddr = NULL;
	args->net.cid = 0;
	args->net.port = DEFAULT_MCAST_PORT;
	args->net.ifindex = 0;
	args->net.family = 0;  /* auto */
	args->serial.device = NULL;
	args->serial.speed = strdup(DEFAULT_SERIAL_SPEED);
	args->serial.address = strdup(DEFAULT_CHANNEL_IP);
	args->timeout = 30;
	args->retr_time = 20;
	args->flags = 0;
	args->debug = 0;
	args->delay = 0;
}


#define _pr_int(piece) printf("  %s = %d\n", #piece, piece)
#define _pr_str(piece) printf("  %s = %s\n", #piece, piece)


/**
  Prints out the contents of an args structure for debugging.

  @param args		Pointer to args structure to print out.
 */
void
args_print(fence_virt_args_t *args)
{
	printf("-- args @ %p --\n", args);
	_pr_str(args->domain);
	_pr_int(args->op);
	_pr_int(args->mode);
	_pr_int(args->debug);
	_pr_int(args->timeout);
	_pr_int(args->delay);
	_pr_int(args->retr_time);
	_pr_int(args->flags);

	_pr_str(args->net.addr);
	_pr_str(args->net.ipaddr);
	_pr_int(args->net.cid);
	_pr_str(args->net.key_file);
	_pr_int(args->net.port);
	_pr_int(args->net.hash);
	_pr_int(args->net.auth);
	_pr_int(args->net.family);
	_pr_int(args->net.ifindex);

	_pr_str(args->serial.device);
	_pr_str(args->serial.speed);
	_pr_str(args->serial.address);
	printf("-- end args --\n");
}


/**
  Print out arguments and help information based on what is allowed in
  the getopt string optstr.

  @param progname	Program name.
  @param optstr		Getopt(3) style options string
  @param print_stdin	0 = print command line options + description,
			1 = print fence-style stdin args + description
 */
static char *
find_rev(const char *start, char *curr, char c)
{

	while (curr > start) {
		if (*curr == c)
			return curr;
		--curr;
	}

	return NULL;
}


static void
output_help_text(int arg_width, int help_width, const char *arg, const char *desc)
{
	char out_buf[4096];
	char *p, *start;
	const char *arg_print = arg;
	int len;

	memset(out_buf, 0, sizeof(out_buf));
	strncpy(out_buf, desc, sizeof(out_buf) - 1);
	start = out_buf;

	do {
		p = NULL;
		len = strlen(start);
		if (len > help_width) {
			p = start + help_width;
			p = find_rev(start, p, ' ');
			if (p) {
				*p = 0;
				p++;
			}
		}
		printf("  %*.*s  %*.*s\n",
		       -arg_width, arg_width,
		       arg_print,
		       -help_width, help_width,
		       start);
		if (!p)
			return;
		if (arg == arg_print)
			arg_print = " ";
		start = p;
	} while(1);
}


void
args_usage(char *progname, const char *optstr, int print_stdin)
{
	int x;
	struct arg_info *arg;

	if (!print_stdin) {
		if (progname) {
			printf("usage: %s [args]\n\nNOTE: reboot-action does not power on nodes that are powered off.\n\n", progname);
		} else {
			printf("usage: fence_virt [args]\n\nNOTE: reboot-action does not power on nodes that are powered off.\n\n");
		}
	}

	for (x = 0; x < strlen(optstr); x++) {
		arg = find_arg_by_char(optstr[x]);
		if (!arg || arg->deprecated)
			continue;

		if (print_stdin) {
			if (arg && arg->stdin_opt)
				output_help_text(20, 55, arg->stdin_opt, arg->desc);
		} else {
			output_help_text(20, 55, arg->opt_desc, arg->desc);
		}
	}

	printf("\n");
}


void
args_metadata(char *progname, const char *optstr)
{
	int x;
	struct arg_info *arg;

	printf("<?xml version=\"1.0\" ?>\n");
	printf("<resource-agent name=\"%s\" shortdesc=\"Fence agent for virtual machines\">\n", basename(progname));
	printf("<longdesc>%s is a Power Fencing agent which can be used with "
	       "virtual machines.\n\nNOTE: reboot-action does not power on nodes that are powered off."
	       "</longdesc>\n", basename(progname));
	printf("<vendor-url>https://libvirt.org</vendor-url>\n");
	printf("<parameters>\n");

	for (x = 0; x < strlen(optstr); x++) {
		arg = find_arg_by_char(optstr[x]);
		if (!arg)
			continue;
		if (!arg->stdin_opt)
			continue;

		if (arg->obsoletes)
			printf("\t<parameter name=\"%s\" unique=\"0\" required=\"%d\" obsoletes=\"%s\">\n", arg->stdin_opt, (!strcmp(arg->content_type, "boolean") || arg->default_value) ? 0 : 1, arg->obsoletes);
		else if (arg->deprecated)
			printf("\t<parameter name=\"%s\" unique=\"0\" required=\"%d\" deprecated=\"%d\">\n", arg->stdin_opt, (!strcmp(arg->content_type, "boolean") || arg->default_value) ? 0 : 1, arg->deprecated);
		else
			printf("\t<parameter name=\"%s\" unique=\"0\" required=\"%d\">\n", arg->stdin_opt, (!strcmp(arg->content_type, "boolean") || arg->default_value || !strcmp(arg->stdin_opt, "multicast_address")) ? 0 : 1);

                printf("\t\t<getopt mixed=\"-%c\" />\n",arg->opt);
                if (arg->default_value) {
                  printf("\t\t<content type=\"%s\" default=\"%s\" />\n", arg->content_type, arg->default_value);
                } else {
                  printf("\t\t<content type=\"%s\" />\n", arg->content_type);
                }
		printf("\t\t<shortdesc lang=\"en\">");
		print_desc_xml(arg->desc);
		printf("</shortdesc>\n");
		printf("\t</parameter>\n");
	}

	for (x = 0; _arg_info[x].opt != 0; x++) {
		if (_arg_info[x].opt != SCHEMA_COMPAT)
			continue;

		arg = &_arg_info[x];

		printf("\t<parameter name=\"%s\" unique=\"0\" required=\"%d\" deprecated=\"1\">\n", arg->stdin_opt,
			(!strcmp(arg->content_type, "boolean") || arg->default_value || !strcmp(arg->stdin_opt, "domain")) ? 0 : 1);
		printf("\t\t<getopt mixed=\"\" />\n");
                if (arg->default_value) {
                  printf("\t\t<content type=\"%s\" default=\"%s\" />\n", arg->content_type, arg->default_value);
                } else {
                  printf("\t\t<content type=\"%s\" />\n", arg->content_type);
                }
		printf("\t\t<shortdesc lang=\"en\">");
		print_desc_xml(arg->desc);
		printf("</shortdesc>\n");
		printf("\t</parameter>\n");
	}

	printf("</parameters>\n");
	printf("<actions>\n");
	printf("\t<action name=\"null\" />\n");
	printf("\t<action name=\"on\" />\n");
	printf("\t<action name=\"off\" />\n");
	printf("\t<action name=\"reboot\" />\n");
	printf("\t<action name=\"metadata\" />\n");
	printf("\t<action name=\"status\" />\n");
	printf("\t<action name=\"monitor\" />\n");
	printf("\t<action name=\"list\" />\n");
	printf("\t<action name=\"list-status\" />\n");
	printf("\t<action name=\"validate-all\" />\n");
	printf("</actions>\n");
	printf("</resource-agent>\n");
}


/**
  Remove leading and trailing whitespace from a line of text.

  @param line		Line to clean up
  @param linelen	Max size of line
  @return		0 on success, -1 on failure
 */
static int
cleanup(char *line, size_t linelen)
{
	char *p;
	int x;

	/* Remove leading whitespace. */
	p = line;
	for (x = 0; x < linelen; x++) {
		switch (line[x]) {
		case '\t':
		case ' ':
			break;
		case '\n':
		case '\r':
			return -1;
		default:
			goto eol;
		}
	}
eol:
	/* Move the remainder down by as many whitespace chars as we
	   chewed up */
	if (x)
		memmove(p, &line[x], linelen-x);

	/* Remove trailing whitespace. */
	for (x=0; x < linelen; x++) {
		switch(line[x]) {
		case '\t':
		case ' ':
		case '\r':
		case '\n':
			line[x] = 0;
		case 0:
		/* End of line */
			return 0;
		}
	}

	return -1;
}


/**
  Parse args from stdin and assign to the specified args structure.

  @param optstr		Command line option string in getopt(3) format
  @param args		Args structure to fill in.
 */
void
args_get_stdin(const char *optstr, fence_virt_args_t *args)
{
	char in[256];
	char *name, *val;
	struct arg_info *arg;

	while (fgets(in, sizeof(in), stdin)) {

		if (in[0] == '#')
			continue;

		if (cleanup(in, sizeof(in)) == -1)
			continue;

		name = in;
		if ((val = strchr(in, '='))) {
			*val = 0;
			++val;
		}

		arg = find_arg_by_string(name);
		if (!arg || (arg->opt != '\xff' &&
			     arg->opt != SCHEMA_COMPAT &&
			     !strchr(optstr, arg->opt))) {
			fprintf(stderr,
			        "Parse error: Ignoring unknown option '%s'\n",
			        name);
			continue;
		}

		if (arg->assign)
			arg->assign(args, arg, val);
	}
}


/**
  Parse args from stdin and assign to the specified args structure.

  @param optstr		Command line option string in getopt(3) format
  @param args		Args structure to fill in.
 */
void
args_get_getopt(int argc, char **argv, const char *optstr, fence_virt_args_t *args)
{
	int opt;
	struct arg_info *arg;

	while ((opt = getopt(argc, argv, optstr)) != EOF) {

		arg = find_arg_by_char(opt);

		if (!arg) {
			args->flags |= F_ERR;
			continue;
		}

		if (arg->assign)
			arg->assign(args, arg, optarg);
	}
}


void
args_finalize(fence_virt_args_t *args)
{
	char *addr = NULL;

	if (!args->net.addr) {
		switch(args->net.family) {
		case 0:
		case PF_INET:
			addr = (char *)IPV4_MCAST_DEFAULT;
			break;
		case PF_INET6:
			addr = (char *)IPV6_MCAST_DEFAULT;
			break;
		default:
			args->flags |= F_ERR;
		break;
		}
	}

	if (!args->net.addr)
		args->net.addr = addr;

	if (!args->net.addr) {
		fprintf(stderr, "No multicast address available\n");
		args->flags |= F_ERR;
	}

	if (!args->net.addr)
		return;
	if (args->net.family)
		return;

	/* Set family */
	if (strchr(args->net.addr, ':'))
		args->net.family = PF_INET6;
	if (strchr(args->net.addr, '.'))
		args->net.family = PF_INET;
	if (!args->net.family) {
		fprintf(stderr, "Could not determine address family\n");
		args->flags |= F_ERR;
	}
}
