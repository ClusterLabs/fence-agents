MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fencing.py fencing_snmp.py azure_fence.py

if BUILD_XENAPILIB
TARGET			+= XenAPI.py
endif

SRC			= fencing.py.py fencing_snmp.py.py XenAPI.py.py azure_fence.py.py check_used_options.py

XSL			= fence2man.xsl fence2rng.xsl fence2wiki.xsl

FASRNG			= fence.rng.head fence.rng.tail metadata.rng

EXTRA_DIST		= $(SRC) $(XSL) $(FASRNG)

fencelibdir		= ${FENCEAGENTSLIBDIR}

fencelib_DATA		= $(TARGET)

rngdir			= ${CLUSTERDATA}/relaxng

rng_DATA		= $(XSL) $(FASRNG)

include $(top_srcdir)/make/fencebuild.mk

clean-man:
