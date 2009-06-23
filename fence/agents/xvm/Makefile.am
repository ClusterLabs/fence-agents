MAINTAINERCLEANFILES	= Makefile.in

EXTRA_DIST		= README TODO tests/hvm.xml tests/linux.xml

sbin_PROGRAMS		= fence_xvm fence_xvmd

noinst_PROGRAMS		= testprog

noinst_HEADERS		= debug.h \
			  ip_lookup.h \
			  mcast.h \
			  options.h \
			  simple_auth.h \
			  tcp.h \
			  virt.h \
			  xvm.h

sharedsources		= mcast.c \
			  simple_auth.c \
			  tcp.c \
			  options.c \
			  debug.c

sharedcppflags		= -D_GNU_SOURCE

sharedcflags		= $(nss_CFLAGS) $(logt_CFLAGS)

sharedldflags		= $(nss_LIBS) $(logt_LIBS)

fence_xvm_SOURCES	= $(sharedsources) \
			  fence_xvm.c \
			  ip_lookup.c

fence_xvm_CPPFLAGS	= $(sharedcppflags)

fence_xvm_CFLAGS	= $(sharedcflags)

fence_xvm_LDFLAGS	= $(sharedldflags)

fence_xvmd_SOURCES	= $(sharedsources) \
			  fence_xvmd.c \
			  virt.c \
			  options-ccs.c \
			  vm_states.c \
			  xml.c

fence_xvmd_CPPFLAGS	= $(sharedcppflags)

fence_xvmd_CFLAGS	= $(sharedcflags) \
			  $(virt_CFLAGS) \
			  $(xml_CFLAGS) \
			  $(cman_CFLAGS) \
			  $(ccs_CFLAGS) \
			  $(sackpt_CFLAGS)

fence_xvmd_LDFLAGS	= $(sharedldflags) \
			  $(virt_LIBS) \
			  $(xml_LIBS) \
			  $(cman_LIBS) \
			  $(ccs_LIBS) \
			  $(sackpt_LIBS)

testprog_SOURCES	= xml.c

testprog_CPPFLAGS	= -DSTANDALONE

testprog_CFLAGS		= $(xml_CFLAGS)

testprog_LDFLAGS	= $(xml_LIBS)
