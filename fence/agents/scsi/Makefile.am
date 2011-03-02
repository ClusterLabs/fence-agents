MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_scsi

SRC			= $(TARGET).pl

EXTRA_DIST		= $(SRC) \
			  $(TARGET)_check.pl 

scsidatadir		= $(CLUSTERDATA)

scsidata_SCRIPTS	= $(TARGET)_check.pl

sbin_SCRIPTS		= $(TARGET)

dist_man_MANS		= $(TARGET).8

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
