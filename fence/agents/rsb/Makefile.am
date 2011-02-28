MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_rsb

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET)

dist_man_MANS		= $(TARGET).8

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
