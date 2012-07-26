MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_ipmilan

SYMTARGET		= fence_ilo3 fence_imm fence_idrac

sbin_PROGRAMS		= $(TARGET)

sbin_SCRIPTS		= $(SYMTARGET)

noinst_HEADERS		= expect.h

fence_ipmilan_SOURCES	= expect.c ipmilan.c

man_MANS		= $(TARGET).8 $(SYMTARGET:%=%.8)

$(SYMTARGET): $(TARGET)
	cp $^ $@

include $(top_srcdir)/make/fencemanc.mk

clean-local: clean-man
	rm -f $(TARGET) $(SYMTARGET)
