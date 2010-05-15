<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
	<xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
	<xsl:template match="@*|node()">
		<!-- Copy everything -->
		<xsl:copy>
			<xsl:apply-templates select="@*|node()"/>
		</xsl:copy>
	</xsl:template>
	<xsl:template match="layout">
		<xsl:copy>
			<xsl:apply-templates select="@*|node()">
				<!-- Sort layout items in the visual order -->
				<xsl:sort select="@row" data-type="number"/>
				<xsl:sort select="@column" data-type="number"/>
			</xsl:apply-templates>
		</xsl:copy>
	</xsl:template>
	<xsl:template match="tabstops">
		<!-- Remove (i.e. do not copy) manual tab stops -->
	</xsl:template>
</xsl:stylesheet>
