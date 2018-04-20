<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version='1.0' xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:template match="/resource-agent">
[=#<xsl:value-of select="@name" />]
||='''<xsl:value-of select="@shortdesc" />''' =||='''<xsl:value-of select="@name" />''' =||
|| '''Name Of The Argument For STDIN''' || '''Name Of The Argument For Command-Line''' || '''Default Value''' ||'''Description''' ||
<xsl:apply-templates select="parameters/parameter" />
</xsl:template>

<xsl:template match="parameters/parameter">|| <xsl:value-of select="@name" /> || <xsl:value-of select="getopt/@mixed" /> || {{{<xsl:value-of select="content/@default" disable-output-escaping="yes"/>}}} || <xsl:value-of select="shortdesc" /> ||
</xsl:template>

</xsl:stylesheet>