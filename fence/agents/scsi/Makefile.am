MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_scsi

EXTRA_DIST		= fence_scsi.pl

sbin_SCRIPTS		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
