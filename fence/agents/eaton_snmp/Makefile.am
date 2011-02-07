MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_eaton_snmp

EXTRA_DIST		= $(TARGET).py \
			  README

sbin_SCRIPTS		= $(TARGET)

man_MANS		= $(TARGET).8

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk

clean-local: clean-man
	rm -f $(TARGET)
