MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_amt

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET)

man_MANS		= $(TARGET).8

FENCE_TEST_ARGS         = -p test -a test

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk
