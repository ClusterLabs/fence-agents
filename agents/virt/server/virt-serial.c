// #include <config.h>

#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <errno.h>
#include <pthread.h>
#include <unistd.h>
#include <fcntl.h>

#include <sys/types.h>
#include <sys/poll.h>
#include <libvirt/libvirt.h>

#include <libxml/xmlreader.h>

#include "simpleconfig.h"
#include "debug.h"

#define DEBUG0(fmt) dbg_printf(5,"%s:%d :: " fmt "\n", \
        __func__, __LINE__)
#define DEBUG1(fmt, ...) dbg_printf(5, "%s:%d: " fmt "\n", \
        __func__, __LINE__, __VA_ARGS__)

#if LIBXML_VERSION >= 21400
#if __GNUC__ * 100 + __GNUC_MINOR__ >= 207
#define ATTRIBUTE_UNUSED __attribute__((unused))
#else
#define ATTRIBUTE_UNUSED
#endif
#endif

#include "serial.h"

#define STREQ(a,b) (strcmp((a),(b)) == 0)

static pthread_t event_tid = 0;
static int run = 0;

/* Prototypes */
const char *eventToString(int event);
int myDomainEventCallback1(virConnectPtr conn, virDomainPtr dom,
			   int event, int detail, void *opaque);

void usage(const char *pname);

struct domain_info {
	virDomainPtr dom;
	virDomainEventType event;
};

static int
is_in_directory(const char *dir, const char *pathspec)
{
	const char *last_slash = NULL;
	size_t dirlen, pathlen;

	if (!dir || !pathspec)
		return 0;

	dirlen = strlen(dir);
	pathlen = strlen(pathspec);

	/*
	printf("dirlen = %d pathlen = %d\n",
		dirlen, pathlen);
	 */

	/* chop off trailing slashes */
	while (dirlen && dir[dirlen-1]=='/')
		--dirlen;

	/* chop off leading slashes */
	while (dirlen && dir[0] == '/') {
		++dir;
		--dirlen;
	}

	/* chop off leading slashes */
	while (pathlen && pathspec[0] == '/') {
		++pathspec;
		--pathlen;
	}

	if (!dirlen || !pathlen)
		return 0;

	if (pathlen <= dirlen)
		return 0;

	last_slash = strrchr(pathspec, '/');

	if (!last_slash)
		return 0;

	while (*last_slash == '/' && last_slash > pathspec)
		--last_slash;

	if (last_slash == pathspec)
		return 0;

	pathlen = last_slash - pathspec + 1;
	/*printf("real dirlen = %d  real pathlen = %d\n",
	dirlen, pathlen);*/
	if (pathlen != dirlen)
		return 0;

	/* todo - intelligently skip multiple slashes mid-path */
	return !strncmp(dir, pathspec, dirlen);
}


static int
domainStarted(virDomainPtr mojaDomain, const char *path, int mode)
{
	char dom_uuid[42];
	char *xml;
	xmlDocPtr doc;
	xmlNodePtr cur, devices, child, serial;
	xmlAttrPtr attr, attr_mode, attr_path;

	if (!mojaDomain)
		return -1;

	virDomainGetUUIDString(mojaDomain, dom_uuid);

	xml = virDomainGetXMLDesc(mojaDomain, 0);
	// printf("%s\n", xml);
	// @todo: free mojaDomain       

	// parseXML output
	doc = xmlParseMemory(xml, strlen(xml));
	xmlFree(xml);
	cur = xmlDocGetRootElement(doc);

	if (cur == NULL) {
		fprintf(stderr, "Empty doc\n");
		xmlFreeDoc(doc);
		return -1;
	}

	if (xmlStrcmp(cur->name, (const xmlChar *) "domain")) {
		fprintf(stderr, "no domain?\n");
		xmlFreeDoc(doc);
		return -1;
	}

	devices = cur->xmlChildrenNode;
	for (devices = cur->xmlChildrenNode; devices != NULL;
	     devices = devices->next) {
		if (xmlStrcmp(devices->name, (const xmlChar *) "devices")) {
			continue;
		}

		for (child = devices->xmlChildrenNode; child != NULL;
		     child = child->next) {
			
			if ((!mode && xmlStrcmp(child->name, (const xmlChar *) "serial")) ||
			    (mode && xmlStrcmp(child->name, (const xmlChar *) "channel"))) {
				continue;
			}

			attr = xmlHasProp(child, (const xmlChar *)"type");
			if (attr == NULL)
				continue;

			if (xmlStrcmp(attr->children->content,
				      (const xmlChar *) "unix")) {
				continue;
			}

			for (serial = child->xmlChildrenNode; serial != NULL;
			     serial = serial->next) {
				if (xmlStrcmp(serial->name,
					      (const xmlChar *) "source")) {
					continue;
				}

				attr_mode = xmlHasProp(serial, (const xmlChar *)"mode");
				attr_path = xmlHasProp(serial, (const xmlChar *)"path");

				if (!attr_path || !attr_mode)
					continue;

				if (xmlStrcmp(attr_mode->children->content,
					      (const xmlChar *) "bind"))
					continue;

				if (path && !is_in_directory(path, (const char *)
							attr_path->children->content))
					continue;

				domain_sock_setup(dom_uuid, (const char *)
						  attr_path->children->content);
			}
		}
	}

	xmlFreeDoc(doc);
	return 0;
}

static int
registerExisting(virConnectPtr vp, const char *path, int mode)
{
	int *d_ids = NULL;
	int d_count, x;
	virDomainPtr dom;
	virDomainInfo d_info;

	errno = EINVAL;
	if (!vp)
		return -1;

	d_count = virConnectNumOfDomains(vp);
	if (d_count <= 0) {
		if (d_count == 0) {
			/* Successful, but no domains running */
			errno = 0;
			return 0;
		}
		goto out_fail;
	}

	d_ids = malloc(sizeof (int) * d_count);
	if (!d_ids)
		goto out_fail;

	if (virConnectListDomains(vp, d_ids, d_count) < 0)
		goto out_fail;

	/* Ok, we have the domain IDs - let's get their names and states */
	for (x = 0; x < d_count; x++) {
		dom = virDomainLookupByID(vp, d_ids[x]);
		if (!dom) {
			/* XXX doom */
			goto out_fail;
		}

		if (virDomainGetInfo(dom, &d_info) < 0) {
			/* XXX no info for the domain?!! */
			virDomainFree(dom);
			goto out_fail;
		}

		if (d_info.state != VIR_DOMAIN_SHUTOFF &&
		    d_info.state != VIR_DOMAIN_CRASHED)
			domainStarted(dom, path, mode);

		virDomainFree(dom);
	}

      out_fail:
	free(d_ids);
	return 0;
}

static int
domainStopped(virDomainPtr mojaDomain)
{
	char dom_uuid[42];

	if (!mojaDomain)
		return -1;

	virDomainGetUUIDString(mojaDomain, dom_uuid);
	domain_sock_close(dom_uuid);

	return 0;
}


struct event_args {
	char *uri;
	char *path;
	int mode;
	int wake_fd;
};

static void
connectClose(virConnectPtr conn ATTRIBUTE_UNUSED,
                         int reason,
                         void *opaque ATTRIBUTE_UNUSED)
{
	switch (reason) {
	case VIR_CONNECT_CLOSE_REASON_ERROR:
		dbg_printf(2, "Connection closed due to I/O error\n");
		break;
	case VIR_CONNECT_CLOSE_REASON_EOF:
		dbg_printf(2, "Connection closed due to end of file\n");
		break;
	case VIR_CONNECT_CLOSE_REASON_KEEPALIVE:
		dbg_printf(2, "Connection closed due to keepalive timeout\n");
		break;
	case VIR_CONNECT_CLOSE_REASON_CLIENT:
		dbg_printf(2, "Connection closed due to client request\n");
		break;
	default:
		dbg_printf(2, "Connection closed due to unknown reason\n");
		break;
	};
	run = 0;
}

int
myDomainEventCallback1(virConnectPtr conn,
		       virDomainPtr dom, int event, int detail, void *opaque)
{
	struct event_args *args = (struct event_args *)opaque;

	if (event == VIR_DOMAIN_EVENT_STARTED ||
	    event == VIR_DOMAIN_EVENT_STOPPED) {
		virDomainRef(dom);
		if (event == VIR_DOMAIN_EVENT_STARTED) {
			domainStarted(dom, args->path, args->mode);
			virDomainFree(dom);
			if (write(args->wake_fd, "x", 1) != 1) {
				dbg_printf(3, "Unable to wake up thread\n");
			}
		} else if (event == VIR_DOMAIN_EVENT_STOPPED) {
			domainStopped(dom);
			virDomainFree(dom);
		}
	}

	return 0;
}


static void *
event_thread(void *arg)
{
	struct event_args *args = (struct event_args *)arg;
	virConnectPtr dconn = NULL;
	int callback1ret = -1;

	dbg_printf(3, "Libvirt event listener starting\n");
	if (args->uri)
		dbg_printf(3," * URI: %s\n", args->uri);
	if (args->path)
		dbg_printf(3," * Socket path: %s\n", args->path);
	dbg_printf(3," * Mode: %s\n", args->mode ? "VMChannel" : "Serial");

	if (virEventRegisterDefaultImpl() < 0) {
		dbg_printf(1, "Failed to register default event impl\n");
		goto out;
	}

	dconn = virConnectOpen(args->uri);
	if (!dconn) {
		dbg_printf(1, "Error connecting to libvirt\n");
		goto out;
	}

	virConnectRegisterCloseCallback(dconn, connectClose, NULL, NULL);

	DEBUG0("Registering domain event cbs");

	registerExisting(dconn, args->path, args->mode);

	callback1ret =
	    virConnectDomainEventRegister(dconn, myDomainEventCallback1, arg, NULL);

	if (callback1ret != -1) {
		if (virConnectSetKeepAlive(dconn, 5, 5) < 0) {
			dbg_printf(1, "Failed to start keepalive protocol\n");
			run = 0;
		}
		while (run) {
			if (virEventRunDefaultImpl() < 0) {
				dbg_printf(1, "RunDefaultImpl Failed\n");
			}
		}

		DEBUG0("Deregistering event handlers");
		virConnectDomainEventDeregister(dconn, myDomainEventCallback1);
	}

	DEBUG0("Closing connection");
	if (dconn && virConnectClose(dconn) < 0) {
		dbg_printf(1, "error closing libvirt connection\n");
	}

out:
	free(args->uri);
	free(args->path);
	free(args);
	return NULL;
}


int
start_event_listener(const char *uri, const char *path, int mode, int *wake_fd)
{
	struct event_args *args = NULL;
	int wake_pipe[2];

	virInitialize();

	args = malloc(sizeof(*args));
	if (!args)
		return -1;
	memset(args, 0, sizeof(*args));
       
	if (pipe2(wake_pipe, O_CLOEXEC) < 0) {
		goto out_fail;
	}

	if (uri) {
	       args->uri = strdup(uri);
	       if (args->uri == NULL)
		       goto out_fail;
	}

	if (path) {
	       args->path = strdup(path);
	       if (args->path == NULL)
		       goto out_fail;
	}

	args->mode = mode;
	//args->p_tid = pthread_self();
	*wake_fd = wake_pipe[0];
	args->wake_fd = wake_pipe[1];

	run = 1;

	return pthread_create(&event_tid, NULL, event_thread, args);

out_fail:
	free(args->uri);
	free(args->path);
	free(args);
	return -1;
}


int
stop_event_listener(void)
{
	run = 0;
	//pthread_cancel(event_tid);
	pthread_join(event_tid, NULL);
	event_tid = 0;

	return 0;
}


