MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_zvmip

sbin_PROGRAMS		= fence_zvm fence_zvmip

noinst_HEADERS		= fence_zvm.h

fence_zvm_SOURCES	= fence_zvm.c
fence_zvm_CFLAGS	= -D_GNU_SOURCE

fence_zvmip_SOURCES	= fence_zvmip.c
fence_zvmip_CFLAGS	= -D_GNU_SOURCE

dist_man_MANS		= fence_zvm.8 fence_zvmip.8

#include $(top_srcdir)/make/fencemanc.mk

clean-local:
	rm -f $(sbin_PROGRAMS)

FENCE_TEST_ARGS		= -n test -a test -p test -u test

include $(top_srcdir)/make/agentccheck.mk

# we do not test fence_zvm because it can be compiled only on specific architecture
check: xml-check.fence_zvmip delay-check.fence_zvmip