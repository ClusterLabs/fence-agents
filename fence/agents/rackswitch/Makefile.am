MAINTAINERCLEANFILES	 = Makefile.in

TARGET			 = fence_rackswitch

sbin_PROGRAMS		 = $(TARGET)

noinst_HEADERS		 = do_rack.h

fence_rackswitch_SOURCES = do_rack.c

dist_man_MANS		 = $(TARGET).8

fence_rackswitch.8: fence_rackswitch $(top_srcdir)/fence/agents/lib/fence2man.xsl
	set -e && \
	./$^ -o metadata > .$@.tmp && \
	xsltproc $(top_srcdir)/fence/agents/lib/fence2man.xsl .$@.tmp > $@

clean-local:
	rm -f *.8 .*.8.tmp