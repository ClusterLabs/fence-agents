###############################################################################
###############################################################################
##
##  Copyright (C) 2009-2021 Red Hat, Inc.
##  
##  This copyrighted material is made available to anyone wishing to use,
##  modify, copy, or redistribute it subject to the terms and conditions
##  of the GNU General Public License v.2.
##
###############################################################################
###############################################################################

MAINTAINERCLEANFILES		= Makefile.in

noinst_HEADERS			= cpg.h serial.h uuid-test.h virt.h

sbin_PROGRAMS			= fence_virtd

#
# daemon
#
fence_virtd_SOURCES		= main.c plugin.c config.c static_map.c uuid-test.c \
				  daemon_init.c

fence_virtd_CFLAGS		= $(VIRT_AM_CFLAGS) \
				  $(nss_CFLAGS) $(xml2_CFLAGS) $(uuid_CFLAGS) $(PTHREAD_CFLAGS) \
				  $(AM_CFLAGS)

fence_virtd_LDADD		= $(VIRT_CONFIG_LIBS) $(VIRT_COMMON_LIBS) \
				  $(nss_LIBS) $(xml2_LIBS) $(uuid_LIBS) $(PTHREAD_LIBS) $(dl_LIBS)

fence_virtd_LDFLAGS		= $(VIRT_AM_LDFLAGS) $(VIRT_COMMON_LDFLAGS)

virt_la_SOURCES			= libvirt.c virt.c uuid-test.c
cpg_la_SOURCES			= cpg-virt.c cpg.c virt.c uuid-test.c
multicast_la_SOURCES		= mcast.c history.c
tcp_la_SOURCES			= tcp.c history.c
vsock_la_SOURCES		= vsock.c history.c
serial_la_SOURCES		= virt-serial.c virt-sockets.c serial.c history.c

fence_virtd_CFLAGS		+= -DMODULE_PATH=\"$(libdir)/fence-virt/\"

fvlibdir			= $(libdir)/fence-virt

fvlib_LTLIBRARIES		=

MODULESCFLAGS			= $(VIRT_AM_CFLAGS) $(AM_CFLAGS)
MODULESLDFLAGS			= $(VIRT_AM_LDFLAGS) $(VIRT_COMMON_LDFLAGS) -module -avoid-version -export-dynamic
MODULESLIBADD			= $(VIRT_COMMON_LIBS)

if modlibvirt
fvlib_LTLIBRARIES		+= virt.la
virt_la_CFLAGS			= $(MODULESCFLAGS) $(nss_CFLAGS) $(virt_CFLAGS)
virt_la_LDFLAGS			= $(MODULESLDFLAGS)
virt_la_LIBADD			= $(MODULESLIBADD) $(nss_LIBS) $(virt_LIBS) $(uuid_LIBS)
endif
if modcpg
fvlib_LTLIBRARIES		+= cpg.la
cpg_la_CFLAGS			= $(MODULESCFLAGS) $(nss_CFLAGS) $(cpg_CFLAGS) $(virt_CFLAGS)
cpg_la_LDFLAGS			= $(MODULESLDFLAGS)
cpg_la_LIBADD			= $(MODULESLIBADD) $(nss_LIBS) $(cpg_LIBS) $(virt_LIBS) $(uuid_LIBS)
endif
if modmulticast
fvlib_LTLIBRARIES		+= multicast.la
multicast_la_CFLAGS		= $(MODULESCFLAGS) $(nss_CFLAGS)
multicast_la_LDFLAGS		= $(MODULESLDFLAGS)
multicast_la_LIBADD		= $(MODULESLIBADD) $(nss_LIBS)
endif
if modserial
fvlib_LTLIBRARIES		+= serial.la
serial_la_CFLAGS		= $(MODULESCFLAGS) $(nss_CFLAGS) $(xml2_CFLAGS) $(virt_CFLAGS)
serial_la_LDFLAGS		= $(MODULESLDFLAGS)
serial_la_LIBADD		= $(MODULESLIBADD) $(nss_LIBS) $(xml2_LIBS) $(virt_LIBS)
endif
if modtcp
fvlib_LTLIBRARIES		+= tcp.la
tcp_la_CFLAGS			= $(MODULESCFLAGS) $(nss_CFLAGS)
tcp_la_LDFLAGS			= $(MODULESLDFLAGS)
tcp_la_LIBADD			= $(MODULESLIBADD) $(nss_LIBS)
endif
if modvsock
fvlib_LTLIBRARIES		+= vsock.la
vsock_la_CFLAGS			= $(MODULESCFLAGS) $(nss_CFLAGS)
vsock_la_LDFLAGS		= $(MODULESLDFLAGS)
vsock_la_LIBADD			= $(MODULESLIBADD) $(nss_LIBS)
endif
