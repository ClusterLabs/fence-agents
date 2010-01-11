// #include <config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>

#include <sys/types.h>
#include <sys/poll.h>
#include <libvirt/libvirt.h>

#include <libxml/xmlreader.h>

#define DEBUG0(fmt) printf("%s:%d :: " fmt "\n", \
        __func__, __LINE__)
#define DEBUG(fmt, ...) printf("%s:%d: " fmt "\n", \
        __func__, __LINE__, __VA_ARGS__)
#define STREQ(a,b) (strcmp((a),(b)) == 0)

/* handle globals */
int h_fd = 0;
virEventHandleType h_event = 0;
virEventHandleCallback h_cb = NULL;
virFreeCallback h_ff = NULL;
void *h_opaque = NULL;

/* timeout globals */
#define TIMEOUT_MS 1000
int t_active = 0;
int t_timeout = -1;
int dom_active = 0;
virEventTimeoutCallback t_cb = NULL;
virFreeCallback t_ff = NULL;
void *t_opaque = NULL;

virDomainPtr mojaDomain = NULL;


/* Prototypes */
const char *eventToString(int event);
int myDomainEventCallback1 (virConnectPtr conn, virDomainPtr dom,
                            int event, int detail, void *opaque);
int myEventAddHandleFunc  (int fd, int event,
                           virEventHandleCallback cb,
                           void *opaque,
                           virFreeCallback ff);
void myEventUpdateHandleFunc(int watch, int event);
int  myEventRemoveHandleFunc(int watch);

int myEventAddTimeoutFunc(int timeout,
                          virEventTimeoutCallback cb,
                          void *opaque,
                          virFreeCallback ff);
void myEventUpdateTimeoutFunc(int timer, int timout);
int myEventRemoveTimeoutFunc(int timer);

int myEventHandleTypeToPollEvent(virEventHandleType events);
virEventHandleType myPollEventToEventHandleType(int events);

void usage(const char *pname);

int myDomainEventCallback1 (virConnectPtr conn,
                            virDomainPtr dom,
                            int event,
                            int detail,
                            void *opaque)
{
    if (event == VIR_DOMAIN_EVENT_STARTED) {
        virDomainRef(dom);
        mojaDomain = dom;

        dom_active = 1;
         }

    return 0;
}

static void myFreeFunc(void *opaque)
{
    char *str = opaque;
    printf("%s: Freeing [%s]\n", __func__, str);
    free(str);
}


/* EventImpl Functions */
int myEventHandleTypeToPollEvent(virEventHandleType events)
{
    int ret = 0;
    if(events & VIR_EVENT_HANDLE_READABLE)
        ret |= POLLIN;
    if(events & VIR_EVENT_HANDLE_WRITABLE)
        ret |= POLLOUT;
    if(events & VIR_EVENT_HANDLE_ERROR)
        ret |= POLLERR;
    if(events & VIR_EVENT_HANDLE_HANGUP)
        ret |= POLLHUP;
    return ret;
}

virEventHandleType myPollEventToEventHandleType(int events)
{
    virEventHandleType ret = 0;
    if(events & POLLIN)
        ret |= VIR_EVENT_HANDLE_READABLE;
    if(events & POLLOUT)
        ret |= VIR_EVENT_HANDLE_WRITABLE;
    if(events & POLLERR)
        ret |= VIR_EVENT_HANDLE_ERROR;
    if(events & POLLHUP)
        ret |= VIR_EVENT_HANDLE_HANGUP;
        
        
    return ret;
}

int  myEventAddHandleFunc(int fd, int event,
                          virEventHandleCallback cb,
                          void *opaque,
                          virFreeCallback ff)
{
    DEBUG("Add handle %d %d %p %p", fd, event, cb, opaque);
    h_fd = fd;
    h_event = myEventHandleTypeToPollEvent(event);
    h_cb = cb;
    h_ff = ff;
    h_opaque = opaque;
    return 0;
}

void myEventUpdateHandleFunc(int fd, int event)
{
    DEBUG("Updated Handle %d %d", fd, event);
    h_event = myEventHandleTypeToPollEvent(event);
    return;
}

int  myEventRemoveHandleFunc(int fd)
{
    DEBUG("Removed Handle %d", fd);
    h_fd = 0;
    if (h_ff)
       (h_ff)(h_opaque);
    return 0;
}

int myEventAddTimeoutFunc(int timeout,
                          virEventTimeoutCallback cb,
                          void *opaque,
                          virFreeCallback ff)
{
    DEBUG("Adding Timeout %d %p %p", timeout, cb, opaque);
    t_active = 1;
    t_timeout = timeout;
    t_cb = cb;
    t_ff = ff;
    t_opaque = opaque;
    return 0;
}

void myEventUpdateTimeoutFunc(int timer, int timeout)
{
    /*DEBUG("Timeout updated %d %d", timer, timeout);*/
    t_timeout = timeout;
}

int myEventRemoveTimeoutFunc(int timer)
{
   DEBUG("Timeout removed %d", timer);
   t_active = 0;
   if (t_ff)
       (t_ff)(t_opaque);
   return 0;
}

/* main test functions */

void usage(const char *pname)
{
    printf("%s uri\n", pname);
}

int run = 1;

static void stop(int sig)
{
    printf("Exiting on signal %d\n", sig);
    run = 0;
}


int main(int argc, char **argv)
{
    int sts;
    int callback1ret = -1;
    int callback2ret = -1;
    struct sigaction action_stop = {
        .sa_handler = stop
    };

    if(argc > 1 && STREQ(argv[1],"--help")) {
        usage(argv[0]);
        return -1;
    }

    virEventRegisterImpl( myEventAddHandleFunc,
                          myEventUpdateHandleFunc,
                          myEventRemoveHandleFunc,
                          myEventAddTimeoutFunc,
                          myEventUpdateTimeoutFunc,
                          myEventRemoveTimeoutFunc);

    virConnectPtr dconn = NULL;
    dconn = virConnectOpen (argv[1] ? argv[1] : NULL);
    if (!dconn) {
        printf("error opening\n");
        return -1;
    }

    sigaction(SIGTERM, &action_stop, NULL);
    sigaction(SIGINT, &action_stop, NULL);

    DEBUG0("Registering domain event cbs");

    /* Add 2 callbacks to prove this works with more than just one */
    callback1ret = virConnectDomainEventRegister(dconn, myDomainEventCallback1,
                                                 strdup("callback 1"), myFreeFunc);

    if ((callback1ret == 0)) {
        while(run) {
            struct pollfd pfd = { .fd = h_fd,
                              .events = h_event,
                              .revents = 0};

            sts = poll(&pfd, 1, TIMEOUT_MS);

            if (mojaDomain && dom_active) {
                printf("NAME: %s\n", virDomainGetName(mojaDomain));
                dom_active = 0;
                
                printf("%s\n", virDomainGetXMLDesc(mojaDomain, 0));
                char *xml = virDomainGetXMLDesc(mojaDomain, 0);
                
                // @todo: free mojaDomain	

                // parseXML output
                xmlDocPtr doc;
                xmlNodePtr cur;

                doc = xmlParseMemory(xml, strlen(xml));
                cur = xmlDocGetRootElement(doc);
                
                if (cur == NULL) {
                    fprintf(stderr, "Empty doc\n");
                    xmlFreeDoc(doc);
                    return 1;
                }
                
                if (!xmlStrcmp(cur->name, (const xmlChar *) "domain")) {
                    xmlNodePtr devices = cur->xmlChildrenNode;

                    while (devices != NULL) {
                        if (!xmlStrcmp(devices->name, (const xmlChar *) "devices")) {
                            xmlNodePtr child = devices->xmlChildrenNode;
                            while (child != NULL) {
                                if (!xmlStrcmp(child->name, (const xmlChar *) "serial")) {
                                    xmlAttrPtr attr = xmlHasProp(child, "type");

				    if (attr == NULL) continue;                                    

                                    if (!xmlStrcmp(attr->children->content, (const xmlChar *) "unix")) {
                                    	xmlNodePtr serial = child->xmlChildrenNode;
					while (serial != NULL) {
						if (!xmlStrcmp(serial->name, (const xmlChar *) "source")) {
							xmlAttrPtr attr_mode = xmlHasProp(serial, "mode");
							xmlAttrPtr attr_path = xmlHasProp(serial, "path");

							if ((attr_path != NULL) && (attr_mode != NULL) && (!xmlStrcmp(attr_mode->children->content, (const xmlChar *) "bind"))) {
								printf(">> IFILE >> %s\n", attr_path->children->content);
                                                        }
						}
						
						serial = serial->next;
					}
                                    }                                    
                                }
                                child = child->next;
                            }
                        }
                        devices = devices->next;
                    } 


                    xmlFreeDoc(doc);
                    return;
                }
                                                            
            }

            /* We are assuming timeout of 0 here - so execute every time */
            if(t_cb && t_active) {
                t_cb(t_timeout,t_opaque);
            }

            if (sts == 0) {
                /* DEBUG0("Poll timeout"); */
                continue;
            }
            if (sts < 0 ) {
                DEBUG0("Poll failed");
                continue;
            }
            if ( pfd.revents & POLLHUP ) {
                DEBUG0("Reset by peer");
                return -1;
            }


            if(h_cb) {
                h_cb(0,
                     h_fd,
                     myPollEventToEventHandleType(pfd.revents & h_event),
                     h_opaque);
            }


        }

        DEBUG0("Deregistering event handlers");
        virConnectDomainEventDeregister(dconn, myDomainEventCallback1);

    }

    DEBUG0("Closing connection");
    if( dconn && virConnectClose(dconn)<0 ) {
        printf("error closing\n");
    }

    printf("done\n");
    return 0;
}
