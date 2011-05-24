MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fencing.py fencing_snmp.py

if BUILD_XENAPILIB
TARGET			+= XenAPI.py
endif

SRC			= fencing.py.py fencing_snmp.py.py XenAPI.py.py

EXTRA_DIST		= $(SRC) fence2man.xsl fence2rng.xsl

fencelibdir		= ${FENCEAGENTSLIBDIR}

fencelib_DATA		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET) *.pyc
