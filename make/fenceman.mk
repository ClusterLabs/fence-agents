%.8: $(TARGET) $(top_srcdir)/fence/agents/lib/fence2man.xsl
	set -e && \
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib \
		python $^ -o metadata > .$@.tmp && \
	xsltproc $(top_srcdir)/fence/agents/lib/fence2man.xsl .$@.tmp > $@

clean-man:
	rm -f *.8 .*.8.tmp
