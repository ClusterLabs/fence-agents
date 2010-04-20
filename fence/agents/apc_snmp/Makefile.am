MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_apc_snmp

EXTRA_DIST		= $(TARGET).py \
			  powernet369.mib \
			  README

sbin_SCRIPTS		= $(TARGET)

dist_man_MANS		= $(TARGET).8

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk

clean-local: clean-man
	rm -f $(TARGET)
