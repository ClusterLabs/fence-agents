// #include <config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <errno.h>
#include <pthread.h>

#include <sys/types.h>
#include <sys/poll.h>
#include <libvirt/libvirt.h>

#include <libxml/xmlreader.h>

#include "debug.h"

#define DEBUG0(fmt) dbg_printf(5,"%s:%d :: " fmt "\n", \
        __func__, __LINE__)
#define DEBUG1(fmt, ...) dbg_printf(5, "%s:%d: " fmt "\n", \
        __func__, __LINE__, __VA_ARGS__)

#include "virt-sockets.h"

#define STREQ(a,b) (strcmp((a),(b)) == 0)

/* handle globals */
static int h_fd = -1;
static virEventHandleType h_event = 0;
static virEventHandleCallback h_cb = NULL;
static virFreeCallback h_ff = NULL;
static void *h_opaque = NULL;

/* timeout globals */
#define TIMEOUT_MS 1000
static int t_active = 0;
static int t_timeout = -1;
static virEventTimeoutCallback t_cb = NULL;
static virFreeCallback t_ff = NULL;
static void *t_opaque = NULL;
static pthread_t event_tid = 0;
static int run = 0;

/* Prototypes */
const char *eventToString(int event);
int myDomainEventCallback1(virConnectPtr conn, virDomainPtr dom,
			   int event, int detail, void *opaque);
int myEventAddHandleFunc(int fd, int event,
			 virEventHandleCallback cb,
			 void *opaque, virFreeCallback ff);
void myEventUpdateHandleFunc(int watch, int event);
int myEventRemoveHandleFunc(int watch);

int myEventAddTimeoutFunc(int timeout,
			  virEventTimeoutCallback cb,
			  void *opaque, virFreeCallback ff);
void myEventUpdateTimeoutFunc(int timer, int timout);
int myEventRemoveTimeoutFunc(int timer);

int myEventHandleTypeToPollEvent(virEventHandleType events);
virEventHandleType myPollEventToEventHandleType(int events);

void usage(const char *pname);

struct domain_info {
	virDomainPtr dom;
	virDomainEventType event;
};


int
myDomainEventCallback1(virConnectPtr conn,
		       virDomainPtr dom, int event, int detail, void *opaque)
{
	struct domain_info *dinfo = (struct domain_info *) opaque;

	if (event == VIR_DOMAIN_EVENT_STARTED ||
	    event == VIR_DOMAIN_EVENT_STOPPED) {
		virDomainRef(dom);
		dinfo->dom = dom;
		dinfo->event = event;
	} else {
		dinfo->event = VIR_DOMAIN_EVENT_UNDEFINED;
	}

	return 0;
}


/* EventImpl Functions */
int
myEventHandleTypeToPollEvent(virEventHandleType events)
{
	int ret = 0;
	if (events & VIR_EVENT_HANDLE_READABLE)
		ret |= POLLIN;
	if (events & VIR_EVENT_HANDLE_WRITABLE)
		ret |= POLLOUT;
	if (events & VIR_EVENT_HANDLE_ERROR)
		ret |= POLLERR;
	if (events & VIR_EVENT_HANDLE_HANGUP)
		ret |= POLLHUP;
	return ret;
}

virEventHandleType
myPollEventToEventHandleType(int events)
{
	virEventHandleType ret = 0;
	if (events & POLLIN)
		ret |= VIR_EVENT_HANDLE_READABLE;
	if (events & POLLOUT)
		ret |= VIR_EVENT_HANDLE_WRITABLE;
	if (events & POLLERR)
		ret |= VIR_EVENT_HANDLE_ERROR;
	if (events & POLLHUP)
		ret |= VIR_EVENT_HANDLE_HANGUP;

	return ret;
}

int
myEventAddHandleFunc(int fd, int event,
		     virEventHandleCallback cb,
		     void *opaque, virFreeCallback ff)
{
	DEBUG1("Add handle %d %d %p %p %p", fd, event, cb, opaque, ff);
	h_fd = fd;
	h_event = myEventHandleTypeToPollEvent(event);
	h_cb = cb;
	h_opaque = opaque;
	h_ff = ff;
	return 0;
}

void
myEventUpdateHandleFunc(int fd, int event)
{
	DEBUG1("Updated Handle %d %d", fd, event);
	h_event = myEventHandleTypeToPollEvent(event);
	return;
}

int
myEventRemoveHandleFunc(int fd)
{
	DEBUG1("Removed Handle %d", fd);
	h_fd = 0;
	if (h_ff)
		(h_ff) (h_opaque);
	return 0;
}

int
myEventAddTimeoutFunc(int timeout,
		      virEventTimeoutCallback cb,
		      void *opaque, virFreeCallback ff)
{
	DEBUG1("Adding Timeout %d %p %p", timeout, cb, opaque);
	t_active = 1;
	t_timeout = timeout;
	t_cb = cb;
	t_ff = ff;
	t_opaque = opaque;
	return 0;
}

void
myEventUpdateTimeoutFunc(int timer, int timeout)
{
	/*DEBUG1("Timeout updated %d %d", timer, timeout); */
	t_timeout = timeout;
}

int
myEventRemoveTimeoutFunc(int timer)
{
	DEBUG1("Timeout removed %d", timer);
	t_active = 0;
	if (t_ff)
		(t_ff) (t_opaque);
	return 0;
}


static int
domainStarted(virDomainPtr mojaDomain)
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
			if (xmlStrcmp(child->name, (const xmlChar *) "serial")) {
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

				if ((attr_path != NULL) &&
				    (attr_mode != NULL) &&
				    (!xmlStrcmp(attr_mode->children->content,
						(const xmlChar *) "bind"))) {
					domain_sock_setup(dom_uuid, (const char *)
							  attr_path->children->content);
				}
			}
		}
	}

	xmlFreeDoc(doc);
	return 0;
}

static int
registerExisting(virConnectPtr vp)
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
			domainStarted(dom);

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


static void *
event_thread(void *arg)
{
	virConnectPtr dconn = NULL;
	struct domain_info dinfo;
	int sts;
	int callback1ret = -1;

	dbg_printf(3,"Event listener starting \n");

	virEventRegisterImpl(myEventAddHandleFunc,
			     myEventUpdateHandleFunc,
			     myEventRemoveHandleFunc,
			     myEventAddTimeoutFunc,
			     myEventUpdateTimeoutFunc,
			     myEventRemoveTimeoutFunc);

	dconn = virConnectOpen((char *)arg);
	if (!dconn) {
		dbg_printf(1, "Error connecting to libvirt\n");
		return NULL;
	}

	DEBUG0("Registering domain event cbs");

	registerExisting(dconn);

	/* Add 2 callbacks to prove this works with more than just one */
	memset(&dinfo, 0, sizeof (dinfo));
	dinfo.event = VIR_DOMAIN_EVENT_UNDEFINED;
	callback1ret =
	    virConnectDomainEventRegister(dconn, myDomainEventCallback1,
					  &dinfo, NULL);

	if ((callback1ret == 0)) {
		while (run) {
			struct pollfd pfd = {.fd = h_fd,
				.events = h_event,
				.revents = 0
			};

			sts = poll(&pfd, 1, TIMEOUT_MS);
			/* We are assuming timeout of 0 here - so execute every time */
			if (t_cb && t_active) {
				t_cb(t_timeout, t_opaque);
			}

			if (dinfo.event == VIR_DOMAIN_EVENT_STARTED) {
				domainStarted(dinfo.dom);
				virDomainFree(dinfo.dom);
				dinfo.dom = NULL;
				dinfo.event = VIR_DOMAIN_EVENT_UNDEFINED;
			} else if (dinfo.event == VIR_DOMAIN_EVENT_STOPPED) {
				domainStopped(dinfo.dom);
				virDomainFree(dinfo.dom);
				dinfo.dom = NULL;
				dinfo.event = VIR_DOMAIN_EVENT_UNDEFINED;
			}

			if (sts == 0) {
				/* DEBUG0("Poll timeout"); */
				continue;
			}

			if (sts < 0) {
				DEBUG0("Poll failed");
				continue;
			}

			if (pfd.revents & POLLHUP) {
				DEBUG0("Reset by peer");
				return NULL;
			}

			if (h_cb) {
				h_cb(0, h_fd,
				     myPollEventToEventHandleType(pfd.revents &
								  h_event),
				     h_opaque);
			}
		}

		DEBUG0("Deregistering event handlers");
		virConnectDomainEventDeregister(dconn, myDomainEventCallback1);
	}

	DEBUG0("Closing connection");
	if (dconn && virConnectClose(dconn) < 0) {
		dbg_printf(1, "error closing libvirt connection\n");
	}

	return NULL;
}


int
start_event_listener(const char *uri)
{
	char *arg = NULL;

	virInitialize();
       
	if (uri) {
	       arg = strdup(uri);
	       if (uri == NULL)
		       return -1;
	}

	run = 1;

	return pthread_create(&event_tid, NULL, event_thread, arg);
}


int
stop_event_listener(void)
{
	run = 0;
	pthread_cancel(event_tid);
	pthread_join(event_tid, NULL);
	event_tid = 0;

	return 0;
}


