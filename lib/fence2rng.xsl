<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="text" indent="no"/>

<xsl:param name="init-indent" select="'      '"/>
<xsl:param name="indent" select="'  '"/>


<!--
  helpers
  -->

<xsl:variable name="SP" select="' '"/>
<xsl:variable name="NL" select="'&#xA;'"/>
<xsl:variable name="Q" select="'&quot;'"/>
<xsl:variable name="TS" select="'&lt;'"/>
<xsl:variable name="TSc" select="'&lt;/'"/>
<xsl:variable name="TE" select="'&gt;'"/>
<xsl:variable name="TEc" select="'/&gt;'"/>

<xsl:template name="comment">
    <xsl:param name="text" select="''"/>
    <xsl:param name="indent" select="''"/>
    <xsl:if test="$indent != 'none'">
        <xsl:value-of select="concat($init-indent, $indent)"/>
    </xsl:if>
    <xsl:value-of select="concat($TS, '!-- ', $text, ' --',$TE)"/>
</xsl:template>

<xsl:template name="tag-start">
    <xsl:param name="name"/>
    <xsl:param name="attrs" select="''"/>
    <xsl:param name="indent" select="''"/>
    <xsl:if test="$indent != 'none'">
        <xsl:value-of select="concat($init-indent, $indent)"/>
    </xsl:if>
    <xsl:value-of select="concat($TS, $name)"/>
    <xsl:if test="$attrs != ''">
        <xsl:value-of select="concat($SP, $attrs)"/>
    </xsl:if>
    <xsl:value-of select="$TE"/>
</xsl:template>

<xsl:template name="tag-end">
    <xsl:param name="name"/>
    <xsl:param name="attrs" select="''"/>
    <xsl:param name="indent" select="''"/>
    <xsl:if test="$indent != 'none'">
        <xsl:value-of select="concat($init-indent, $indent)"/>
    </xsl:if>
    <xsl:value-of select="concat($TSc, $name)"/>
    <xsl:if test="$attrs != ''">
        <xsl:value-of select="concat($SP, $attrs)"/>
    </xsl:if>
    <xsl:value-of select="$TE"/>
</xsl:template>

<xsl:template name="tag-self">
    <xsl:param name="name"/>
    <xsl:param name="attrs" select="''"/>
    <xsl:param name="indent" select="''"/>
    <xsl:if test="$indent != 'none'">
        <xsl:value-of select="concat($init-indent, $indent)"/>
    </xsl:if>
    <xsl:value-of select="concat($TS, $name)"/>
    <xsl:if test="$attrs != ''">
        <xsl:value-of select="concat($SP, $attrs)"/>
    </xsl:if>
    <xsl:value-of select="$TEc"/>
</xsl:template>


<!--
  proceed
  -->

<xsl:template match="/resource-agent">
    <xsl:value-of select="$NL"/>

    <!-- (comment denoting the fence agent name) -->
    <xsl:call-template name="comment">
        <xsl:with-param name="text" select="@name"/>
    </xsl:call-template>
    <xsl:value-of select="$NL"/>

    <!-- group rha:name=... rha:description=... (start) -->
    <xsl:call-template name="tag-start">
        <xsl:with-param name="name" select="'group'"/>
        <xsl:with-param name="attrs" select="concat(
            'rha:name=',        $Q, @name,      $Q, $SP,
            'rha:description=', $Q, @shortdesc, $Q)"/>
    </xsl:call-template>
    <xsl:value-of select="$NL"/>

        <!-- optional (start) -->
        <xsl:call-template name="tag-start">
            <xsl:with-param name="name" select="'optional'"/>
            <xsl:with-param name="indent" select="$indent"/>
        </xsl:call-template>
        <xsl:value-of select="$NL"/>

            <!-- attribute name="option" -->
            <xsl:call-template name="tag-self">
                <xsl:with-param name="name" select="'attribute'"/>
                <xsl:with-param name="attrs" select="concat(
                    'name=', $Q, 'option', $Q)"/>
                <xsl:with-param name="indent" select="concat($indent, $indent)"/>
            </xsl:call-template>
            <xsl:value-of select="$SP"/>
            <!-- (comment mentioning that "option" is deprecated) -->
            <xsl:call-template name="comment">
                <xsl:with-param name="text">
                    <xsl:text>deprecated; for compatibility.  use "action"</xsl:text>
                </xsl:with-param>
                <xsl:with-param name="indent" select="'none'"/>
            </xsl:call-template>
            <xsl:value-of select="$NL"/>

        <!-- optional (end) -->
        <xsl:call-template name="tag-end">
            <xsl:with-param name="name" select="'optional'"/>
            <xsl:with-param name="indent" select="$indent"/>
        </xsl:call-template>
        <xsl:value-of select="$NL"/>

        <xsl:for-each select="parameters/parameter">
            <xsl:variable name="escapeddesc">
                <xsl:call-template name="escape_quot">
                    <xsl:with-param name="replace" select="shortdesc"/>
                </xsl:call-template>
        </xsl:variable>

            <!-- optional (start) -->
            <xsl:call-template name="tag-start">
                <xsl:with-param name="name" select="'optional'"/>
                <xsl:with-param name="indent" select="$indent"/>
            </xsl:call-template>
            <xsl:value-of select="$NL"/>

            <!-- attribute name=... rha:description=... -->
            <xsl:call-template name="tag-self">
                <xsl:with-param name="name" select="'attribute'"/>
                <xsl:with-param name="attrs" select="concat(
                    'name=',            $Q, @name,                      $Q, $SP,
                    'rha:description=', $Q, normalize-space($escapeddesc), $Q, $SP)"/>
                <xsl:with-param name="indent" select="concat($indent, $indent)"/>
            </xsl:call-template>
            <xsl:value-of select="$NL"/>

            <!-- optional (end) -->
            <xsl:call-template name="tag-end">
                <xsl:with-param name="name" select="'optional'"/>
                <xsl:with-param name="indent" select="$indent"/>
            </xsl:call-template>
            <xsl:value-of select="$NL"/>
        </xsl:for-each>

    <!-- group rha:name=... rha:description=... (end) -->
    <xsl:call-template name="tag-end">
        <xsl:with-param name="name" select="'group'"/>
    </xsl:call-template>
    <xsl:value-of select="$NL"/>

    <xsl:value-of select="$NL"/>
</xsl:template>

<xsl:template name="escape_quot">
    <xsl:param name="replace"/>
    <xsl:choose>
        <xsl:when test="contains($replace,'&quot;')">
            <xsl:value-of select="substring-before($replace,'&quot;')"/>
            <!-- escape quot-->
            <xsl:text>&amp;quot;</xsl:text>
            <xsl:call-template name="escape_quot">
                <xsl:with-param name="replace" select="substring-after($replace,'&quot;')"/>
            </xsl:call-template>
        </xsl:when>
    <xsl:otherwise>
        <xsl:value-of select="$replace"/>
    </xsl:otherwise>
    </xsl:choose>
    </xsl:template>

</xsl:stylesheet>
