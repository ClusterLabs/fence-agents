MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_cisco_mds

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET)

man_MANS		= $(TARGET).8

FENCE_TEST_ARGS         = -l test -p test -a test -n fc1/1

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk
