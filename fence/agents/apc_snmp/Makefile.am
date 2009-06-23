MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_apc_snmp

EXTRA_DIST		= $(TARGET).py \
			  powernet369.mib \
			  README

sbin_SCRIPTS		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
