<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="text" indent="yes"/>
<xsl:template name="capitalize">
	<xsl:param name="value"/>
	<xsl:variable name="normalized" select="translate($value, '_abcdefghijklmnopqrstuvwrxyz', '-ABCDEFGHIJKLMNOPQRSTUVWRXYZ')"/>
	<xsl:value-of select="$normalized"/>
</xsl:template>
<xsl:template match="/resource-agent">
      &lt;!-- <xsl:value-of select="@name"/> --&gt;
      &lt;group&gt;
        &lt;optional&gt;
          &lt;attribute name="option"/&gt; &lt;!-- deprecated; for compatibility.  use "action" --&gt;
        &lt;/optional&gt;<xsl:for-each select="parameters/parameter">
	<xsl:choose><xsl:when test="@required = 1 or @primary = 1">
        &lt;attribute name="<xsl:value-of select="@name"/>" rha:description="<xsl:value-of select="normalize-space(shortdesc)"/>" /&gt;</xsl:when><xsl:otherwise>
        &lt;optional&gt;
          &lt;attribute name="<xsl:value-of select="@name"/>" rha:description="<xsl:value-of select="normalize-space(shortdesc)"/>" /&gt;
        &lt;/optional&gt;</xsl:otherwise>
		</xsl:choose></xsl:for-each>
      &lt;/group&gt;

</xsl:template>
</xsl:stylesheet>
