###############################################################################
###############################################################################
##
##  Copyright (C) 2009-2019 Red Hat, Inc.
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

fence_virtd_CFLAGS		= $(AM_CFLAGS) \
				  $(nss_CFLAGS) $(xml2_CFLAGS) $(uuid_CFLAGS) $(PTHREAD_CFLAGS)

fence_virtd_LDADD		= $(CONFIG_LIBS) $(COMMON_LIBS) \
				  $(nss_LIBS) $(xml2_LIBS) $(uuid_LIBS) $(PTHREAD_LIBS) $(dl_LIBS)

fence_virtd_LDFLAGS		= $(AM_LDFLAGS) $(COMMON_LDFLAGS)

#
# modules
#

virt_la_SOURCES			= libvirt.c
null_la_SOURCES			= null.c
virt_qmf_la_SOURCES		= libvirt-qmf.cpp
pm_fence_la_SOURCES		= pm-fence.c
cpg_la_SOURCES			= cpg-virt.c cpg.c
multicast_la_SOURCES		= mcast.c
tcp_la_SOURCES			= tcp.c
vsock_la_SOURCES		= vsock.c
serial_la_SOURCES		= virt-serial.c virt-sockets.c serial.c

#################
# Modular build #
#################
if modularbuild

fence_virtd_CFLAGS		+= -DMODULE_PATH=\"$(pkglibdir)/\"

pkglib_LTLIBRARIES		=

MODULESCFLAGS			= $(AM_CFLAGS)
MODULESLDFLAGS			= $(AM_LDFLAGS) $(COMMON_LIBS) $(COMMON_LDFLAGS) -module -avoid-version -export-dynamic

if modlibvirt
pkglib_LTLIBRARIES		+= virt.la
virt_la_SOURCES			+= virt.c uuid-test.c
virt_la_CFLAGS			= $(MODULESCFLAGS) $(nss_CFLAGS) $(virt_CFLAGS)
virt_la_LDFLAGS			= $(MODULESLDFLAGS) $(nss_LIBS) $(virt_LIBS)
endif
if modlibvirtqmf
pkglib_LTLIBRARIES		+= virt-qmf.la
virt_qmf_la_SOURCES		+= uuid-test.c
virt_qmf_la_CXXFLAGS		= $(MODULESCFLAGS) $(nss_CFLAGS) $(qpid_CFLAGS)
virt_qmf_la_LDFLAGS		= $(MODULESLDFLAGS) $(nss_LIBS) $(qpid_LIBS)
endif
if modpmfence
pkglib_LTLIBRARIES		+= pm-fence.la
pm_fence_la_CFLAGS		= $(MODULESCFLAGS) $(nss_CFLAGS) $(cib_CFLAGS) $(glib2_CFLAGS) $(xml2_CFLAGS)
pm_fence_la_LDFLAGS		= $(MODULESLDFLAGS) $(nss_LIBS) $(cib_LIBS) $(glib2_LIBS) $(xml2_LIBS)
endif
if modcpg
pkglib_LTLIBRARIES		+= cpg.la
cpg_la_SOURCES			+= virt.c history.c uuid-test.c
cpg_la_CFLAGS			= $(MODULESCFLAGS) $(nss_CFLAGS) $(cpg_CFLAGS) $(virt_CFLAGS)
cpg_la_LDFLAGS			= $(MODULESLDFLAGS) $(nss_LIBS) $(cpg_LIBS) $(virt_LIBS)
endif
if modmulticast
pkglib_LTLIBRARIES		+= multicast.la
multicast_la_SOURCES		+= history.c
multicast_la_CFLAGS		= $(MODULESCFLAGS) $(nss_CFLAGS)
multicast_la_LDFLAGS		= $(MODULESLDFLAGS) $(nss_LIBS)
endif
if modserial
pkglib_LTLIBRARIES		+= serial.la
serial_la_SOURCES		+= history.c
serial_la_CFLAGS		= $(MODULESCFLAGS) $(nss_CFLAGS) $(xml2_CFLAGS) $(virt_CFLAGS)
serial_la_LDFLAGS		= $(MODULESLDFLAGS) $(nss_LIBS) $(xml2_LIBS) $(virt_LIBS)
endif
if modtcp
pkglib_LTLIBRARIES		+= tcp.la
tcp_la_SOURCES			+= history.c
tcp_la_CFLAGS			= $(MODULESCFLAGS) $(nss_CFLAGS)
tcp_la_LDFLAGS			= $(MODULESLDFLAGS) $(nss_LIBS)
endif
if modvsock
pkglib_LTLIBRARIES		+= vsock.la
vsock_la_SOURCES		+= history.c
vsock_la_CFLAGS			= $(MODULESCFLAGS) $(nss_CFLAGS)
vsock_la_LDFLAGS		= $(MODULESLDFLAGS) $(nss_LIBS)
endif
if modnull
pkglib_LTLIBRARIES		+= null.la
null_la_CFLAGS			= $(MODULESCFLAGS)
null_la_LDFLAGS			= $(MODULESLDFLAGS)
endif

else

####################
# Monolithic build #
####################

# avoid a linking issues when:
# 1) do a server modular build
# 2) run configure to switch to monolithic build without make clean
# 3) do a server build
#
# libtool will get confused by the presence of .la files in the builddir
# and will fail to link the binary

EXTRA_fence_virtd_DEPENDENCIES	= cleanmods

cleanmods:
	@rm -rf $(builddir)/*.la

fence_virtd_SOURCES		+= virt.c history.c

if modlibvirt
fence_virtd_SOURCES		+= $(libvirt_la_SOURCES)
fence_virtd_CFLAGS		+= $(virt_CFLAGS)
fence_virtd_LDADD		+= $(virt_LIBS)
endif
if modlibvirtqmf
fence_virtd_SOURCES		+= $(libvirt_qmf_la_SOURCES)
fence_virtd_CFLAGS		+= $(qpid_CFLAGS)
fence_virtd_LDADD		+= $(qpid_LIBS)
endif
if modpmfence
fence_virtd_SOURCES		+= $(pm_fence_la_SOURCES)
fence_virtd_CFLAGS		+= $(cib_CFLAGS)
fence_virtd_LDADD		+= $(cib_LIBS)
endif
if modcpg
fence_virtd_SOURCES		+= $(cpg_la_SOURCES)
fence_virtd_CFLAGS		+= $(cpg_CFLAGS)
fence_virtd_LDADD		+= $(cpg_LIBS)
endif
if modmulticast
fence_virtd_SOURCES		+= $(multicast_la_SOURCES)
endif
if modserial
fence_virtd_SOURCES		+= $(serial_la_SOURCES)
endif
if modtcp
fence_virtd_SOURCES		+= $(tcp_la_SOURCES)
endif
if modvsock
fence_virtd_SOURCES		+= $(vsock_la_SOURCES)
endif
if modnull
fence_virtd_SOURCES		+= $(null_la_SOURCES)
endif

endif
