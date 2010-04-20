MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fencing.py fencing_snmp.py

EXTRA_DIST		= fencing.py.py fencing_snmp.py.py fence2man.xsl

fencelibdir		= ${FENCEAGENTSLIBDIR}

fencelib_DATA		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET) *.pyc
