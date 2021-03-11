%.8: % $(top_srcdir)/lib/fence2man.xsl
	set -e && \
	PYTHONPATH=$(abs_srcdir)/lib:$(abs_builddir)/../lib:$(abs_builddir)/lib \
		$(PYTHON) $* -o manpage > $(@D)/.$(@F).tmp && \
	xmllint --noout --relaxng $(top_srcdir)/lib/metadata.rng $(@D)/.$(@F).tmp && \
	xsltproc $(top_srcdir)/lib/fence2man.xsl $(@D)/.$(@F).tmp > $@
	xsltproc $(top_srcdir)/lib/fence2wiki.xsl $(@D)/.$(@F).tmp | grep -v '<?xml' > $(@D)/$(@F:%.8=%.wiki)

clean-man:
	$(eval CLEAN_TARGET=$(shell find . -name "*.8" | grep -v "kdump/fence_kdump_send.8\|manual/fence_ack_manual.8"))
	rm -f $(CLEAN_TARGET) */.*.8.tmp */*.wiki
