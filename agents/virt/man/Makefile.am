###############################################################################
###############################################################################
##
##  Copyright (C) 2009-2021 Red Hat, Inc.
##  
##  This copyrighted material is made available to anyone wishing to use,
##  modify, copy, or redistribute it subject to the terms and conditions
##  of the GNU General Public License v.2.
##
###############################################################################
###############################################################################

MAINTAINERCLEANFILES	= Makefile.in

dist_man8_MANS 		= fence_xvm.8 fence_virtd.8
dist_man5_MANS 		= fence_virt.conf.5
man8_MANS		= fence_virt.8

fence_virt.8: $(top_builddir)/agents/virt/client/fence_virt $(top_srcdir)/lib/fence2man.xsl
	set -e && \
		../client/$(@:%.8=%) -o metadata > .$(@F).tmp && \
	xmllint --noout --relaxng $(top_srcdir)/lib/metadata.rng .$(@F).tmp && \
	xsltproc $(top_srcdir)/lib/fence2man.xsl .$(@F).tmp > $@
	xsltproc $(top_srcdir)/lib/fence2wiki.xsl .$(@F).tmp | grep -v '<?xml' > $(@F:%.8=%.wiki)


clean-local:
	rm -f fence_virt.8* .*.8.tmp *.wiki
