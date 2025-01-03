# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.63])

# TODO: port .gitarchiver

AC_INIT([fence-agents],
	[m4_esyscmd([make/git-version-gen .tarball-version])],
	[developers@clusterlabs.org])

AC_CONFIG_AUX_DIR([.])

# Don't let AC_PROC_CC (invoked by AC_USE_SYSTEM_EXTENSIONS) replace
# undefined CFLAGS with -g -O2, overriding our special OPT_CFLAGS.
: ${CFLAGS=""}
AC_USE_SYSTEM_EXTENSIONS
AM_INIT_AUTOMAKE([1.13 dist-bzip2 dist-xz color-tests -Wno-portability subdir-objects])

# Sanitize path

if test "$prefix" = "NONE"; then
	prefix="/usr"
	if test "$localstatedir" = "\${prefix}/var"; then
		localstatedir="/var"
	fi
	if test "$sysconfdir" = "\${prefix}/etc"; then
		sysconfdir="/etc"
	fi
	if test "$libdir" = "\${exec_prefix}/lib"; then
		if test -e /usr/lib64; then
			libdir="/usr/lib64"
		else
			libdir="/usr/lib"
		fi
	fi
fi

case $exec_prefix in
  NONE)   exec_prefix=$prefix;;
  prefix) exec_prefix=$prefix;;
esac

# It is necessary to have this done before libtool does linker detection.
# See also: https://github.com/kronosnet/kronosnet/issues/107
# --as-needed: Modern systems have builtin ceil() making -lm superfluous but
# AC_SEARCH_LIBS can't detect this because it tests with a false prototype
AX_CHECK_LINK_FLAG([-Wl,--enable-new-dtags],
		   [AM_LDFLAGS=-Wl,--enable-new-dtags],
		   [AC_MSG_ERROR(["Linker support for --enable-new-dtags is required"])])
AX_CHECK_LINK_FLAG([-Wl,--as-needed], [AM_LDFLAGS="$AM_LDFLAGS -Wl,--as-needed"])

LT_PREREQ([2.2.6])
LT_INIT

AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([lib/fencing.py.py])
AC_CONFIG_HEADERS([make/config.h])

AC_CANONICAL_HOST
AC_PROG_LIBTOOL

AC_LANG([C])

# Checks for programs.

# check stolen from gnulib/m4/gnu-make.m4
if ! ${MAKE-make} --version /cannot/make/this >/dev/null 2>&1; then
	AC_MSG_ERROR([you don't seem to have GNU make; it is required])
fi

AC_PROG_CC
AM_PROG_CC_C_O
AC_PROG_GCC_TRADITIONAL
AC_PROG_LN_S
AC_PROG_INSTALL
AC_PROG_MAKE_SET
AC_PROG_AWK
AC_PROG_CXX
AC_PROG_YACC
AC_PROG_LEX
PKG_PROG_PKG_CONFIG

## local helper functions

# this function checks if CC support options passed as
# args. Global CFLAGS are ignored during this test.
cc_supports_flag() {
	local CFLAGS="-Werror $@"
	AC_MSG_CHECKING([whether $CC supports "$@"])
	AC_COMPILE_IFELSE([AC_LANG_PROGRAM([[ ]], [[ ]])],
			  [RC=0; AC_MSG_RESULT([yes])],
			  [RC=1; AC_MSG_RESULT([no])])
	return $RC
}

# Checks for header files.
AC_HEADER_DIRENT
AC_HEADER_STDC
AC_HEADER_SYS_WAIT
AC_HEADER_TIME
AC_CHECK_HEADERS([arpa/inet.h fcntl.h malloc.h netdb.h netinet/in.h stdint.h stdlib.h string.h sys/ioctl.h sys/socket.h sys/time.h syslog.h termios.h unistd.h libintl.h limits.h netdb.h stddef.h])

# Checks for typedefs, structures, and compiler characteristics.
AC_C_INLINE
AC_C_CONST
AC_TYPE_SIZE_T
AC_TYPE_SSIZE_T
AC_TYPE_UINT32_T
AC_TYPE_OFF_T
AC_TYPE_SIGNAL

# Checks for library functions.
AC_FUNC_FORK
AC_FUNC_MALLOC
AC_FUNC_CLOSEDIR_VOID
AC_FUNC_MEMCMP
AC_FUNC_SELECT_ARGTYPES
AC_FUNC_STAT
AC_CHECK_FUNCS([alarm atexit bzero dup2 memmove memset select socket strcasecmp strchr strdup strerror strtol gettimeofday])

# local options
AC_ARG_ENABLE([debug],
	[  --enable-debug          enable debug build. ],
	[ default="no" ])

AC_ARG_WITH([fenceagentslibdir],
	[  --with-fenceagentslibdir=PATH
                          installation path for fence library. ],
	[ FENCEAGENTSLIBDIR="$withval" ],
	[ FENCEAGENTSLIBDIR="${datadir}/fence" ])

AC_ARG_WITH([agents],
	[  --with-agents=LIST
                          list of agents to build/ship (default: all). ],
	[ AGENTS_LIST="$withval" ],
	[ AGENTS_LIST="all" ])

FENCETMPDIR=${localstatedir}/run/fence-agents
AC_ARG_WITH(fencetmpdir,
    [  --with-fencetmpdir=DIR      directory for fence agents state files [${FENCETMPDIR}]],
    [ FENCETMPDIR="$withval" ])

# Expand $prefix
eval FENCETMPDIR="`eval echo ${FENCETMPDIR}`"
AC_DEFINE_UNQUOTED(FENCETMPDIR,"$FENCETMPDIR", Where Fence agents keep state files)
AC_SUBST(FENCETMPDIR)

SBDPID_PATH=${localstatedir}/run/sbd.pid
AC_SUBST(SBDPID_PATH)

if test "x$AGENTS_LIST" = x; then
	AC_ERROR([No agents selected])
fi

# PKG_CHECK_MODULES will fail if systemd is not found by default, so make sure
# we set the proper vars and deal with it
PKG_CHECK_MODULES([systemd], [systemd], [HAS_SYSTEMD=yes], [HAS_SYSTEMD=no])
if test "x$HAS_SYSTEMD" == "xyes"; then
	PKG_CHECK_VAR([SYSTEMD_TMPFILES_DIR], [systemd], [tmpfilesdir])
	if test "x$SYSTEMD_TMPFILES_DIR" == "x"; then
		AC_MSG_ERROR([Unable to detect systemd tmpfiles directory automatically])
	fi

	# sanitize systed vars when using non standard prefix
	if test "$prefix" != "/usr"; then
		SYSTEMD_TMPFILES_DIR="$prefix/$SYSTEMD_TMPFILES_DIR"
		AC_SUBST([SYSTEMD_TMPFILES_DIR])
	fi
fi
AM_CONDITIONAL(HAVE_SYSTEMD, [test "x$HAS_SYSTEMD" == xyes ])

FENCE_KDUMP=0
if echo "$AGENTS_LIST" | grep -q -E "all|kdump"; then
	case "$host_os" in
		*bsd*)
			;;
		*)
			FENCE_KDUMP=1
			;;
	esac
	AGENTS_LIST=$(echo "$AGENTS_LIST" | sed -E "s/kdump( |$)//")
fi

FENCE_MANUAL=0
if echo "$AGENTS_LIST" | grep -q -E "all|manual"; then
	FENCE_MANUAL=1
	AGENTS_LIST=$(echo "$AGENTS_LIST" | sed -E "s/manual( |$)//")
fi

FENCE_MPATH=0
if echo "$AGENTS_LIST" | grep -q -E "all|mpath"; then
	FENCE_MPATH=1
fi

FENCE_SCSI=0
if echo "$AGENTS_LIST" | grep -q -E "all|scsi"; then
	FENCE_SCSI=1
fi

FENCE_ZVM=0
if echo "$AGENTS_LIST" | grep -q -E "zvm( |$)"; then
	FENCE_ZVM=1
fi

FENCE_VIRT=0
if echo "$AGENTS_LIST" | grep -q -E "all|(^| )virt( |$)"; then
	AGENTS_LIST=$(echo "$AGENTS_LIST" | sed -E "s/(^| )virt( |$)//")
	case "$host_os" in
		*bsd*)
			;;
		*)
			FENCE_VIRT=1

			VIRT_AM_LDFLAGS="$AM_LDFLAGS -fPIC -fPIE -Wl,-z,now"
			AC_SUBST([VIRT_AM_LDFLAGS])

			VIRT_AM_CFLAGS="-fPIC -fPIE -I\$(top_srcdir)/agents/virt/include -D_GNU_SOURCE"
			AC_SUBST([VIRT_AM_CFLAGS])

			VIRT_COMMON_LDFLAGS="-Wl,-wrap,syslog,-wrap,closelog"
			AC_SUBST([VIRT_COMMON_LDFLAGS])

			VIRT_COMMON_LIBS="-Wl,-Bstatic -L\$(top_builddir)/agents/virt/common -lfence_virt -Wl,-Bdynamic"
			AC_SUBST([VIRT_COMMON_LIBS])

			VIRT_CONFIG_LIBS="-L\$(top_builddir)/agents/virt/config -lsimpleconfig"
			AC_SUBST([VIRT_CONFIG_LIBS])

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
			;;
	esac
fi

if test "x$AGENTS_LIST" != xall; then
	for j in $AGENTS_LIST; do
		if ! test -f agents/$j/fence_$j*.py; then
			AC_ERROR([Agent $j does not exist])
		fi
		AGENTS_LIST=`echo "$AGENTS_LIST" | sed -E -e "s#$j([^_/]|$)#$j/fence_$j\1#g" -e "s#zvm/fence_zvm( |$)#zvm/fence_zvmip\1#g"`
	done
fi

if test "x$AGENTS_LIST" = xall; then
	AGENTS_LIST=`find $srcdir/agents -mindepth 2 -maxdepth 2 -name 'fence_*.py' -print0 | xargs -0 | sed -E -e 's#[^ ]*/agents/##g' -e 's#lib/[A-Za-z_.]*( |$)##g' -e 's#nss_wrapper/[A-Za-z_.]*( |$)##g' -e 's#autodetect/[A-Za-z_.]*( |$)##g'`
fi

XENAPILIB=0
if echo "$AGENTS_LIST" | grep -q xenapi; then
	XENAPILIB=1
fi

## random vars

LOGDIR=${localstatedir}/log/cluster
CLUSTERVARRUN=${localstatedir}/run/cluster
CLUSTERDATA=${datadir}/cluster

## Program Paths
PATH="$PATH:/sbin:/usr/sbin:/usr/local/sbin:/usr/local/bin"
export PATH

AC_PATH_PROGS(XMLLINT, xmllint)
AM_CONDITIONAL(BUILD_DOC, test "x$XMLLINT" != "x" )
if test "x$XMLLINT" = "x"; then
   AC_MSG_WARN([xmllint not installed, unable to (re-)build manual pages])
   exit 1
fi
AC_SUBST(XMLLINT)

AC_PATH_PROGS(XSLTPROC, xsltproc)
AM_CONDITIONAL(BUILD_DOC, test "x$XSLTPROC" != "x" )
if test "x$XSLTPROC" = "x"; then
   AC_MSG_WARN([xsltproc not installed, unable to (re-)build manual pages])
   exit 1
fi
AC_SUBST(XSLTPROC)

AM_PATH_PYTHON([3.6])
if test -z "$PYTHON"; then
    echo "*** Essential program python not found" 1>&2
    exit 1
fi

dnl Ensure PYTHON is an absolute path
AC_PATH_PROG([PYTHON], [$PYTHON])

AC_PYTHON_MODULE(pexpect, 1)
AC_PYTHON_MODULE(pycurl, 1)
AC_PYTHON_MODULE(requests, 1)

AC_PYTHON_MODULE(boto3)
AM_CONDITIONAL(HAVE_BOTO3, [test "x$HAVE_PYMOD_BOTO3" == xyes ])

if echo "$AGENTS_LIST" | grep -q amt_ws; then
	AC_PYTHON_MODULE(pywsman)
	if test "x${HAVE_PYMOD_PYWSMAN}" != xyes; then
		AGENTS_LIST=$(echo "$AGENTS_LIST" | sed -E "s#amt_ws/fence_amt_ws.py( |$)##")
		AC_MSG_WARN("Not building fence_amt_ws")
	fi
fi
if echo "$AGENTS_LIST" | grep -q -E "ovh|vmware_soap"; then
	AC_PYTHON_MODULE(suds)
	if test "x${HAVE_PYMOD_SUDS}" != xyes; then
		AGENTS_LIST=$(echo "$AGENTS_LIST" | sed -E "s#(ovh/fence_ovh|vmware_soap/fence_vmware_soap).py( |$)##g")
		AC_MSG_WARN("Not building fence_ovh and fence_vmware_soap")
	fi
fi
if echo "$AGENTS_LIST" | grep -q gce; then
	AC_PYTHON_MODULE(google.auth)
fi

## path to 3rd-party binaries
AC_PATH_PROG([IPMITOOL_PATH], [ipmitool], [/usr/bin/ipmitool])
AC_PATH_PROG([OPENSTACK_PATH], [openstack], [/usr/bin/openstack])
AC_PATH_PROG([AMTTOOL_PATH], [amttool], [/usr/bin/amttool])
AC_PATH_PROG([GNUTLSCLI_PATH], [gnutlscli], [/usr/bin/gnutls-cli])
AC_PATH_PROG([COROSYNC_CMAPCTL_PATH], [corosync-cmapctl], [/usr/sbin/corosync-cmapctl])
AC_PATH_PROG([SG_PERSIST_PATH], [sg_persist], [/usr/bin/sg_persist])
AC_PATH_PROG([SG_TURS_PATH], [sg_turs], [/usr/bin/sg_turs])
AC_PATH_PROG([VGS_PATH], [vgs], [/usr/sbin/vgs])
AC_PATH_PROG([SUDO_PATH], [sudo], [/usr/bin/sudo])
AC_PATH_PROG([SSH_PATH], [ssh], [/usr/bin/ssh])
AC_PATH_PROG([TELNET_PATH], [telnet], [/usr/bin/telnet])
AC_PATH_PROG([MPATH_PATH], [mpathpersist], [/usr/sbin/mpathpersist])
AC_PATH_PROG([SBD_PATH], [sbd], [/usr/sbin/sbd])
AC_PATH_PROG([SUDO_PATH], [sudo], [/usr/bin/sudo])
AC_PATH_PROG([SNMPWALK_PATH], [snmpwalk], [/usr/bin/snmpwalk])
AC_PATH_PROG([SNMPSET_PATH], [snmpset], [/usr/bin/snmpset])
AC_PATH_PROG([SNMPGET_PATH], [snmpget], [/usr/bin/snmpget])
AC_PATH_PROG([NOVA_PATH], [nova], [/usr/bin/nova])
AC_PATH_PROG([POWERMAN_PATH], [powerman], [/usr/bin/powerman])

AC_PATH_PROG([PING_CMD], [ping])
AC_PATH_PROG([PING6_CMD], [ping6])
AC_PATH_PROG([PING4_CMD], [ping4])

if test "x${ac_cv_path_PING_CMD}" = x; then
	# assume multicall-ping just not available in build-environment
	PING_CMD="/bin/ping"
	PING4_CMD="/bin/ping -4"
	PING6_CMD="/bin/ping -6"
elif test "x${ac_cv_path_PING6_CMD}" = x; then
	# just IPv4
	PING4_CMD="${ac_cv_path_PING_CMD}"
elif test -L ${ac_cv_path_PING6_CMD}; then
	# assume multicall-ping
	PING4_CMD="${ac_cv_path_PING_CMD} -4"
else
	# ping is just IPv4
	PING4_CMD="${ac_cv_path_PING_CMD}"
fi


## do subst

AC_SUBST([LOGDIR])
AC_SUBST([CLUSTERVARRUN])
AC_SUBST([CLUSTERDATA])
AC_SUBST([FENCEAGENTSLIBDIR])
AC_SUBST([SNMPBIN])
AC_SUBST([AGENTS_LIST])
AM_CONDITIONAL(BUILD_FENCE_KDUMP, test $FENCE_KDUMP -eq 1)
AM_CONDITIONAL(BUILD_FENCE_MANUAL, test $FENCE_MANUAL -eq 1)
AM_CONDITIONAL(BUILD_FENCE_MPATH, test $FENCE_MPATH -eq 1)
AM_CONDITIONAL(BUILD_FENCE_SCSI, test $FENCE_SCSI -eq 1)
AM_CONDITIONAL(BUILD_FENCE_ZVM, test $FENCE_ZVM -eq 1)
AM_CONDITIONAL(BUILD_FENCE_VIRT, test $FENCE_VIRT -eq 1)
AM_CONDITIONAL(BUILD_XENAPILIB, test $XENAPILIB -eq 1)

AC_SUBST([IPMITOOL_PATH])
AC_SUBST([OPENSTACK_PATH])
AC_SUBST([AMTTOOL_PATH])
AC_SUBST([COROSYNC_CMAPCTL_PATH])
AC_SUBST([SG_PERSIST_PATH])
AC_SUBST([SG_TURS_PATH])
AC_SUBST([VGS_PATH])
AC_SUBST([POWERMAN_PATH])

## fence-virt stuff

if test "x$FENCE_VIRT" = "x1"; then
	sysconf=$(eval echo $sysconfdir)
	AC_DEFINE_UNQUOTED([SYSCONFDIR], ["$sysconf"], [Default config dir])
fi

### The following options only are used when $modules="yes" ###

# libvirt plugin: Enabled by default
AC_ARG_ENABLE(libvirt-plugin,
[AS_HELP_STRING([--disable-libvirt-plugin],
		[Disable local-mode libvirt backend plugin])],
[ modlibvirt=$enableval ], [ modlibvirt=yes ])

AM_CONDITIONAL([modlibvirt], [test "x$modlibvirt" == "xyes"])
if test "x$modlibvirt" == "xyes" && test "x$FENCE_VIRT" = "x1"; then
	PKG_CHECK_MODULES([virt], [libvirt])
fi

# cpg plugin: Disabled by default
AC_ARG_ENABLE(cpg-plugin,
[AS_HELP_STRING([--disable-cpg-plugin],
		[Enable CPG/libvirt backend plugin])],
[ modcpg=$enableval ], [ modcpg=yes ])

AM_CONDITIONAL([modcpg], [test "x$modcpg" == "xyes"])

if test "x$modcpg" == "xyes" && test "x$FENCE_VIRT" = "x1"; then
	PKG_CHECK_MODULES([cpg], [libcpg])
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

# Try to detect the appropriate conf dir. Several systems have both /etc/default
# and /etc/sysconfig but latter is always primary.
AC_ARG_VAR(initconfdir, [directory for initscripts configuration])
if test "x$initconfdir" = x && test "x$FENCE_VIRT" = "x1"; then
	AC_CHECK_FILE(/etc/conf.d, [initconfdir='$(sysconfdir)/conf.d}'], [# Gentoo/Arch
	AC_CHECK_FILE(/etc/sysconfig, [initconfdir='$(sysconfdir)/sysconfig'], [# RedHat/Fedora/Slax/Mandriva/S
	AC_CHECK_FILE(/etc/default, [initconfdir='$(sysconfdir)/default'], [# Debian/Ubuntu
	AC_MSG_ERROR([could not determine system initscripts config dir; please set initconfdir manually.])])])])
fi

## *FLAGS handling

ENV_CFLAGS="$CFLAGS"
ENV_CPPFLAGS="$CPPFLAGS"
ENV_LDFLAGS="$LDFLAGS"

# debug build stuff
if test "x${enable_debug}" = xyes; then
	AC_DEFINE_UNQUOTED([DEBUG], [1], [Compiling Debugging code])
	OPT_CFLAGS="-O0"
else
	OPT_CFLAGS="-O2"
fi

# gdb flags
if test "x${GCC}" = xyes; then
	GDB_FLAGS="-ggdb3"
else
	GDB_FLAGS="-g"
fi

# extra warnings
EXTRA_WARNINGS=""

WARNLIST="
	error
	all
	shadow
	missing-prototypes
	missing-declarations
	strict-prototypes
	declaration-after-statement
	pointer-arith
	write-strings
	cast-align
	bad-function-cast
	missing-format-attribute
	format=2
	format-security
	format-nonliteral
	no-long-long
	unsigned-char
	gnu89-inline
	no-strict-aliasing
	"

for j in $WARNLIST; do
	if cc_supports_flag -W$j; then
		EXTRA_WARNINGS="$EXTRA_WARNINGS -W$j";
	fi
done

AM_CFLAGS="$ENV_CFLAGS $OPT_CFLAGS $GDB_FLAGS $EXTRA_WARNINGS"

AC_SUBST([AM_CFLAGS])

CPPFLAGS="-I\$(top_builddir)/make -I\$(top_srcdir)/make -I. $ENV_CPPFLAGS"
LDFLAGS="$ENV_LDFLAGS"

AM_EXTRA_RECURSIVE_TARGETS([delay-check xml-check xml-upload test-fencing])

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

if test "x$VERSION" = "xUNKNOWN"; then
	AC_MSG_ERROR([m4_text_wrap([
  configure was unable to determine the source tree's current version. This
  generally happens when using git archive (or the github download button)
  generated tarball/zip file. In order to workaround this issue, either use git
  clone https://github.com/ClusterLabs/fence-agents.git or use an official release
  tarball. Alternatively you can add a compatible version in a .tarball-version
  file at the top of the source tree, wipe your autom4te.cache dir and generated
  configure, and rerun autogen.sh.
  ], [  ], [   ], [76])])
fi


AC_CONFIG_FILES([Makefile
		 fence-agents.pc
		 agents/Makefile
		 lib/Makefile
		 lib/tests/Makefile
		 doc/Makefile
		 systemd/Makefile
		 systemd/fence-agents.conf
		 agents/virt/Makefile
		 agents/virt/config/Makefile
		 agents/virt/common/Makefile
		 agents/virt/client/Makefile
		 agents/virt/server/Makefile
		 agents/virt/man/Makefile
		 ])

AC_OUTPUT
