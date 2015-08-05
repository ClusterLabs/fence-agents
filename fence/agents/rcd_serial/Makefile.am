MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_rcd_serial

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC) 

sbin_SCRIPTS		= $(TARGET)

man_MANS		= $(TARGET).8

FENCE_TEST_ARGS         = 

fence_rcd_serial_check: $(TARGET)

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk

