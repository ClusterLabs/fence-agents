MAINTAINERCLEANFILES	= Makefile.in

sbin_PROGRAMS		= fence_ipmilan

noinst_HEADERS		= expect.h

fence_ipmilan_SOURCES	= expect.c ipmilan.c

man_MANS		= fence_ipmilan.8

fence_ipmilan.8: fence_ipmilan $(top_srcdir)/fence/agents/lib/fence2man.xsl
	set -e && \
	./$^ -o metadata > .$@.tmp && \
	xsltproc $(top_srcdir)/fence/agents/lib/fence2man.xsl .$@.tmp > $@

clean-local:
	rm -f *.8 .*.8.tmp
