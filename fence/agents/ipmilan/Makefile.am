MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_ipmilan

SYMTARGET		= fence_ilo3 fence_ilo4 fence_imm fence_idrac

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET) $(SYMTARGET)

man_MANS		= $(TARGET).8 $(SYMTARGET:%=%.8)

FENCE_TEST_ARGS         = -l test -p test -a test

$(SYMTARGET): $(TARGET)
	cp $^ $@

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk
