TEMPFILE:=$(shell mktemp)
DATADIR:=../../../tests/data/metadata

check: $(TARGET:%=xml-check.%) $(SYMTARGET:%=xml-check.%)

xml-check.%: %
	$(eval INPUT=$(subst xml-check.,,$@))
	./$(INPUT) -o metadata > $(TEMPFILE)
	diff $(TEMPFILE) $(DATADIR)/$(INPUT).xml
	rm $(TEMPFILE)

xml-upload.%: %
	$(eval INPUT=$(subst xml-upload.,,$@))
	./$(INPUT) -o metadata > $(DATADIR)/$(INPUT).xml

