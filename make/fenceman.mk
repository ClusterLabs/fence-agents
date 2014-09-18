%.8: $(TARGET) $(top_srcdir)/fence/agents/lib/fence2man.xsl
	set -e && \
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib \
		python $(@:%.8=%) -o metadata > .$@.tmp && \
	xmllint --noout --relaxng $(abs_srcdir)/../lib/metadata.rng .$@.tmp && \
	xsltproc $(top_srcdir)/fence/agents/lib/fence2man.xsl .$@.tmp > $@
	xsltproc $(top_srcdir)/fence/agents/lib/fence2wiki.xsl .$@.tmp | grep -v '<?xml' > $(@:%.8=%.wiki)

clean-man:
	rm -f *.8 .*.8.tmp *.wiki
