pkgconfigdir		= $(datadir)/pkgconfig
pkgconfig_DATA		= $(PACKAGE_NAME).pc

SPEC			= $(PACKAGE_NAME).spec

EXTRA_DIST		= autogen.sh make/fencebuild.mk \
			  .version make/release.mk \
			  make/git-version-gen make/gitlog-to-changelog tests \
			  $(pkgconfig_DATA).in $(SPEC).in

AUTOMAKE_OPTIONS	= foreign

MAINTAINERCLEANFILES	= Makefile.in aclocal.m4 configure depcomp \
			  config.guess config.sub missing install-sh \
			  autoheader automake autoconf libtool libtoolize \
			  ltmain.sh compile make/config.h.in \
			  make/config.h.in~ autoscan.log \
			  configure.scan

TARFILES		= $(PACKAGE_NAME)-$(VERSION).tar.bz2 \
			  $(PACKAGE_NAME)-$(VERSION).tar.gz \
			  $(PACKAGE_NAME)-$(VERSION).tar.xz

ACLOCAL_AMFLAGS		= -I m4

SUBDIRS			= lib agents doc systemd

if HAVE_BOTO3
HAVE_BOTO3 = 1
else
HAVE_BOTO3 = 0
endif

.PHONY: $(SUBDIRS)

agents: lib

doc: agents

install-exec-local:
			$(INSTALL) -d $(DESTDIR)/$(LOGDIR)
			$(INSTALL) -d $(DESTDIR)/$(CLUSTERVARRUN)
			$(INSTALL) -d -m 1755 $(DESTDIR)$(FENCETMPDIR)

uninstall-local:
			rmdir $(DESTDIR)/$(LOGDIR) || :;
			rmdir $(DESTDIR)/$(CLUSTERVARRUN) || :;

BUILT_SOURCES = .version
.version:
	echo $(VERSION) > $@-t && mv $@-t $@

dist-hook: gen-ChangeLog
	echo $(VERSION) > $(distdir)/.tarball-version

gen_start_date = 2000-01-01
.PHONY: gen-ChangeLog
gen-ChangeLog:
	if test -d .git; then						\
		$(top_srcdir)/make/gitlog-to-changelog			\
			--since=$(gen_start_date) > $(distdir)/cl-t;	\
		rm -f $(distdir)/ChangeLog;				\
		mv $(distdir)/cl-t $(distdir)/ChangeLog;		\
	fi

# this will get rid of "libtoolized" m4 files
maintainer-clean-local:
	rm -rf $(filter-out \
		$(top_srcdir)/m4/ax_check_link_flag.m4 \
		$(top_srcdir)/m4/ax_prog_date.m4 \
		$(top_srcdir)/m4/ax_pthread.m4 \
		$(top_srcdir)/m4/ac_python_module.m4 \
		$(top_srcdir)/m4/PKG_CHECK_VAR.m4, \
		$(wildcard $(top_srcdir)/m4/*.m4))

## make rpm/srpm section.
$(SPEC): $(SPEC).in
	rm -f $@-t $@
	date="$(shell LC_ALL=C date "+%a %b %d %Y")" && \
	specver="1" && \
	rcver="" && \
	dirty="" && \
	alphatag="" && \
	numcomm="" && \
	ver="$(VERSION)" && \
	boto3_br="$(HAVE_BOTO3)" && \
	if echo $$ver | grep -q -- "-dirty$$"; then \
		dirty="dirty" && \
		echo VERSION IS DIRTY && \
		ver=`echo $$ver | sed -e "s/-dirty$$//"`; \
	fi && \
	echo $$ver && \
	if echo $$ver | grep -q -- "-"; then \
		alphatag=`echo $$ver | sed -e "s/.*-//"` && \
		echo VERSION HAS ALPHATAG && \
		ver=`echo $$ver | sed -e "s/-.*//"`; \
	fi && \
	echo $$ver && \
	if [ -n "$$alphatag" ]; then \
		echo VERSION HAS NUMCOMMITS && \
		numcomm=`echo $$ver | sed -e 's/.*\.//'` && \
		ver=`echo $$ver | sed -e 's/.'$$numcomm'$$//'`; \
	fi && \
	if echo $$ver | grep -q "\.[[:digit:]]rc[[:digit:]]"; then \
		rpmver=`echo $$ver | sed -e "s/rc[[:digit:]].*//g"` && \
		rcver=`echo $$ver | sed -e "s/.*\(rc[[:digit:]]\).*/\1/g"` && \
		specver="0"; \
	else \
		rpmver=$$ver; \
	fi && \
	echo $$rpmver $$rcver && \
	sed \
		-e "s#@version@#$$rpmver#g" \
		-e "s#@alphatag@#$$alphatag#g" \
		-e "s#@numcomm@#$$numcomm#g" \
		-e "s#@dirty@#$$dirty#g" \
		-e "s#@date@#$$date#g" \
		-e "s#@specver@#$$specver#g" \
		-e "s#@rcver@#$$rcver#g" \
		-e "s#@rgmanager@#$(RGMANAGER)#g" \
		-e "s#@linux-ha@#$(LINUX_HA)#g" \
		-e "s#@compat-habindir@#$(COMPAT_HABINDIR)#g" \
		-e "s#@boto3_br@#$$boto3_br#g" \
	$< > $@-t; \
	if [ -z "$$dirty" ]; then sed -i -e "s#%glo.*dirty.*##g" $@-t; fi; \
	if [ -z "$$alphatag" ]; then sed -i -e "s#%glo.*alphatag.*##g" $@-t; fi; \
	if [ -z "$$numcomm" ]; then sed -i -e "s#%glo.*numcomm.*##g" $@-t; fi; \
	if [ -z "$$rcver" ]; then sed -i -e "s#%glo.*rcver.*##g" $@-t; fi
	chmod a-w $@-t
	mv $@-t $@

$(TARFILES):
	$(MAKE) dist

RPMBUILDOPTS    = --define "_sourcedir $(abs_builddir)" \
		  --define "_specdir $(abs_builddir)" \
		  --define "_builddir $(abs_builddir)" \
		  --define "_srcrpmdir $(abs_builddir)" \
		  --define "_rpmdir $(abs_builddir)"

srpm: clean
	$(MAKE) $(SPEC) $(TARFILES)
	rpmbuild $(RPMBUILDOPTS) --nodeps -bs $(SPEC)

rpm: clean
	$(MAKE) $(SPEC) $(TARFILES)
	PYTHON="$(PYTHON)" rpmbuild $(RPMBUILDOPTS) -ba $(SPEC)

clean-generic:
	rm -rf $(SPEC) $(TARFILES) $(PACKAGE_NAME)-$(VERSION) *.rpm
