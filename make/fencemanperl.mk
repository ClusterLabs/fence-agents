%.8: $(TARGET) $(top_srcdir)/fence/agents/lib/fence2man.xsl
	set -e && \
		perl $(TARGET) -o metadata > .$@.tmp && \
	xmllint --noout --relaxng $(top_srcdir)/fence/agents/lib/metadata.rng .$@.tmp && \
	xsltproc $(top_srcdir)/fence/agents/lib/fence2man.xsl .$@.tmp > $@
	xsltproc $(top_srcdir)/fence/agents/lib/fence2wiki.xsl .$@.tmp | grep -v '<?xml' > $(@:%.8=%.wiki)

clean-man:
	rm -f *.8 .*.8.tmp *.wiki
