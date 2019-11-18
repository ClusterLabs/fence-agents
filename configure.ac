#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.63])
AC_INIT([fence-virt],
	[m4_esyscmd([build-aux/git-version-gen .tarball-version .gitarchivever])],
	[developers@clusterlabs.org])

# Don't let AC_PROC_CC (invoked by AC_USE_SYSTEM_EXTENSIONS) replace
# undefined CFLAGS with -g -O2, overriding our special OPT_CFLAGS.
: ${CFLAGS=""}
AC_USE_SYSTEM_EXTENSIONS
AM_INIT_AUTOMAKE([1.13 dist-bzip2 dist-xz color-tests -Wno-portability subdir-objects])

# sanitize paths
if test "$prefix" = "NONE"; then
	prefix="/usr"
	if test "$localstatedir" = "\${prefix}/var"; then
		localstatedir="/var"
	fi
	if test "$sysconfdir" = "\${prefix}/etc"; then
		sysconfdir="/etc"
	fi
	if test "$systemddir" = "NONE/lib/systemd/system"; then
		systemddir=/lib/systemd/system
	fi
	if test "$libdir" = "\${exec_prefix}/lib"; then
		if test -e /usr/lib64; then
			libdir="/usr/lib64"
		else
			libdir="/usr/lib"
		fi
	fi
fi

LT_PREREQ([2.2.6])
# --enable-new-dtags: Use RUNPATH instead of RPATH.
# It is necessary to have this done before libtool does linker detection.
# See also: https://github.com/kronosnet/kronosnet/issues/107
# --as-needed: Modern systems have builtin ceil() making -lm superfluous but
# AC_SEARCH_LIBS can't detect this because it tests with a false prototype
AX_CHECK_LINK_FLAG([-Wl,--enable-new-dtags],
		   [AM_LDFLAGS=-Wl,--enable-new-dtags],
		   [AC_MSG_ERROR(["Linker support for --enable-new-dtags is required"])])
AX_CHECK_LINK_FLAG([-Wl,--as-needed], [AM_LDFLAGS="$AM_LDFLAGS -Wl,--as-needed"])

AM_LDFLAGS="$AM_LDFLAGS -fPIC -fPIE -Wl,-z,now"

AC_SUBST([AM_LDFLAGS])
saved_LDFLAGS="$LDFLAGS"
LDFLAGS="$AM_LDFLAGS $LDFLAGS"
LT_INIT
LDFLAGS="$saved_LDFLAGS"

AM_CFLAGS="-fPIC -fPIE -I\$(top_srcdir)/include -Wall -Wformat=2 -Wstrict-prototypes -Wshadow -Wno-unused -D_GNU_SOURCE"
AC_SUBST([AM_CFLAGS])

COMMON_LDFLAGS="-Wl,-wrap,syslog,-wrap,closelog"
AC_SUBST([COMMON_LDFLAGS])
COMMON_LIBS="-Wl,-Bstatic -L\$(top_builddir)/common -lfence_virt -Wl,-Bdynamic"
AC_SUBST([COMMON_LIBS])

CONFIG_LIBS="-L\$(top_builddir)/config -lsimpleconfig"
AC_SUBST([CONFIG_LIBS])

sysconf=$(eval echo $sysconfdir)
AC_DEFINE_UNQUOTED([SYSCONFDIR], ["$sysconf"], [Default config dir])

###

AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([server/main.c])
AC_CONFIG_HEADER([include/config.h])

AC_CANONICAL_HOST

AC_LANG([C])

# Checks for programs.
AC_PROG_YACC
AC_PROG_CC
AC_PROG_CXX
AC_PROG_LEX
AC_PROG_INSTALL
AC_PROG_LN_S
AC_PROG_MAKE_SET
PKG_PROG_PKG_CONFIG

# Checks for libraries.
AX_PTHREAD(,[AC_MSG_ERROR([POSIX threads support is required])])
PKG_CHECK_MODULES([nss], [nss])
PKG_CHECK_MODULES([xml2], [libxml-2.0])
PKG_CHECK_MODULES([uuid], [uuid])
saved_LIBS="$LIBS"
LIBS=
AC_SEARCH_LIBS([dlopen], [dl dld], , [AC_MSG_ERROR([dlopen not found])])
AC_SUBST([dl_LIBS], [$LIBS])
LIBS="$saved_LIBS"

# Checks for header files.
AC_HEADER_DIRENT
AC_HEADER_STDC
AC_HEADER_SYS_WAIT
AC_CHECK_HEADERS([arpa/inet.h fcntl.h malloc.h netdb.h netinet/in.h stdint.h stdlib.h string.h sys/ioctl.h sys/socket.h sys/time.h syslog.h termios.h unistd.h])

# Checks for typedefs, structures, and compiler characteristics.
AC_C_CONST
AC_C_INLINE
AC_TYPE_OFF_T
AC_TYPE_SIZE_T
AC_HEADER_TIME

# Checks for library functions.
AC_FUNC_CLOSEDIR_VOID
AC_PROG_GCC_TRADITIONAL
AC_FUNC_MALLOC
AC_FUNC_MEMCMP
AC_FUNC_SELECT_ARGTYPES
AC_TYPE_SIGNAL
AC_FUNC_STAT
AC_CHECK_FUNCS([gettimeofday memmove memset select socket strcasecmp strchr strdup strerror])

#
# Modular build for fence_virtd to split up dependencies
# (default)
#
AC_ARG_ENABLE(modules,
[AS_HELP_STRING([--disable-modules],
		[Disable modular build])],
[ modules=$enableval ], [ modules=yes ])
AM_CONDITIONAL([modularbuild], [test "x$modules" == "xyes"])

if test "x$modules" == "xyes"; then
	AC_DEFINE_UNQUOTED([_MODULE], [1], [modular build])
fi

### The following options only are used when $modules="yes" ###

# Null plugin: Disabled by default
AC_ARG_ENABLE(null-plugin,
[AS_HELP_STRING([--enable-null-plugin],
		[Enable null (no-op) backend plugin])],
[ modnull=$enableval ], [ modnull=no ])

AM_CONDITIONAL([modnull], [test "x$modnull" == "xyes"])

# libvirt plugin: Enabled by default
AC_ARG_ENABLE(libvirt-plugin,
[AS_HELP_STRING([--disable-libvirt-plugin],
		[Disable local-mode libvirt backend plugin])],
[ modlibvirt=$enableval ], [ modlibvirt=yes ])

AM_CONDITIONAL([modlibvirt], [test "x$modlibvirt" == "xyes"])
if test "x$modlibvirt" == "xyes"; then
	PKG_CHECK_MODULES([virt], [libvirt])
fi

# cpg plugin: Disabled by default
AC_ARG_ENABLE(cpg-plugin,
[AS_HELP_STRING([--enable-cpg-plugin],
		[Enable CPG/libvirt backend plugin])],
[ modcpg=$enableval ], [ modcpg=no ])

AM_CONDITIONAL([modcpg], [test "x$modcpg" == "xyes"])

if test "x$modcpg" == "xyes"; then
	PKG_CHECK_MODULES([cpg], [libcpg])
fi

# (broken!) libvirt-qmf plugin: Disabled by default
AC_ARG_ENABLE(libvirt-qmf-plugin,
[AS_HELP_STRING([--enable-libvirt-qmf-plugin],
		[Enable libvirt-qmf backend plugin])],
[ modlibvirtqmf=$enableval ], [ modlibvirtqmf=no ])

AM_CONDITIONAL([modlibvirtqmf], [test "x$modlibvirtqmf" == "xyes"])

if test "x$modlibvirtqmf" == "xyes"; then
	PKG_CHECK_MODULES([qpid], [qpid])
fi

# (broken with pcmk 2.0!) pm-fence plugin: Disabled by default
AC_ARG_ENABLE(pm-fence-plugin,
[AS_HELP_STRING([--enable-pm-fence-plugin],
		[Enable pm-fence backend plugin])],
[ modpmfence=$enableval ], [ modpmfence=no ])

AM_CONDITIONAL([modpmfence], [test "x$modpmfence" == "xyes"])

if test "x$modpmfence" == "xyes"; then
	PKG_CHECK_MODULES([cib], [pacemaker-cib])
	PKG_CHECK_MODULES([ncurses], [ncurses])
	PKG_CHECK_MODULES([glib2], [glib-2.0])
	AC_SEARCH_LIBS([read_attr_delegate], [cib], [ ], [ AC_DEFINE_UNQUOTED([PM_1_0], [1], [pacemaker 1.0]) ])
fi

# multicast plugin: Enabled by default
AC_ARG_ENABLE(multicast-plugin,
[AS_HELP_STRING([--disable-multicast-plugin],
		[Disable multicast listener plugin])],
[ modmulticast=$enableval ], [ modmulticast=yes ])

AM_CONDITIONAL([modmulticast], [test "x$modmulticast" == "xyes"])

# tcp plugin: Enabled by default
AC_ARG_ENABLE(tcp-plugin,
[AS_HELP_STRING([--disable-tcp-plugin],
		[Disable TCP listener plugin])],
[ modtcp=$enableval ], [ modtcp=yes ])

AM_CONDITIONAL([modtcp], [test "x$modtcp" == "xyes"])

# serial/libvirt plugin: Enabled by default
AC_ARG_ENABLE(serial-plugin,
[AS_HELP_STRING([--disable-serial-plugin],
		[Disable serial listener plugin])],
[ modserial=$enableval ], [ modserial=yes ])

AM_CONDITIONAL([modserial], [test "x$modserial" == "xyes"])

# vsock plugin: Enabled by default
AC_ARG_ENABLE(vsock-plugin,
[AS_HELP_STRING([--disable-vsock-plugin],
		[Disable TCP listener plugin])],
[ modvsock=$enableval ], [ modvsock=yes ])

AM_CONDITIONAL([modvsock], [test "x$modvsock" == "xyes"])

#
# Compatibility symlink: enabled by default
#
AC_ARG_ENABLE(xvm-compat,
[AS_HELP_STRING([--disable-xvm-compat],
		[Disable fence_xvm symlink compatibility])],
[ xvmcompat=$enableval ], [ xvmcompat=yes ])

AM_CONDITIONAL([xvmcompat], [test "x$xvmcompat" == "xyes"])

AX_PROG_DATE
AS_IF([test "$ax_cv_prog_date_gnu_date:$ax_cv_prog_date_gnu_utc" = yes:yes],
	[UTC_DATE_AT="date -u -d@"],
	[AS_IF([test "x$ax_cv_prog_date_bsd_date" = xyes],
		[UTC_DATE_AT="date -u -r"],
		[AC_MSG_ERROR([date utility unable to convert epoch to UTC])])])
AC_SUBST([UTC_DATE_AT])

AC_ARG_VAR([SOURCE_EPOCH],[last modification date of the source])
AC_MSG_NOTICE([trying to determine source epoch])
AC_MSG_CHECKING([for source epoch in \$SOURCE_EPOCH])
AS_IF([test -n "$SOURCE_EPOCH"],
	[AC_MSG_RESULT([yes])],
	[AC_MSG_RESULT([no])
	 AC_MSG_CHECKING([for source epoch in source_epoch file])
	 AS_IF([test -e "$srcdir/source_epoch"],
		[read SOURCE_EPOCH <"$srcdir/source_epoch"
		 AC_MSG_RESULT([yes])],
		[AC_MSG_RESULT([no])
		 AC_MSG_CHECKING([for source epoch baked in by gitattributes export-subst])
		 SOURCE_EPOCH='$Format:%at$' # template for rewriting by git-archive
		 AS_CASE([$SOURCE_EPOCH],
			[?Format:*], # was not rewritten
				[AC_MSG_RESULT([no])
				 AC_MSG_CHECKING([for source epoch in \$SOURCE_DATE_EPOCH])
				 AS_IF([test "x$SOURCE_DATE_EPOCH" != x],
					[SOURCE_EPOCH="$SOURCE_DATE_EPOCH"
					 AC_MSG_RESULT([yes])],
					[AC_MSG_RESULT([no])
					 AC_MSG_CHECKING([whether git log can provide a source epoch])
					 SOURCE_EPOCH=f${SOURCE_EPOCH#\$F} # convert into git log --pretty format
					 SOURCE_EPOCH=$(cd "$srcdir" && git log -1 --pretty=${SOURCE_EPOCH%$} 2>/dev/null)
					 AS_IF([test -n "$SOURCE_EPOCH"],
						[AC_MSG_RESULT([yes])],
						[AC_MSG_RESULT([no, using current time and breaking reproducibility])
						 SOURCE_EPOCH=$(date +%s)])])],
			[AC_MSG_RESULT([yes])]
		 )])
	])
AC_MSG_NOTICE([using source epoch $($UTC_DATE_AT$SOURCE_EPOCH +'%F %T %Z')])

AC_CONFIG_FILES([Makefile
		 fence_virtd.init
                 man/Makefile
                 client/Makefile
                 common/Makefile
                 config/Makefile
 		 server/Makefile])

if test "x$VERSION" = "xUNKNOWN"; then
	AC_MSG_ERROR([m4_text_wrap([
  configure was unable to determine the source tree's current version. This
  generally happens when using git archive (or the github download button)
  generated tarball/zip file. In order to workaround this issue, either use git
  clone https://github.com/ClusterLabs/fence-virt.git or use an official release
  tarball. Alternatively you can add a compatible version in a .tarball-version
  file at the top of the source tree, wipe your autom4te.cache dir and generated
  configure, and rerun autogen.sh.
  ], [  ], [   ], [76])])
fi

AC_OUTPUT
