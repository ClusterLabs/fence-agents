<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="text" indent="no"/>
<xsl:template match="parameter">
<xsl:param name="show" />
.TP
<xsl:if test="$show = 'getopt'">.B <xsl:value-of select="getopt/@mixed" /></xsl:if>
<xsl:if test="$show = 'stdin'">.B <xsl:value-of select="@name"/></xsl:if>
. 
<xsl:value-of select="normalize-space(shortdesc)"/>
<xsl:if test="count(content/option) > 1">
	<xsl:text> (</xsl:text>
	<xsl:for-each select="content/option">
		<xsl:value-of select="@value" />
		<xsl:if test="position() &lt; last()">
			<xsl:text>|</xsl:text>
		</xsl:if>
	</xsl:for-each>
	<xsl:text>)</xsl:text>
</xsl:if>
<xsl:if test="not(content/@default)"><xsl:if test="@required = 1"> This parameter is always required.</xsl:if></xsl:if>
<xsl:if test="content/@default"> (Default Value: <xsl:value-of select="content/@default"/>)</xsl:if>
</xsl:template>

<xsl:template match="action">
.TP
\fB<xsl:value-of select="@name"/> \fP
<xsl:choose>
<xsl:when test="@name = 'on'">Power on machine.</xsl:when>
<xsl:when test="@name = 'off'">Power off machine.</xsl:when>
<xsl:when test="@name = 'enable'">Enable fabric access.</xsl:when>
<xsl:when test="@name = 'disable'">Disable fabric access.</xsl:when>
<xsl:when test="@name = 'reboot'">Reboot machine.</xsl:when>
<xsl:when test="@name = 'diag'">Pulse a diagnostic interrupt to the processor(s).</xsl:when>
<xsl:when test="@name = 'monitor'">Check the health of fence device</xsl:when>
<xsl:when test="@name = 'metadata'">Display the XML metadata describing this resource.</xsl:when>
<xsl:when test="@name = 'list'">List available plugs with aliases/virtual machines if there is support for more then one device. Returns N/A otherwise.</xsl:when>
<xsl:when test="@name = 'list-status'">List available plugs with aliases/virtual machines and their power state if it can be obtained without additional commands.</xsl:when>
<xsl:when test="@name = 'status'">This returns the status of the plug/virtual machine.</xsl:when>
<xsl:when test="@name = 'validate-all'">Validate if all required parameters are entered.</xsl:when>
<!-- Ehhh -->
<xsl:otherwise> The operational behavior of this is not known.</xsl:otherwise>
</xsl:choose>
</xsl:template>

<xsl:template match="/resource-agent">
.TH FENCE_AGENT 8 2009-10-20 "<xsl:value-of select="@name"/> (Fence Agent)"
.SH NAME
<xsl:value-of select="@name" /> - <xsl:value-of select="@shortdesc" />
<xsl:for-each select="symlink">
.P
<xsl:value-of select="@name" /> - <xsl:value-of select="@shortdesc" /> (symlink)
</xsl:for-each>
.SH DESCRIPTION
.P
<xsl:value-of select="longdesc"/>
.P
<xsl:value-of select="@name" /> accepts options on the command line as well
as from stdin. Fenced sends parameters through stdin when it execs the
agent. <xsl:value-of select="@name" /> can be run by itself with command
line options.  This is useful for testing and for turning outlets on or off
from scripts.
<xsl:if test="vendor-url">
Vendor URL: <xsl:value-of select="vendor-url" />
</xsl:if>
.SH PARAMETERS
<xsl:apply-templates select="parameters"><xsl:with-param name="show">getopt</xsl:with-param></xsl:apply-templates>
.SH ACTIONS
<xsl:apply-templates select="actions"/>
.SH STDIN PARAMETERS
<xsl:apply-templates select="parameters"><xsl:with-param name="show">stdin</xsl:with-param></xsl:apply-templates>
</xsl:template>
</xsl:stylesheet>
