MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_rcd_serial

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC) 

scsidatadir		= $(CLUSTERDATA)
scsidata_SCRIPTS	= fence_rcd_serial_check

sbin_SCRIPTS		= $(TARGET)

man_MANS		= $(TARGET).8

FENCE_TEST_ARGS         = -k 1

fence_rcd_serial_check: $(TARGET)
	cp $^ $@

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk

clean-local: clean-man
	rm -f $(TARGET) $(SYMTARGET) fence_rcd_serial_check
