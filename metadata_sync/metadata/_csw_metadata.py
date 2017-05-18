#!/usr/bin/env python

"""XML Metadata module

Author: Alex Ip (alex.ip@ga.gov.au)
"""

import xml.dom.minidom
import logging
import unicodedata
from _xml_metadata import XMLMetadata

logger = logging.getLogger('root.' + __name__)


class CSWMetadata(XMLMetadata):
    """Subclass of XMLMetadata to manage XML data pulled from a CSW source
    """
    # Class variable holding metadata type string
    _metadata_type_id = 'XML'
    _filename_pattern = '.*\.xml'  # Default RegEx for finding metadata file.

    def unicode_to_ascii(self, instring):
        """Convert unicode to char string if required and strip any leading/trailing whitespaces
        ToDO: Investigate whether we can just change the encoding of the DOM tree
        """
        result = instring
        if isinstance(result, unicode):
            result = unicodedata.normalize('NFKD', result).encode(
                'ascii', 'ignore').strip(""" "'\n\t""")
            return result

    def __init__(self, source=None, uses_attributes=False):
        """Instantiates CSWMetadata object. Overrides Metadata method
        """
        self._uses_attributes = uses_attributes  # Boolean flag indicating whether values are stored as tag attributes
        # Dict containing processing instruction name and value
        self.processing_instruction = {}
        # Dict containing any attributes when not self._uses_attributes
        self.document_attributes = {}
        XMLMetadata.__init__(self)  # Call inherited constructor

        if source:
            pass

    #=========================================================================
    # # Attempted fix for whitespace issue using PyXML. Caused problems with SceneDataset config XML
    # def toprettyxml_fixed (self, node, encoding='utf-8'):
    #     """
    #     Creates well-formatted XML without whitespaces
    #     """
    #     tmpStream = StringIO()
    #     PrettyPrint(node, stream=tmpStream, encoding=encoding)
    #     return tmpStream.getvalue()
    #=========================================================================

#    def _populate_dict_from_node(self, node, tree_dict, level=0):

# def _populate_node_from_dict(self, tree_dict, node, uses_attributes,
# owner_document=None, level=0):

#    def read_file(self, filename=None):

# def write_file(self, filename=None, uses_attributes=None,
# save_backup=False):

    def get_csw_metadata(self, csw_url):
        pass

    @property
    def uses_attributes(self):
        """Property returning a Boolean value indicating that values are stored in tag attributes rather than as text
        """
        return self._uses_attributes


def main():
    # Test data from file
    # LS7_ETM_OTH_P51_GALPGS01_092_085_20100315/scene01/LE7_20100315_092_085_L1T.xml
    TESTXML = """<?xml version="1.0" encoding="UTF-8" ?>
<EODS_DATASET>
    <MDRESOURCE>
        <MDFILEID></MDFILEID>
            <FILESIZE>842</FILESIZE>
            <RESOLUTIONINMETRES>50.000000000000 25.000000000000 12.500000000000</RESOLUTIONINMETRES>
            <CONSTRAINTID></CONSTRAINTID>
            <RESOURCESTATUS>COMPLETED</RESOURCESTATUS>
            <KEYWORDS></KEYWORDS>
            <TOPICCATEGORIES></TOPICCATEGORIES>
            <CITATION>
        <TITLE></TITLE>
        <ALTERNATETITLE>Landsat7 RCC-L1T 0920852010074</ALTERNATETITLE>
        <DATE>20111025T05:14:51</DATE>
        <DATETYPE>creation</DATETYPE>
                <EDITION></EDITION>
                <EDITIONDATE></EDITIONDATE>
                <ENTEREDBYRESPONSIBLEPARTY>
                    <INDIVIDUALNAME></INDIVIDUALNAME>
                    <ORGANISATIONNAME></ORGANISATIONNAME>
                    <POSITIONNAME></POSITIONNAME>
                    <ROLE></ROLE>
                </ENTEREDBYRESPONSIBLEPARTY>
                <UPDATEDBYRESPONSIBLEPARTY>
                    <INDIVIDUALNAME></INDIVIDUALNAME>
                    <ORGANISATIONNAME></ORGANISATIONNAME>
                    <POSITIONNAME></POSITIONNAME>
                    <ROLE></ROLE>
                </UPDATEDBYRESPONSIBLEPARTY>
                <OTHERCITATIONDETAILS></OTHERCITATIONDETAILS>
            </CITATION>
            <MDSTANDARDNAME>ANZLIC Metadata Profile: An Australian/New Zealand Profile of AS/NZS ISO 19115:2005, Geographic information - Metadata</MDSTANDARDNAME>
            <MDSTANDARDVERSION>1.1</MDSTANDARDVERSION>
            <PARENTID></PARENTID>
            <DATALANGUAGE>eng</DATALANGUAGE>
            <MDCONTACT>
        <INDIVIDUALNAME></INDIVIDUALNAME>
        <ORGANISATIONNAME></ORGANISATIONNAME>
        <POSITIONNAME></POSITIONNAME>
        <ROLE></ROLE>
            </MDCONTACT>
            <RESOURCETYPE>Processed Image</RESOURCETYPE>
            <CHARACTERSETCODE>utf8</CHARACTERSETCODE>
            <ABSTRACT>Landsat7 RCC-L1T</ABSTRACT>
            <PURPOSE></PURPOSE>
            <CREDIT></CREDIT>
            <HEIRACHYLEVEL>dataset</HEIRACHYLEVEL>
            <HEIRARCHYLEVELNAME></HEIRARCHYLEVELNAME>
            <ENVIRONMENTDESCRIPTION></ENVIRONMENTDESCRIPTION>
            <SPATIALREPRESENTATIONTYPE></SPATIALREPRESENTATIONTYPE>
            <SUPPLEMENTARYINFORMATION></SUPPLEMENTARYINFORMATION>
            <FORMAT>
        <FORMATNAME>FASTL7A</FORMATNAME>
        <FORMATVERSION></FORMATVERSION>
            </FORMAT>
        </MDRESOURCE>
    <EXEXTENT>
        <COORDINATEREFERENCESYSTEM></COORDINATEREFERENCESYSTEM>
        <EXTENTTYPE></EXTENTTYPE>
        <EXTENTDESCRIPTION></EXTENTDESCRIPTION>
        <UL_LAT>-35.0700000</UL_LAT>
        <UL_LONG>144.8700000</UL_LONG>
        <UR_LAT>-35.0700000</UR_LAT>
        <UR_LONG>147.5900000</UR_LONG>
        <LR_LAT>-37.0000000</LR_LAT>
        <LR_LONG>147.5900000</LR_LONG>
        <LL_LAT>-37.0000000</LL_LAT>
        <LL_LONG>144.8700000</LL_LONG>
        <WEST_BLONG>144.8700000</WEST_BLONG>
        <EAST_BLONG>147.5900000</EAST_BLONG>
        <NORTH_BLAT>-37.0000000</NORTH_BLAT>
        <SOUTH_BLAT>-35.0700000</SOUTH_BLAT>
        <TEMPORALEXTENTFROM>20100315 23:54:58</TEMPORALEXTENTFROM>
        <TEMPORALEXTENTTO>20100315 23:55:25</TEMPORALEXTENTTO>
        <VERTICALEXTENTMAX></VERTICALEXTENTMAX>
        <VERTICALEXTENTMIN></VERTICALEXTENTMIN>
        <VERTICALEXTENTUOM></VERTICALEXTENTUOM>
        <VERTICALEXTENTCRS></VERTICALEXTENTCRS>
        <VERTICALEXTENTDATUM></VERTICALEXTENTDATUM>
        <SCENECENTRELAT>-36.0459</SCENECENTRELAT>
        <SCENECENTRELONG>146.2550</SCENECENTRELONG>
  <TIMESERIESCOMPOSITINGINTERVAL></TIMESERIESCOMPOSITINGINTERVAL>
    </EXEXTENT>
    <DATAQUALITY>
        <SCOPELEVEL>dataset</SCOPELEVEL>
        <SCOPELEVELDESCRIPTION></SCOPELEVELDESCRIPTION>
        <LINEAGE>
            <STATEMENT>Resampling=CC,RadiometricCorrection=CPF,Orientation=NUP,LAM_version=6.2.1,LACS_version=6.3.0,LPS_version=8.2.1,LPGS_version=11.4.0</STATEMENT>
          <PROCESSINGSTEP>
   <ALGORITHMCITATION>
     <TITLE>Pinkmatter Landsat Processor</TITLE>
     <EDITION>3.2.1518</EDITION>
   </ALGORITHMCITATION>
   </PROCESSINGSTEP>
            <LINEAGESOURCE>
                <MDFILEID></MDFILEID>
          <SOURCERESOURCEID></SOURCERESOURCEID>
                <SOURCECITATION>
                    <TITLE></TITLE>
                    <DATE>20111025T05:14:51</DATE>
                    <DATETYPE>creation</DATETYPE>
               <ENTEREDBYRESPONSIBLEPARTY>
                        <INDIVIDUALNAME></INDIVIDUALNAME>
                        <ORGANISATIONNAME></ORGANISATIONNAME>
                        <POSITIONNAME></POSITIONNAME>
                        <ROLE></ROLE>
               </ENTEREDBYRESPONSIBLEPARTY>
                </SOURCECITATION>
                <DESCRIPTION></DESCRIPTION>
            <SOURCEREFERENCESYSTEM></SOURCEREFERENCESYSTEM>
            <SOURCESCALE></SOURCESCALE>
            <SOURCESTEP></SOURCESTEP>
            <PROCESSINGLEVEL></PROCESSINGLEVEL>
            </LINEAGESOURCE>
        </LINEAGE>
        <DQELEMENT>
            <MEASURENAME>Automatically Generated Report</MEASURENAME>
            <QUANTATIVEVALUE>1</QUANTATIVEVALUE>
            <QUANTATIVEVALUEUNIT>text</QUANTATIVEVALUEUNIT>
        </DQELEMENT>
    </DATAQUALITY>
    <IMAGEDESCRIPTION>
        <ILLUMINATIONELEVATIONANGLE>41.5610274</ILLUMINATIONELEVATIONANGLE>
        <ILLUMINATIONELEVATIONAZIMUTH>53.7730377</ILLUMINATIONELEVATIONAZIMUTH>
         <VIEWINGINCIDENCEANGLEXTRACK></VIEWINGINCIDENCEANGLEXTRACK>
        <VIEWINGINCIDENCEANGLELONGTRACK></VIEWINGINCIDENCEANGLELONGTRACK>
        <CLOUDCOVERPERCENTAGE></CLOUDCOVERPERCENTAGE>
        <CLOUDCOVERDETAILS></CLOUDCOVERDETAILS>
        <SENSOROPERATIONMODE>BUMPER</SENSOROPERATIONMODE>
        <BANDGAIN>HHHLHLHHL</BANDGAIN>
        <BANDSAVAILABLE>123456678</BANDSAVAILABLE>
        <SATELLITEREFERENCESYSTEM_X>092</SATELLITEREFERENCESYSTEM_X>
        <SATELLITEREFERENCESYSTEM_Y>085</SATELLITEREFERENCESYSTEM_Y>
        <IMAGECONDITION></IMAGECONDITION>
        <PROCESSINGTYPECD>L1T</PROCESSINGTYPECD>
      <BEARING></BEARING>
    </IMAGEDESCRIPTION>
    <BROWSEGRAPHIC>
        <FILENAME></FILENAME>
        <FILEDESCRIPTION></FILEDESCRIPTION>
        <FILETYPE></FILETYPE>
        <SAMPLEPIXELRESOLUTION></SAMPLEPIXELRESOLUTION>
        <BLUEBAND></BLUEBAND>
        <GREENORGREYBAND></GREENORGREYBAND>
        <REDBAND></REDBAND>
    </BROWSEGRAPHIC>
    <ACQUISITIONINFORMATION>
        <PLATFORMNAME>Landsat-7</PLATFORMNAME>
        <INSTRUMENTNAME>ETM+</INSTRUMENTNAME>
        <INSTRUMENTYPE>Multi-spectral</INSTRUMENTYPE>
        <MISSIONNAME>Landsat Data Continuity Mission (LDCM)</MISSIONNAME>
        <EVENT>
            <TIME>2010-03-15</TIME>
            <AOS>2010-03-15</AOS>
            <LOS>2010-03-15</LOS>
            <ORBITNUMBER></ORBITNUMBER>
            <CYCLENUMBER></CYCLENUMBER>
            <PASSSTATUS></PASSSTATUS>
            <NUMBERSCENESINPASS></NUMBERSCENESINPASS>
            <COLLECTIONSITE></COLLECTIONSITE>
            <ANTENNA></ANTENNA>
            <HEADING></HEADING>
            <SEQUENCE></SEQUENCE>
            <TRIGGER></TRIGGER>
            <CONTEXT></CONTEXT>
        </EVENT>
    </ACQUISITIONINFORMATION>
    <GRIDSPATIALREPRESENTATION>
        <NUMBEROFDIMENSIONS>2</NUMBEROFDIMENSIONS>
        <TRANSFORMATIONPARAMETERAVAILABILITY></TRANSFORMATIONPARAMETERAVAILABILITY>
        <CELLGEOMETRY></CELLGEOMETRY>
        <DIMENSION_X>
            <NAME>sample</NAME>
            <SIZE>5441 10881 21761</SIZE>
            <RESOLUTION>0.000500 0.000250 0.000125</RESOLUTION>
        </DIMENSION_X>
        <DIMENSION_Y>
            <NAME>line</NAME>
            <SIZE>3861 7721 15441</SIZE>
            <RESOLUTION>0.000500 0.000250 0.000125</RESOLUTION>
        </DIMENSION_Y>
        <GEORECTIFIED>
            <CHECKPOINTAVAILABILITY></CHECKPOINTAVAILABILITY>
            <CHECKPOINTDESCRIPTION></CHECKPOINTDESCRIPTION>
            <POINTINPIXEL></POINTINPIXEL>
              <GEOREFULPOINT_X></GEOREFULPOINT_X>
              <GEOREFULPOINT_Y></GEOREFULPOINT_Y>
              <GEOREFULPOINT_Z></GEOREFULPOINT_Z>
              <GEOREFURPOINT_X></GEOREFURPOINT_X>
              <GEOREFURPOINT_Y></GEOREFURPOINT_Y>
              <GEOREFURPOINT_Z></GEOREFURPOINT_Z>
              <GEOREFLLPOINT_X></GEOREFLLPOINT_X>
              <GEOREFLLPOINT_Y></GEOREFLLPOINT_Y>
              <GEOREFLLPOINT_Z></GEOREFLLPOINT_Z>
              <GEOREFLRPOINT_X></GEOREFLRPOINT_X>
              <GEOREFLRPOINT_Y></GEOREFLRPOINT_Y>
              <GEOREFLRPOINT_Z></GEOREFLRPOINT_Z>
              <CENTREPOINT_X></CENTREPOINT_X>
              <CENTREPOINT_Y></CENTREPOINT_Y>
              <ELLIPSOID>WGS84</ELLIPSOID>
              <DATUM>WGS84</DATUM>
              <ZONE></ZONE>
              <PROJECTION>EQR</PROJECTION>
            <COORDINATEREFERENCESYSTEM></COORDINATEREFERENCESYSTEM>
        </GEORECTIFIED>
    </GRIDSPATIALREPRESENTATION>
</EODS_DATASET>"""

    # Instantiate empty MTLMetadata object and parse test string (strip all
    # EOLs first)
    xml_object = CSWMetadata()
    xml_object._populate_dict_from_node(xml.dom.minidom.parseString(TESTXML.translate(None, '\n')),
                                        xml_object.metadata_dict)
    assert xml_object.metadata_dict, 'No metadata_dict created'
    assert xml_object.tree_to_list(), 'Unable to create list from metadata_dict'
    assert xml_object.get_metadata('EODS_DATASET,ACQUISITIONINFORMATION,PLATFORMNAME'.split(
        ',')), 'Unable to find value for key L1_METADATA_FILE,PRODUCT_METADATA,SPACECRAFT_ID'
    assert xml_object.get_metadata('...,PLATFORMNAME'.split(
        ',')), 'Unable to find value for key ...,SPACECRAFT_ID'
    assert not xml_object.get_metadata('RUBBERCHICKEN'.split(
        ',')), 'Found nonexistent key RUBBERCHICKEN'
    xml_object.set_metadata_node(
        'EODS_DATASET,ACQUISITIONINFORMATION,PLATFORMNAME'.split(','), 'Rubber Chicken')
    assert xml_object.get_metadata('...,PLATFORMNAME'.split(
        ',')), 'Unable to change ...,SPACECRAFT_ID to "Rubber Chicken"'
    xml_object.merge_metadata_dicts(
        {'RUBBERCHICKEN': 'Rubber Chicken'}, xml_object.metadata_dict)
    assert xml_object.get_metadata('RUBBERCHICKEN'.split(
        ',')), 'Unable to find value for key RUBBERCHICKEN'
    xml_object.delete_metadata('RUBBERCHICKEN'.split(','))
    assert not xml_object.get_metadata('RUBBERCHICKEN'.split(
        ',')), 'Found value for key RUBBERCHICKEN'
    print xml_object.tree_to_list()
if __name__ == '__main__':
    main()
