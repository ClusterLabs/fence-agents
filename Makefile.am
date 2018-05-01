EXTRA_DIST		= autogen.sh make/fencebuild.mk \
			  .version make/release.mk \
			  make/git-version-gen make/gitlog-to-changelog tests

AUTOMAKE_OPTIONS	= foreign

MAINTAINERCLEANFILES	= Makefile.in aclocal.m4 configure depcomp \
			  config.guess config.sub missing install-sh \
			  autoheader automake autoconf libtool libtoolize \
			  ltmain.sh compile make/clusterautoconfig.h.in \
			  make/clusterautoconfig.h.in~ autoscan.log \
			  configure.scan

ACLOCAL_AMFLAGS		= -I m4

SUBDIRS			= lib agents doc

install-exec-local:
			$(INSTALL) -d $(DESTDIR)/$(LOGDIR)
			$(INSTALL) -d $(DESTDIR)/$(CLUSTERVARRUN)

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
	         $(top_srcdir)/m4/ac_python_module.m4,$(wildcard \
		                                        $(top_srcdir)/m4/*.m4))
