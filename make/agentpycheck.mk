TEMPFILE:=$(shell mktemp)
DATADIR:=../../../tests/data/metadata

check: $(TARGET:%=xml-check.%) $(SYMTARGET:%=xml-check.%)

xml-check.%: %
	$(eval INPUT=$(subst xml-check.,,$@))
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib python ./$(INPUT) -o metadata > $(TEMPFILE)
	diff $(TEMPFILE) $(DATADIR)/$(INPUT).xml
	rm $(TEMPFILE)

xml-upload.%: %
	$(eval INPUT=$(subst xml-upload.,,$@))
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib python ./$(INPUT) -o metadata > $(DATADIR)/$(INPUT).xml

