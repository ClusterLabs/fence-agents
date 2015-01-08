MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_apc_snmp

SYMTARGET		= fence_tripplite_snmp

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC) \
			  powernet369.mib \
			  README

sbin_SCRIPTS		= $(TARGET) $(SYMTARGET)

man_MANS		= $(TARGET).8 $(SYMTARGET).8

FENCE_TEST_ARGS         = -l test -p test -a test -n 1

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk

$(SYMTARGET): $(TARGET)
	cp $^ $@
