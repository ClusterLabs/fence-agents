MAINTAINERCLEANFILES	 = Makefile.in

TARGET			 = fence_rackswitch

sbin_PROGRAMS		 = $(TARGET)

noinst_HEADERS		 = do_rack.h

fence_rackswitch_SOURCES = do_rack.c

man_MANS		 = $(TARGET).8

include $(top_srcdir)/make/fencemanc.mk

clean-local: clean-man
	rm -f $(TARGET)
