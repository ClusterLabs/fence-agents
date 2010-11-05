EXTRA_DIST		= autogen.sh make/fencebuild.mk scripts/fenceparse

AUTOMAKE_OPTIONS	= foreign

MAINTAINERCLEANFILES	= Makefile.in aclocal.m4 configure depcomp \
			  config.guess config.sub missing install-sh \
			  autoheader automake autoconf libtool libtoolize \
			  ltmain.sh compile make/clusterautoconfig.h.in \
			  make/clusterautoconfig.h.in~ autoscan.log \
			  configure.scan

noinst_HEADERS		= make/copyright.cf

ACLOCAL_AMFLAGS		= -I m4

SUBDIRS			= fence doc

install-exec-local:
			$(INSTALL) -d $(DESTDIR)/$(LOGDIR)
			$(INSTALL) -d $(DESTDIR)/$(CLUSTERVARRUN)

uninstall-local:
			rmdir $(DESTDIR)/$(LOGDIR) || :;
			rmdir $(DESTDIR)/$(CLUSTERVARRUN) || :;

maintainer-clean-local:
	rm -rf m4
