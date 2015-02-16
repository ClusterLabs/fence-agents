MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_drac

SRC			= $(TARGET).pl

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET)

man_MANS		= $(TARGET).8

FENCE_TEST_ARGS         = -l test -p test -a test

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fencemanperl.mk

clean-local: clean-man
	rm -f $(TARGET)
