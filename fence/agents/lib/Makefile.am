MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fencing.py fencing_snmp.py XenAPI.py

SRC			= fencing.py.py fencing_snmp.py.py XenAPI.py.py

EXTRA_DIST		= $(SRC) fence2man.xsl fence2rng.xsl

fencelibdir		= ${FENCEAGENTSLIBDIR}

fencelib_DATA		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET) *.pyc
