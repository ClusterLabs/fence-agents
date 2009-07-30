
# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.63b])
AC_INIT([fence-agents], [master], [linux-cluster@redhat.com])
AM_INIT_AUTOMAKE([-Wno-portability])
LT_PREREQ([2.2.7])
LT_INIT

AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([fence/agents/rackswitch/do_rack.h])
AC_CONFIG_HEADERS([make/clusterautoconfig.h])

AC_CANONICAL_HOST
AC_PROG_LIBTOOL

AC_LANG([C])

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

# Checks for programs.

# check stolen from gnulib/m4/gnu-make.m4
if ! ${MAKE-make} --version /cannot/make/this >/dev/null 2>&1; then
	AC_MSG_ERROR([you don't seem to have GNU make; it is required])
fi

AC_PROG_CC
AM_PROG_CC_C_O
AC_PROG_LN_S
AC_PROG_INSTALL
AC_PROG_MAKE_SET

## local helper functions

# this function checks if CC support options passed as
# args. Global CFLAGS are ignored during this test.
cc_supports_flag() {
	local CFLAGS="$@"
	AC_MSG_CHECKING([whether $CC supports "$@"])
	AC_COMPILE_IFELSE([int main(){return 0;}] ,
			  [RC=0; AC_MSG_RESULT([yes])],
			  [RC=1; AC_MSG_RESULT([no])])
	return $RC
}

# this function tests if a library has a certain function
# by using AC_CHECK_LIB but restores the original LIBS global
# envvar. This is required to avoid libtool to link everything
# with everything.
check_lib_no_libs() {
	AC_CHECK_LIB([$1], [$2],,
		     [AC_MSG_ERROR([Unable to find $1 library])])
	LIBS=$ac_check_lib_save_LIBS
}

# corosync libs
PKG_CHECK_MODULES([corosync],[corosync])
PKG_CHECK_MODULES([sackpt],[libSaCkpt])
PKG_CHECK_MODULES([ccs],[libccs])
PKG_CHECK_MODULES([cman],[libcman])
PKG_CHECK_MODULES([logt],[liblogthread])
PKG_CHECK_MODULES([nss],[nss])
PKG_CHECK_MODULES([nspr],[nspr])
PKG_CHECK_MODULES([virt],[libvirt])
PKG_CHECK_MODULES([xml],[libxml-2.0])

# external libs (no pkgconfig)
check_lib_no_libs pthread pthread_mutex_lock
check_lib_no_libs ldap ldap_initialize
check_lib_no_libs rt clock_gettime
check_lib_no_libs z crc32

# Checks for header files.
AC_CHECK_HEADERS([arpa/inet.h fcntl.h libintl.h limits.h malloc.h netdb.h netinet/in.h stddef.h stdint.h stdlib.h string.h sys/ioctl.h sys/socket.h sys/time.h syslog.h unistd.h])

# Checks for typedefs, structures, and compiler characteristics.
AC_C_INLINE
AC_TYPE_INT32_T
AC_TYPE_PID_T
AC_TYPE_SIZE_T
AC_TYPE_SSIZE_T
AC_TYPE_UINT16_T
AC_TYPE_UINT32_T
AC_TYPE_UINT64_T
AC_TYPE_UINT8_T

# Checks for library functions.
AC_FUNC_FORK
AC_FUNC_LSTAT_FOLLOWS_SLASHED_SYMLINK
AC_FUNC_MALLOC
AC_CHECK_FUNCS([alarm atexit bzero dup2 memmove memset select socket strcasecmp strchr strdup strerror strtol])

# local options
AC_ARG_ENABLE([debug],
	[  --enable-debug          enable debug build. ],
	[ default="no" ])

AC_ARG_WITH([syslogfacility],
	[  --syslogfacility=FACILITY
                          cluster default syslog facility. ],
	[ SYSLOGFACILITY="$withval" ],
	[ SYSLOGFACILITY="LOG_LOCAL4" ])

AC_ARG_WITH([sysloglevel],
	[  --sysloglevel=LEVEL
                          cluster default syslog level. ],
	[ SYSLOGLEVEL="$withval" ],
	[ SYSLOGLEVEL="LOG_INFO" ])

AC_ARG_WITH([fenceagentslibdir],
	[  --fenceagentslibdir=PATH
                          installation path for fence library. ],
	[ FENCEAGENTSLIBDIR="$withval" ],
	[ FENCEAGENTSLIBDIR="${datadir}/fence" ])

AC_ARG_WITH([snmpbin],
	[  --snmpbin=PATH
                          path to snmp binaries (snmpwalk/get). ],
	[ SNMPBIN="$withval" ],
	[ SNMPBIN="${bindir}" ])

AC_ARG_WITH([default-config-dir],
	[  --default-config-dir=DIR
			  cluster config directory. ],
	[ DEFAULT_CONFIG_DIR="$withval" ],
	[ DEFAULT_CONFIG_DIR="$sysconfdir/cluster" ])

## random vars

LOGDIR=${localstatedir}/log/cluster
CLUSTERVARRUN=${localstatedir}/run/cluster
CLUSTERVARLIB=${localstatedir}/lib/cluster

## do subst

AC_SUBST([DEFAULT_CONFIG_DIR])
AC_DEFINE_UNQUOTED([DEFAULT_CONFIG_DIR], "$(eval echo ${DEFAULT_CONFIG_DIR})",
		   [Default config directory])

AC_SUBST([LOGDIR])
AC_DEFINE_UNQUOTED([LOGDIR], "$(eval echo ${LOGDIR})",
		   [Default logging directory])

AC_SUBST([CLUSTERVARRUN])
AC_DEFINE_UNQUOTED([CLUSTERVARRUN], "$(eval echo ${CLUSTERVARRUN})",
		   [Default cluster var/run directory])

AC_SUBST([CLUSTERVARLIB])

AC_SUBST([FENCEAGENTSLIBDIR])
AC_SUBST([SNMPBIN])

AC_DEFINE_UNQUOTED([SYSLOGFACILITY], $(eval echo ${SYSLOGFACILITY}),
		   [Default syslog facility])

AC_DEFINE_UNQUOTED([SYSLOGLEVEL], $(eval echo ${SYSLOGLEVEL}),
		   [Default syslog level])

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

CFLAGS="$ENV_CFLAGS $OPT_CFLAGS $GDB_FLAGS \
	$EXTRA_WARNINGS $WERROR_CFLAGS"
CPPFLAGS="-I\$(top_builddir)/make -I\$(top_srcdir)/make -I. $ENV_CPPFLAGS"
LDFLAGS="$ENV_LDFLAGS"

AC_CONFIG_FILES([Makefile
		 fence/Makefile
		 fence/agents/Makefile
		 fence/agents/alom/Makefile
		 fence/agents/apc/Makefile
		 fence/agents/apc_snmp/Makefile
		 fence/agents/baytech/Makefile
		 fence/agents/bladecenter/Makefile
		 fence/agents/brocade/Makefile
		 fence/agents/bullpap/Makefile
		 fence/agents/cisco_mds/Makefile
		 fence/agents/cpint/Makefile
		 fence/agents/drac/Makefile
		 fence/agents/egenera/Makefile
		 fence/agents/eps/Makefile
		 fence/agents/ibmblade/Makefile
		 fence/agents/ifmib/Makefile
		 fence/agents/ilo/Makefile
		 fence/agents/ilo_mp/Makefile
		 fence/agents/intelmodular/Makefile
		 fence/agents/ipmilan/Makefile
		 fence/agents/ldom/Makefile
		 fence/agents/lib/Makefile
		 fence/agents/lpar/Makefile
		 fence/agents/manual/Makefile
		 fence/agents/mcdata/Makefile
		 fence/agents/nss_wrapper/Makefile
		 fence/agents/rackswitch/Makefile
		 fence/agents/rsa/Makefile
		 fence/agents/rsb/Makefile
		 fence/agents/sanbox2/Makefile
		 fence/agents/scsi/Makefile
		 fence/agents/virsh/Makefile
		 fence/agents/vixel/Makefile
		 fence/agents/vmware/Makefile
		 fence/agents/wti/Makefile
		 fence/agents/xcat/Makefile
		 fence/agents/xvm/Makefile
		 fence/agents/zvm/Makefile
		 fence/man/Makefile
		 doc/Makefile])

AC_OUTPUT
