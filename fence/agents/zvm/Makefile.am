MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_zvmip

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET)

sbin_PROGRAMS           = fence_zvm
fence_zvm_SOURCES	= fence_zvm.c
fence_zvm_CFLAGS	= -D_GNU_SOURCE

man_MANS		= $(TARGET).8 fence_zvm.8

fence_zvm.8: fence_zvm_man_page
	cp fence_zvm_man_page fence_zvm.8

FENCE_TEST_ARGS         = -l test -p test -a test -n 1

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk

# we do not test fence_zvm because it can be compiled only on specific architecture
check: xml-check.fence_zvmip delay-check.fence_zvmip
