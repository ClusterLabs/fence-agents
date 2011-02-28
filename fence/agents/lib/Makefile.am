MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fencing.py fencing_snmp.py

SRC			= fencing.py.py fencing_snmp.py.py

EXTRA_DIST		= $(SRC) fence2man.xsl

fencelibdir		= ${FENCEAGENTSLIBDIR}

fencelib_DATA		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET) *.pyc
