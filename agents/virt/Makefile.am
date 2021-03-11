###############################################################################
###############################################################################
##
##  Copyright (C) 2009-2019 Red Hat, Inc.
##  
##  This copyrighted material is made available to anyone wishing to use,
##  modify, copy, or redistribute it subject to the terms and conditions
##  of the GNU General Public License v.2.
##
###############################################################################
###############################################################################

MAINTAINERCLEANFILES	= Makefile.in aclocal.m4 configure depcomp \
			  config.guess config.sub missing install-sh \
			  ltmain.sh compile config.h.in config.h.in~ \
			  autoscan.log configure.scan test-driver \
			  m4/libtool.m4 m4/lt~obsolete.m4 m4/ltoptions.m4 \
			  m4/ltsugar.m4 m4/ltversion.m4 include/config.in*

AUTOMAKE_OPTIONS	= foreign

ACLOCAL_AMFLAGS		= -I m4

SPEC			= $(PACKAGE_NAME).spec

TARFILES		= $(PACKAGE_NAME)-$(VERSION).tar.bz2 \
			  $(PACKAGE_NAME)-$(VERSION).tar.gz \
			  $(PACKAGE_NAME)-$(VERSION).tar.xz

EXTRA_DIST		= autogen.sh .version architecture.txt \
			  fence_virtd.init.in fence_virtd.service.in \
			  fence_virt.txt README README.md TODO \
			  include $(SPEC).in build-aux

SUBDIRS			= config common client server man

all-local: fence_virtd.service

clean-local:
	rm -f $(SPEC) fence_virtd.service

distclean-local:
	rm -f $(PACKAGE_NAME)-*.tar.* $(PACKAGE_NAME)-*.sha256* tag-*

fence_virtd.service: fence_virtd.service.in
	SBINDIR="@sbindir@"; \
	INITCONFDIR="@initconfdir@"; \
	cat $^ > $@ ; \
	echo "EnvironmentFile=-$$INITCONFDIR/fence_virtd" >> $@ ;\
	echo "ExecStart=$$SBINDIR/fence_virtd \$$FENCE_VIRTD_ARGS" >> $@

## make rpm/srpm section.

$(SPEC): $(SPEC).in .version config.status
	rm -f $@-t $@
	date="`LC_ALL=C $(UTC_DATE_AT)$(SOURCE_EPOCH) "+%a %b %d %Y"`" && \
	if [ -f $(abs_srcdir)/.tarball-version ]; then \
		gitver="`cat $(abs_srcdir)/.tarball-version`" && \
		rpmver=$$gitver && \
		alphatag="" && \
		dirty="" && \
		numcomm="0"; \
	elif [ "`git log -1 --pretty=format:x . 2>&1`" = "x" ]; then \
		gitver="`GIT_DIR=$(abs_srcdir)/.git git describe --abbrev=4 --match='v*' HEAD 2>/dev/null`" && \
		rpmver=`echo $$gitver | sed -e "s/^v//" -e "s/-.*//g"` && \
		alphatag=`echo $$gitver | sed -e "s/.*-//" -e "s/^g//"` && \
		vtag=`echo $$gitver | sed -e "s/-.*//g"` && \
		numcomm=`GIT_DIR=$(abs_srcdir)/.git git rev-list $$vtag..HEAD | wc -l` && \
		cd $(abs_srcdir) && \
		git update-index --refresh > /dev/null 2>&1 || true && \
		dirty=`git diff-index --name-only HEAD 2>/dev/null` && cd - 2>/dev/null; \
	else \
		gitver="`cd $(abs_srcdir); build-aux/git-version-gen .tarball-version .gitarchivever`" && \
		rpmver=$$gitver && \
		alphatag="" && \
		dirty="" && \
		numcomm="0"; \
	fi && \
	if [ -n "$$dirty" ]; then dirty="dirty"; else dirty=""; fi && \
	if [ "$$numcomm" = "0" ]; then \
		sed \
			-e "s#@version@#$$rpmver#g" \
			-e "s#%glo.*alpha.*##g" \
			-e "s#%glo.*numcomm.*##g" \
			-e "s#@dirty@#$$dirty#g" \
			-e "s#@date@#$$date#g" \
		$(abs_srcdir)/$@.in > $@-t; \
	else \
		sed \
			-e "s#@version@#$$rpmver#g" \
			-e "s#@alphatag@#$$alphatag#g" \
			-e "s#@numcomm@#$$numcomm#g" \
			-e "s#@dirty@#$$dirty#g" \
			-e "s#@date@#$$date#g" \
		$(abs_srcdir)/$@.in > $@-t; \
	fi; \
	if [ -z "$$dirty" ]; then sed -i -e "s#%glo.*dirty.*##g" $@-t; fi
	sed -i -e "s#@defaultadmgroup@#$(DEFAULTADMGROUP)#g" $@-t
	chmod a-w $@-t
	mv $@-t $@
	rm -f $@-t*

$(TARFILES):
	$(MAKE) dist

RPMBUILDOPTS	= --define "_sourcedir $(abs_builddir)" \
		  --define "_specdir $(abs_builddir)" \
		  --define "_builddir $(abs_builddir)" \
		  --define "_srcrpmdir $(abs_builddir)" \
		  --define "_rpmdir $(abs_builddir)"

srpm: clean
	$(MAKE) $(SPEC) $(TARFILES)
	rpmbuild $(RPMBUILDOPTS) --nodeps -bs $(SPEC)

rpm: clean
	$(MAKE) $(SPEC) $(TARFILES)
	rpmbuild $(RPMBUILDOPTS) -ba $(SPEC)

# release/versioning
BUILT_SOURCES	= .version
.version:
	echo $(VERSION) > $@-t && mv $@-t $@

dist-hook:
	echo $(VERSION) > $(distdir)/.tarball-version
	echo $(SOURCE_EPOCH) > $(distdir)/source_epoch
