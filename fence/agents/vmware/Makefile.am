MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_vmware fence_vmware_helper

EXTRA_DIST		= fence_vmware.py fence_vmware_helper.pl

sbin_SCRIPTS		= $(TARGET)

dist_man_MANS		= fence_vmware.8

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk

clean-local: clean-man
	rm -f $(TARGET)
