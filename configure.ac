# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.63])

AC_INIT([fence-agents],
	m4_esyscmd([make/git-version-gen .tarball-version]),
	[linux-cluster@redhat.com])

AM_INIT_AUTOMAKE([-Wno-portability dist-bzip2 dist-xz])

LT_PREREQ([2.2.6])
LT_INIT

AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([fence/agents/lib/fencing.py.py])
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
AC_PROG_AWK
AC_PROG_CXX
AC_PROG_RANLIB

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

# Checks for header files.
AC_CHECK_HEADERS([arpa/inet.h fcntl.h libintl.h limits.h netdb.h stddef.h sys/socket.h sys/time.h syslog.h])

# Checks for typedefs, structures, and compiler characteristics.
AC_C_INLINE
AC_TYPE_SIZE_T
AC_TYPE_SSIZE_T
AC_TYPE_UINT32_T

# Checks for library functions.
AC_FUNC_FORK
AC_FUNC_MALLOC
AC_CHECK_FUNCS([alarm atexit bzero dup2 memmove memset select socket strcasecmp strchr strdup strerror strtol])

# local options
AC_ARG_ENABLE([debug],
	[  --enable-debug          enable debug build. ],
	[ default="no" ])

AC_ARG_WITH([fenceagentslibdir],
	[  --with-fenceagentslibdir=PATH
                          installation path for fence library. ],
	[ FENCEAGENTSLIBDIR="$withval" ],
	[ FENCEAGENTSLIBDIR="${datadir}/fence" ])

AC_ARG_WITH([snmpbin],
	[  --with-snmpbin=PATH
                          path to snmp binaries (snmpwalk/get). ],
	[ SNMPBIN="$withval" ],
	[ SNMPBIN="${bindir}" ])

AC_ARG_WITH([default-config-dir],
	[  --with-default-config-dir=DIR
			  cluster config directory. ],
	[ DEFAULT_CONFIG_DIR="$withval" ],
	[ DEFAULT_CONFIG_DIR="$sysconfdir/cluster" ])

AC_ARG_WITH([default-config-file],
	[  --with-default-config-file=FILE
			  cluster config file. ],
	[ DEFAULT_CONFIG_FILE="$withval" ],
	[ DEFAULT_CONFIG_FILE="cluster.conf" ])

AC_ARG_WITH([agents],
	[  --with-agents=LIST
                          list of agents to build/ship (default: all). ],
	[ AGENTS_LIST="$withval" ],
	[ AGENTS_LIST="all" ])

if test "x$AGENTS_LIST" = x; then
	AC_ERROR([No agents selected])
fi

if test "x$AGENTS_LIST" != xall; then
	for j in $AGENTS_LIST; do
		if ! test -d fence/agents/$j; then
			AC_ERROR([Agent $j does not exists])
		fi
	done
fi

if test "x$AGENTS_LIST" = xall; then
	AGENTS_LIST=`find $srcdir/fence/agents -mindepth 2 -maxdepth 2 -name Makefile.am -printf '%h ' | sed -e 's#'$srcdir'/fence/agents/##g' -e 's#lib ##g' -e 's#nss_wrapper ##g'`
fi

XENAPILIB=0
if echo "$AGENTS_LIST" | grep -q xenapi; then
	XENAPILIB=1
fi

## random vars

LOGDIR=${localstatedir}/log/cluster
CLUSTERVARRUN=${localstatedir}/run/cluster
CLUSTERDATA=${datadir}/cluster

AC_PYTHON_MODULE(suds, 1)
AC_PYTHON_MODULE(pexpect, 1)
AC_PYTHON_MODULE(pycurl, 1)
AC_PYTHON_MODULE(requests, 1)

## path to 3rd-party binaries
AC_PATH_PROG([IPMITOOL_PATH], [ipmitool], [/usr/bin/ipmitool])
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
AC_PATH_PROG([SUDO_PATH], [sudo], [/usr/bin/sudo])

## do subst

AC_SUBST([DEFAULT_CONFIG_DIR])
AC_DEFINE_UNQUOTED([DEFAULT_CONFIG_DIR], "$(eval echo ${DEFAULT_CONFIG_DIR})",
		   [Default config directory])

AC_SUBST([DEFAULT_CONFIG_FILE])
AC_DEFINE_UNQUOTED([DEFAULT_CONFIG_FILE], "$(eval echo ${DEFAULT_CONFIG_FILE})",
		   [Default config file])

AC_SUBST([LOGDIR])
AC_DEFINE_UNQUOTED([LOGDIR], "$(eval echo ${LOGDIR})",
		   [Default logging directory])

AC_SUBST([CLUSTERVARRUN])
AC_DEFINE_UNQUOTED([CLUSTERVARRUN], "$(eval echo ${CLUSTERVARRUN})",
		   [Default cluster var/run directory])

AC_SUBST([CLUSTERDATA])
AC_SUBST([FENCEAGENTSLIBDIR])
AC_SUBST([SNMPBIN])
AC_SUBST([AGENTS_LIST])
AM_CONDITIONAL(BUILD_XENAPILIB, test $XENAPILIB -eq 1)

AC_SUBST([IPMITOOL_PATH])
AC_SUBST([AMTTOOL_PATH])
AC_SUBST([COROSYNC_CMAPCTL_PATH])
AC_SUBST([SG_PERSIST_PATH])
AC_SUBST([SG_TURS_PATH])
AC_SUBST([VGS_PATH])

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
		 fence/agents/amt/Makefile 
		 fence/agents/bladecenter/Makefile
		 fence/agents/brocade/Makefile
		 fence/agents/cisco_mds/Makefile
		 fence/agents/cisco_ucs/Makefile
		 fence/agents/docker/Makefile
		 fence/agents/drac/Makefile
		 fence/agents/drac5/Makefile
		 fence/agents/dummy/Makefile
		 fence/agents/eaton_snmp/Makefile
		 fence/agents/emerson/Makefile
		 fence/agents/eps/Makefile
		 fence/agents/hpblade/Makefile
		 fence/agents/ibmblade/Makefile
		 fence/agents/ipdu/Makefile
		 fence/agents/ifmib/Makefile
		 fence/agents/ilo/Makefile
		 fence/agents/ilo_moonshot/Makefile
		 fence/agents/ilo_mp/Makefile
		 fence/agents/ilo_ssh/Makefile
		 fence/agents/intelmodular/Makefile
		 fence/agents/ipmilan/Makefile
		 fence/agents/kdump/Makefile
		 fence/agents/ldom/Makefile
		 fence/agents/lib/Makefile
		 fence/agents/lpar/Makefile
		 fence/agents/manual/Makefile
		 fence/agents/mpath/Makefile
		 fence/agents/netio/Makefile
		 fence/agents/ovh/Makefile
		 fence/agents/pve/Makefile
		 fence/agents/raritan/Makefile
		 fence/agents/rhevm/Makefile
		 fence/agents/rsa/Makefile
		 fence/agents/rsb/Makefile
		 fence/agents/sanbox2/Makefile
		 fence/agents/scsi/Makefile
		 fence/agents/virsh/Makefile
		 fence/agents/vmware/Makefile
		 fence/agents/vmware_soap/Makefile
		 fence/agents/wti/Makefile
		 fence/agents/xenapi/Makefile
		 fence/agents/hds_cb/Makefile
		 fence/agents/zvm/Makefile
		 doc/Makefile])

AC_OUTPUT
