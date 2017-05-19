#!/usr/bin/env python

"""XML Metadata module

Author: Alex Ip (alex.ip@ga.gov.au)
"""

import xml.dom.minidom
import logging
import os
import re
import unicodedata
from _metadata import Metadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Initial logging level for this module


class XMLMetadata(Metadata):
    """Subclass of Metadata to manage XML data
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
        """Instantiates XMLMetadata object. Overrides Metadata method
        """
        self._uses_attributes = uses_attributes  # Boolean flag indicating whether values are stored as tag attributes
        # Dict containing processing instruction name and value
        self.processing_instruction = {}
        # Dict containing any attributes when not self._uses_attributes
        self.document_attributes = {}
        Metadata.__init__(self, source)  # Call inherited constructor

    def _populate_dict_from_node(self, node, tree_dict, level=0):
        """Private recursive function to populate a nested dict from DOM tree or element node
        Exposed to allow unit testing using a DOM tree constructed from a string
        Arguments:
            node: xml.dom.Node object to traverse
            tree_dict: nested dict structure to hold result
        """
        def set_node_value(node_dict, key, value):
            '''Sets node_dict[key] to value when node_dict[key] doesn't already exist, otherwise appends comma-separated value
            '''
            # TODO: Do something better than comma-separated text - one-way
            # translation only: will break if text contains commas
            existing_value = node_dict.get(key)
            if existing_value:  # Existing leaf node found - repeated xpath
                if value:
                    # Append new value to comma-separated list
                    node_dict[key] = existing_value + ', ' + value
            else:  # No existing leaf node - new xpath
                node_dict[key] = value

        # Traverse all non-text nodes
        for child_node in [
                x for x in node.childNodes if x.nodeType == xml.dom.minidom.Node.ELEMENT_NODE]:
            nodeName = child_node.nodeName
            if nodeName:
                nodeName = self.unicode_to_ascii(nodeName)

                logger.debug('%sDOM Node name = %s, Node type = %s, Child nodes = %s, Attributes = %s',
                             '  ' * level, nodeName, child_node.nodeType, child_node.childNodes, child_node.attributes)

                subtree_dict = tree_dict.get(nodeName) or {}
                if child_node.childNodes:  # Recursive call to check for non-text child nodes
                    self._populate_dict_from_node(
                        child_node, subtree_dict, level + 1)

                logger.debug('%s  subtree_dict = %s',
                             '  ' * level, subtree_dict)
                if child_node.attributes:
                    logger.debug('%s  Child node attribute count = %s',
                                 '  ' * level, len(child_node.attributes))

                # Not a leaf node - sub-nodes found
                if subtree_dict and not tree_dict.get(nodeName):
                    tree_dict[nodeName] = subtree_dict

                elif child_node.attributes:  # Leaf node - values held in attributes
                    self._uses_attributes = True  # Remember that attributes are being used for this file

                    subtree_dict = tree_dict.get(nodeName) or {}
                    tree_dict[nodeName] = subtree_dict
                    level += 1
                    for attr_index in range(len(child_node.attributes)):
                        attribute = child_node.attributes.item(attr_index)
                        logger.debug('%s  Attribute: %s = %s', '  ' *
                                     level, attribute.name, attribute.value)
                        set_node_value(subtree_dict, self.unicode_to_ascii(
                            attribute.name), self.unicode_to_ascii(attribute.value))

                    # Leaf node - value held in child text node
                    if child_node.childNodes and child_node.childNodes[
                            0].nodeType == xml.dom.minidom.Node.TEXT_NODE:
                        node_value = self.unicode_to_ascii(
                            child_node.childNodes[0].nodeValue)
                        # TODO: Do something better than using 'TEXT' as key
                        set_node_value(subtree_dict, 'TEXT', node_value)
                    level -= 1

                # Leaf node - value held in child text node
                elif child_node.childNodes and child_node.childNodes[0].nodeType == xml.dom.minidom.Node.TEXT_NODE:
                    # Take value of first text child node
                    node_value = self.unicode_to_ascii(
                        child_node.childNodes[0].nodeValue)
                    logger.debug(
                        '%s  Node value = %s from text child node', '  ' * level, node_value)
                    set_node_value(tree_dict, nodeName, node_value)
                elif not child_node.childNodes:  # Empty leaf node
                    tree_dict[nodeName] = ''

    def _populate_node_from_dict(
            self, tree_dict, node, uses_attributes, owner_document=None, level=0):
        """Private recursive function to populate a nested dict from DOM tree or element node
        Exposed to allow unit testing using a DOM tree constructed from a string
        Arguments:
            tree_dict: nested dict structure to traverse
            node: xml.dom.Node object to hold result
            uses_attributes: Boolean flag indicating whether to write values to tag attributes
        """
        # TODO: Handle delimited lists as repeated xpaths
        owner_document = owner_document or node

        for node_name in sorted(tree_dict.keys()):
            child_item = tree_dict[node_name]
            assert child_item is not None, node_name + \
                ' node is empty - must hold either a string or subtree dict'
            if isinstance(child_item, dict):  # Subtree - descend to next level
                logger.debug('%sElement Node %s', '  ' * level, node_name)
                child_node = xml.dom.minidom.Element(node_name)
                child_node.ownerDocument = owner_document
                node.appendChild(child_node)

                self._populate_node_from_dict(
                    child_item, child_node, uses_attributes, owner_document, level + 1)

            else:  # Leaf node - store node value
                if child_item is None:
                    child_item = ''
                assert isinstance(child_item, str), node_name + \
                    ' node is not a string'
                if uses_attributes:  # Store value in attribute
                    logger.debug('%sAttribute for %s = %s', '  ' *
                                 level, node_name, repr(child_item))
                    node.setAttribute(node_name, child_item)
                else:  # Store value in child text node
                    logger.debug('%sText Child Node for %s = %s',
                                 '  ' * level, node_name, repr(child_item))

                    child_node = xml.dom.minidom.Element(node_name)
                    child_node.ownerDocument = owner_document
                    node.appendChild(child_node)

                    # Only add text node if value is non-empty
                    if child_item:
                        text_node = xml.dom.minidom.Text()
                        text_node.ownerDocument = owner_document
                        text_node.nodeValue = child_item
                        child_node.appendChild(text_node)

    def read_file(self, filename=None):
        """Function to parse an XML metadata file and store the results in self._metadata_dict
        Argument:
            filename: XML Metadata file to be parsed and stored
        Returns:
            nested dict containing metadata
        """
        logger.debug('read_file(%s) called', filename)

        filename = filename or self._filename
        assert filename, 'Filename must be specified'

        logger.debug('Parsing XML file %s', filename)

        # Open XML document using minidom parser
        dom_tree = xml.dom.minidom.parse(filename)

        # Remember any processing instruction node
        for node in dom_tree.childNodes:
            if node.nodeType == xml.dom.minidom.Node.PROCESSING_INSTRUCTION_NODE:
                processing_instruction_node = node
                logger.debug('Processing Instruction Node found: Name = %s, Value = %s',
                             processing_instruction_node.nodeName, processing_instruction_node.nodeValue)
                self.processing_instruction[
                    'name'] = processing_instruction_node.nodeName
                self.processing_instruction[
                    'value'] = processing_instruction_node.nodeValue
            elif node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:  # Root node has attributes
                for attr_index in range(len(node.attributes)):
                    attribute = node.attributes.item(attr_index)
                    logger.debug('Document Attribute: %s = %s',
                                 attribute.name, attribute.value)
                    self.document_attributes[self.unicode_to_ascii(
                        attribute.name)] = self.unicode_to_ascii(attribute.value)

        # Create nested dict from DOM tree
        self._populate_dict_from_node(dom_tree, self._metadata_dict)
        self._filename = filename

        return self._metadata_dict

    def write_file(self, filename=None, uses_attributes=None,
                   save_backup=False):
        """Function write the metadata contained in self._metadata_dict to an XML file
        Argument:
            filename: Metadata file to be written
            uses_attributes: Boolean flag indicating whether to write values to tag attributes
        """
        logger.debug('write_file(%s) called', filename)

        filename = filename or self._filename
        assert filename, 'Filename must be specified'

        # Allow values to be stored as attributes
        if uses_attributes is None:
            uses_attributes = self._uses_attributes

        if save_backup and os.path.exists(filename + '.bck'):
            os.remove(filename + '.bck')

        if os.path.exists(filename):
            if save_backup:
                os.rename(filename, filename + '.bck')
            else:
                os.remove(filename)

        # Open XML document
        try:
            outfile = open(filename, 'w')
            assert outfile is not None, 'Unable to open XML file ' + filename + ' for writing'

            logger.debug('Writing XML file %s', filename)

            dom_tree = xml.dom.minidom.Document()

            # Write any processing instruction node
            if self.processing_instruction:
                processing_instruction_node = xml.dom.minidom.ProcessingInstruction(
                    self.processing_instruction['name'], self.processing_instruction['value'])
                processing_instruction_node.ownerDocument = dom_tree
                dom_tree.appendChild(processing_instruction_node)

            # Open XML document using minidom parser
            self._populate_node_from_dict(
                self._metadata_dict, dom_tree, uses_attributes)

            # Set root node attributes if required
            if self.document_attributes:
                root_node = [node for node in dom_tree.childNodes if node.nodeType ==
                             xml.dom.minidom.Node.ELEMENT_NODE][0]
                for attribute_name in self.document_attributes.keys():
                    root_node.setAttribute(
                        attribute_name, self.document_attributes[attribute_name])

#            outfile.write(dom_tree.toxml(encoding='utf-8'))
#            outfile.write(dom_tree.toprettyxml(encoding='utf-8'))
# outfile.write(self.toprettyxml_fixed(node, encoding='utf-8')) # PyXML
# required

            #==================================================================
            # # Strip all tabs and EOLs from around values
            # outfile.write(re.sub('(\<\w*[^/]\>)\n(\t+\n)*(\t*)([^<>\n]*)\n\t*\n*(\t+)(\</\w+\>)',
            #                      '\\1\\4\\6',
            #                      dom_tree.toprettyxml(encoding='utf-8')
            #                      )
            #               )
            #==================================================================

            # Strip all tabs and EOLs from around values, remove all empty
            # lines
            outfile.write(re.sub('\>(\s+)(\n\t*)\<',
                                 '>\\2<',
                                 re.sub('(\<\w*[^/]\>)\n(\t*\n)*(\t*)([^<>\n]*)\n\t*\n*(\t+)(\</\w+\>)',
                                        '\\1\\4\\6',
                                        dom_tree.toprettyxml(encoding='utf-8')
                                        )
                                 )
                          )

        finally:
            outfile.close()

    def read_string(self, xml_string):
        self._populate_dict_from_node(xml.dom.minidom.parseString(
            xml_string.translate(None, '\n')), self._metadata_dict)

    @property
    def uses_attributes(self):
        """Property returning a Boolean value indicating that values are stored in tag attributes rather than as text
        """
        return self._uses_attributes


def main():
    # Test data from file
    # LS7_ETM_OTH_P51_GALPGS01_092_085_20100315/scene01/LE7_20100315_092_085_L1T.xml
    TESTXML = """<mdb:MD_Metadata xmlns:mdb="http://standards.iso.org/iso/19115/-3/mdb/1.0" xmlns:cit="http://standards.iso.org/iso/19115/-3/cit/1.0" xmlns:gco="http://standards.iso.org/iso/19115/-3/gco/1.0" xmlns:gcx="http://standards.iso.org/iso/19115/-3/gcx/1.0" xmlns:gex="http://standards.iso.org/iso/19115/-3/gex/1.0" xmlns:lan="http://standards.iso.org/iso/19115/-3/lan/1.0" xmlns:mcc="http://standards.iso.org/iso/19115/-3/mcc/1.0" xmlns:mco="http://standards.iso.org/iso/19115/-3/mco/1.0" xmlns:mmi="http://standards.iso.org/iso/19115/-3/mmi/1.0" xmlns:mrd="http://standards.iso.org/iso/19115/-3/mrd/1.0" xmlns:mri="http://standards.iso.org/iso/19115/-3/mri/1.0" xmlns:mrl="http://standards.iso.org/iso/19115/-3/mrl/1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:geonet="http://www.fao.org/geonetwork" xsi:schemaLocation="http://standards.iso.org/iso/19115/-3/cat/1.0 http://standards.iso.org/iso/19115/-3/cat/1.0/cat.xsd http://standards.iso.org/iso/19115/-3/cit/1.0 http://standards.iso.org/iso/19115/-3/cit/1.0/cit.xsd http://standards.iso.org/iso/19115/-3/gcx/1.0 http://standards.iso.org/iso/19115/-3/gcx/1.0/gcx.xsd http://standards.iso.org/iso/19115/-3/gex/1.0 http://standards.iso.org/iso/19115/-3/gex/1.0/gex.xsd http://standards.iso.org/iso/19115/-3/lan/1.0 http://standards.iso.org/iso/19115/-3/lan/1.0/lan.xsd http://standards.iso.org/iso/19115/-3/srv/2.0 http://standards.iso.org/iso/19115/-3/srv/2.0/srv.xsd http://standards.iso.org/iso/19115/-3/mas/1.0 http://standards.iso.org/iso/19115/-3/mas/1.0/mas.xsd http://standards.iso.org/iso/19115/-3/mcc/1.0 http://standards.iso.org/iso/19115/-3/mcc/1.0/mcc.xsd http://standards.iso.org/iso/19115/-3/mco/1.0 http://standards.iso.org/iso/19115/-3/mco/1.0/mco.xsd http://standards.iso.org/iso/19115/-3/mda/1.0 http://standards.iso.org/iso/19115/-3/mda/1.0/mda.xsd http://standards.iso.org/iso/19115/-3/mdb/1.0 http://standards.iso.org/iso/19115/-3/mdb/1.0/mdb.xsd http://standards.iso.org/iso/19115/-3/mds/1.0 http://standards.iso.org/iso/19115/-3/mds/1.0/mds.xsd http://standards.iso.org/iso/19115/-3/mdt/1.0 http://standards.iso.org/iso/19115/-3/mdt/1.0/mdt.xsd http://standards.iso.org/iso/19115/-3/mex/1.0 http://standards.iso.org/iso/19115/-3/mex/1.0/mex.xsd http://standards.iso.org/iso/19115/-3/mmi/1.0 http://standards.iso.org/iso/19115/-3/mmi/1.0/mmi.xsd http://standards.iso.org/iso/19115/-3/mpc/1.0 http://standards.iso.org/iso/19115/-3/mpc/1.0/mpc.xsd http://standards.iso.org/iso/19115/-3/mrc/1.0 http://standards.iso.org/iso/19115/-3/mrc/1.0/mrc.xsd http://standards.iso.org/iso/19115/-3/mrd/1.0 http://standards.iso.org/iso/19115/-3/mrd/1.0/mrd.xsd http://standards.iso.org/iso/19115/-3/mri/1.0 http://standards.iso.org/iso/19115/-3/mri/1.0/mri.xsd http://standards.iso.org/iso/19115/-3/mrl/1.0 http://standards.iso.org/iso/19115/-3/mrl/1.0/mrl.xsd http://standards.iso.org/iso/19115/-3/mrs/1.0 http://standards.iso.org/iso/19115/-3/mrs/1.0/mrs.xsd http://standards.iso.org/iso/19115/-3/msr/1.0 http://standards.iso.org/iso/19115/-3/msr/1.0/msr.xsd http://standards.iso.org/iso/19157/-2/mdq/1.0 http://standards.iso.org/iso/19157/-2/mdq/1.0/mdq.xsd http://standards.iso.org/iso/19115/-3/mac/1.0 http://standards.iso.org/iso/19115/-3/mac/1.0/mac.xsd http://standards.iso.org/iso/19115/-3/gco/1.0 http://standards.iso.org/iso/19115/-3/gco/1.0/gco.xsd http://www.opengis.net/gml/3.2 http://schemas.opengis.net/gml/3.2.1/gml.xsd http://www.w3.org/1999/xlink http://www.w3.org/1999/xlink.xsd">
  <mdb:metadataIdentifier>
    <mcc:MD_Identifier>
      <mcc:authority>
        <cit:CI_Citation>
          <cit:title>
            <gco:CharacterString>GeoNetwork UUID</gco:CharacterString>
          </cit:title>
        </cit:CI_Citation>
      </mcc:authority>
      <mcc:code>
        <gco:CharacterString>dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
      </mcc:code>
      <mcc:codeSpace>
        <gco:CharacterString>urn:uuid</gco:CharacterString>
      </mcc:codeSpace>
    </mcc:MD_Identifier>
  </mdb:metadataIdentifier>
  <mdb:parentMetadata>
    <cit:CI_Citation>
      <cit:title>
        <gco:CharacterString>Geophysical Data Collection - gravity</gco:CharacterString>
      </cit:title>
      <cit:date>
        <cit:CI_Date>
          <cit:date>
            <gco:DateTime>1937-01-01T00:00:00</gco:DateTime>
          </cit:date>
          <cit:dateType>
            <cit:CI_DateTypeCode codeList="codeListLocation#CI_DateTypeCode" codeListValue="creation"/>
          </cit:dateType>
        </cit:CI_Date>
      </cit:date>
      <cit:edition gco:nilReason="missing">
        <gco:CharacterString/>
      </cit:edition>
      <cit:editionDate>
        <gco:DateTime>1937-01-01T00:00:00</gco:DateTime>
      </cit:editionDate>
      <cit:identifier>
        <mcc:MD_Identifier>
          <mcc:code>
            <gcx:FileName src="http://intranet.ga.gov.au/geonetwork/srv/eng/file.disclaimer?uuid=dbcc0c59-81e6-4eed-e044-00144fdd4fa6&amp;fname=c6b58f54-102c-19e9-e044-00144fdd4fa6&amp;access=private">c6b58f54-102c-19e9-e044-00144fdd4fa6</gcx:FileName>
          </mcc:code>
          <mcc:description>
            <gco:CharacterString>UUID</gco:CharacterString>
          </mcc:description>
        </mcc:MD_Identifier>
      </cit:identifier>
      <cit:identifier>
        <mcc:MD_Identifier>
          <mcc:code>
            <gcx:FileName src="http://intranet.ga.gov.au/geonetwork/srv/eng/file.disclaimer?uuid=dbcc0c59-81e6-4eed-e044-00144fdd4fa6&amp;fname=74512&amp;access=private">74512</gcx:FileName>
          </mcc:code>
          <mcc:description>
            <gco:CharacterString>eCat ID</gco:CharacterString>
          </mcc:description>
        </mcc:MD_Identifier>
      </cit:identifier>
      <cit:ISBN gco:nilReason="missing">
        <gco:CharacterString/>
      </cit:ISBN>
    </cit:CI_Citation>
  </mdb:parentMetadata>
  <mdb:metadataScope>
    <mdb:MD_MetadataScope>
      <mdb:resourceScope>
        <mcc:MD_ScopeCode codeList="codeListLocation#MD_ScopeCode" codeListValue="dataset"/>
      </mdb:resourceScope>
      <mdb:name>
        <gco:CharacterString>dataset</gco:CharacterString>
      </mdb:name>
    </mdb:MD_MetadataScope>
  </mdb:metadataScope>
  <mdb:contact>
    <cit:CI_Responsibility>
      <cit:role>
        <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="pointOfContact"/>
      </cit:role>
      <cit:party>
        <cit:CI_Organisation>
          <cit:name>
            <gco:CharacterString>Commonwealth of Australia (Geoscience Australia)</gco:CharacterString>
          </cit:name>
          <cit:contactInfo>
            <cit:CI_Contact>
              <cit:phone>
                <cit:CI_Telephone>
                  <cit:number>
                    <gco:CharacterString>02 6249 9966</gco:CharacterString>
                  </cit:number>
                  <cit:numberType>
                    <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                  </cit:numberType>
                </cit:CI_Telephone>
              </cit:phone>
              <cit:phone>
                <cit:CI_Telephone>
                  <cit:number>
                    <gco:CharacterString>02 6249 9960</gco:CharacterString>
                  </cit:number>
                  <cit:numberType>
                    <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="facsimile"/>
                  </cit:numberType>
                </cit:CI_Telephone>
              </cit:phone>
              <cit:address>
                <cit:CI_Address>
                  <cit:deliveryPoint>
                    <gco:CharacterString>Cnr Jerrabomberra Ave and Hindmarsh Dr</gco:CharacterString>
                  </cit:deliveryPoint>
                  <cit:deliveryPoint>
                    <gco:CharacterString>GPO Box 378</gco:CharacterString>
                  </cit:deliveryPoint>
                  <cit:city>
                    <gco:CharacterString>Canberra</gco:CharacterString>
                  </cit:city>
                  <cit:administrativeArea>
                    <gco:CharacterString>ACT</gco:CharacterString>
                  </cit:administrativeArea>
                  <cit:postalCode>
                    <gco:CharacterString>2601</gco:CharacterString>
                  </cit:postalCode>
                  <cit:country>
                    <gco:CharacterString>Australia</gco:CharacterString>
                  </cit:country>
                  <cit:electronicMailAddress>
                    <gco:CharacterString>clientservices@ga.gov.au</gco:CharacterString>
                  </cit:electronicMailAddress>
                </cit:CI_Address>
              </cit:address>
            </cit:CI_Contact>
          </cit:contactInfo>
        </cit:CI_Organisation>
      </cit:party>
    </cit:CI_Responsibility>
  </mdb:contact>
  <mdb:dateInfo>
    <cit:CI_Date>
      <cit:date>
        <gco:DateTime>2016-06-16T14:38:55</gco:DateTime>
      </cit:date>
      <cit:dateType>
        <cit:CI_DateTypeCode codeList="codeListLocation#CI_DateTypeCode" codeListValue="revision"/>
      </cit:dateType>
    </cit:CI_Date>
  </mdb:dateInfo>
  <mdb:dateInfo>
    <cit:CI_Date>
      <cit:date>
        <gco:DateTime>2013-05-03T00:00:00</gco:DateTime>
      </cit:date>
      <cit:dateType>
        <cit:CI_DateTypeCode codeList="codeListLocation#CI_DateTypeCode" codeListValue="creation"/>
      </cit:dateType>
    </cit:CI_Date>
  </mdb:dateInfo>
  <mdb:metadataStandard>
    <cit:CI_Citation>
      <cit:title>
        <gco:CharacterString>ANZLIC Metadata Profile: An Australian/New Zealand Profile of AS/NZS ISO 19115:2005, Geographic information - Metadata</gco:CharacterString>
      </cit:title>
      <cit:edition>
        <gco:CharacterString>1.1</gco:CharacterString>
      </cit:edition>
    </cit:CI_Citation>
  </mdb:metadataStandard>
  <mdb:metadataProfile>
    <cit:CI_Citation>
      <cit:title>
        <gco:CharacterString>Geoscience Australia Community Metadata Profile of ISO 19115-1:2014</gco:CharacterString>
      </cit:title>
      <cit:edition>
        <gco:CharacterString>Version 2.0, April 2015</gco:CharacterString>
      </cit:edition>
    </cit:CI_Citation>
  </mdb:metadataProfile>
  <mdb:alternativeMetadataReference>
    <cit:CI_Citation>
      <cit:title>
        <gco:CharacterString>Geoscience Australia - short identifier for metadata record with uuid</gco:CharacterString>
      </cit:title>
      <cit:identifier>
        <mcc:MD_Identifier>
          <mcc:code>
            <gco:CharacterString>76068</gco:CharacterString>
          </mcc:code>
          <mcc:codeSpace>
            <gco:CharacterString>http://www.ga.gov.au/eCatId</gco:CharacterString>
          </mcc:codeSpace>
        </mcc:MD_Identifier>
      </cit:identifier>
    </cit:CI_Citation>
  </mdb:alternativeMetadataReference>
  <mdb:metadataLinkage>
    <cit:CI_OnlineResource>
      <cit:linkage>
        <gco:CharacterString>http://intranet.ga.gov.au/geonetwork/srv/eng/search?uuid=dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
      </cit:linkage>
      <cit:function>
        <cit:CI_OnLineFunctionCode codeList="codeListLocation#CI_OnLineFunctionCode" codeListValue="completeMetadata"/>
      </cit:function>
    </cit:CI_OnlineResource>
  </mdb:metadataLinkage>
  <mdb:identificationInfo>
    <mri:MD_DataIdentification>
      <mri:citation>
        <cit:CI_Citation>
          <cit:title>
            <gco:CharacterString>Isostatic Residual Gravity Anomaly Grid of Onshore Australia - 2011</gco:CharacterString>
          </cit:title>
          <cit:date>
            <cit:CI_Date>
              <cit:date>
                <gco:DateTime>2011-01-01T00:00:00</gco:DateTime>
              </cit:date>
              <cit:dateType>
                <cit:CI_DateTypeCode codeList="codeListLocation#CI_DateTypeCode" codeListValue="publication"/>
              </cit:dateType>
            </cit:CI_Date>
          </cit:date>
          <cit:identifier>
            <mcc:MD_Identifier>
              <mcc:code>
                <gco:CharacterString>76068</gco:CharacterString>
              </mcc:code>
            </mcc:MD_Identifier>
          </cit:identifier>
          <cit:identifier>
            <mcc:MD_Identifier>
              <mcc:code>
                <gco:CharacterString>Product</gco:CharacterString>
              </mcc:code>
            </mcc:MD_Identifier>
          </cit:identifier>
          <cit:identifier>
            <mcc:MD_Identifier>
              <mcc:code>
                <gco:CharacterString>http://www.ga.gov.au/metadata-gateway/metadata/record/76068/</gco:CharacterString>
              </mcc:code>
              <mcc:codeSpace>
                <gco:CharacterString>ga-dataSetURI</gco:CharacterString>
              </mcc:codeSpace>
            </mcc:MD_Identifier>
          </cit:identifier>
          <cit:citedResponsibleParty>
            <cit:CI_Responsibility>
              <cit:role>
                <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="publisher"/>
              </cit:role>
              <cit:party>
                <cit:CI_Organisation>
                  <cit:name>
                    <gco:CharacterString>Geoscience Australia</gco:CharacterString>
                  </cit:name>
                  <cit:contactInfo>
                    <cit:CI_Contact>
                      <cit:address>
                        <cit:CI_Address>
                          <cit:city>
                            <gco:CharacterString>Canberra</gco:CharacterString>
                          </cit:city>
                        </cit:CI_Address>
                      </cit:address>
                    </cit:CI_Contact>
                  </cit:contactInfo>
                </cit:CI_Organisation>
              </cit:party>
            </cit:CI_Responsibility>
          </cit:citedResponsibleParty>
          <cit:citedResponsibleParty>
            <cit:CI_Responsibility>
              <cit:role>
                <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="author"/>
              </cit:role>
              <cit:party>
                <cit:CI_Individual>
                  <cit:name>
                    <gco:CharacterString>Nakamura, A.</gco:CharacterString>
                  </cit:name>
                  <cit:contactInfo>
                    <cit:CI_Contact>
                      <cit:contactInstructions>
                        <gco:CharacterString>1</gco:CharacterString>
                      </cit:contactInstructions>
                    </cit:CI_Contact>
                  </cit:contactInfo>
                </cit:CI_Individual>
              </cit:party>
            </cit:CI_Responsibility>
          </cit:citedResponsibleParty>
        </cit:CI_Citation>
      </mri:citation>
      <mri:abstract>
        <gco:CharacterString>Gravity data measure small changes in gravity due to changes in the density of rocks beneath the Earth surface. This grid represents isostatic residual gravity anomalies over onshore Australia made from onshore gravity measurements collected on geophysical surveys conducted by Commonwealth, State and Northern Territory governments, and the private sector. The grid cell size is approximately 800 metres. As the effect of the long wavelength anomalies are removed, the isostatic residual anomalies reveal better than most gravity maps, the density distributions within the upper crust.</gco:CharacterString>
      </mri:abstract>
      <mri:pointOfContact>
        <cit:CI_Responsibility>
          <cit:role>
            <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="owner">owner</cit:CI_RoleCode>
          </cit:role>
          <cit:party>
            <cit:CI_Organisation>
              <cit:name>
                <gco:CharacterString>Commonwealth of Australia (Geoscience Australia)</gco:CharacterString>
              </cit:name>
            </cit:CI_Organisation>
          </cit:party>
        </cit:CI_Responsibility>
      </mri:pointOfContact>
      <mri:pointOfContact>
        <cit:CI_Responsibility>
          <cit:role>
            <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="custodian">custodian</cit:CI_RoleCode>
          </cit:role>
          <cit:party>
            <cit:CI_Organisation>
              <cit:name>
                <gco:CharacterString>Commonwealth of Australia (Geoscience Australia)</gco:CharacterString>
              </cit:name>
              <cit:contactInfo>
                <cit:CI_Contact>
                  <cit:phone>
                    <cit:CI_Telephone>
                      <cit:number>
                        <gco:CharacterString>02 6249 9966</gco:CharacterString>
                      </cit:number>
                      <cit:numberType>
                        <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice">voice</cit:CI_TelephoneTypeCode>
                      </cit:numberType>
                    </cit:CI_Telephone>
                  </cit:phone>
                  <cit:phone>
                    <cit:CI_Telephone>
                      <cit:number>
                        <gco:CharacterString>02 6249 9960</gco:CharacterString>
                      </cit:number>
                      <cit:numberType>
                        <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="facsimile">facsimile</cit:CI_TelephoneTypeCode>
                      </cit:numberType>
                    </cit:CI_Telephone>
                  </cit:phone>
                  <cit:address>
                    <cit:CI_Address>
                      <cit:deliveryPoint>
                        <gco:CharacterString>Cnr Jerrabomberra Ave and Hindmarsh Dr GPO Box 378</gco:CharacterString>
                      </cit:deliveryPoint>
                      <cit:city>
                        <gco:CharacterString>Canberra</gco:CharacterString>
                      </cit:city>
                      <cit:administrativeArea>
                        <gco:CharacterString>ACT</gco:CharacterString>
                      </cit:administrativeArea>
                      <cit:postalCode>
                        <gco:CharacterString>2601</gco:CharacterString>
                      </cit:postalCode>
                      <cit:country>
                        <gco:CharacterString>Australia</gco:CharacterString>
                      </cit:country>
                      <cit:electronicMailAddress>
                        <gco:CharacterString>clientservices@ga.gov.au</gco:CharacterString>
                      </cit:electronicMailAddress>
                    </cit:CI_Address>
                  </cit:address>
                </cit:CI_Contact>
              </cit:contactInfo>
              <cit:individual>
                <cit:CI_Individual>
                  <cit:positionName>
                    <gco:CharacterString>Manager Client Services</gco:CharacterString>
                  </cit:positionName>
                </cit:CI_Individual>
              </cit:individual>
            </cit:CI_Organisation>
          </cit:party>
        </cit:CI_Responsibility>
      </mri:pointOfContact>
      <mri:topicCategory>
        <mri:MD_TopicCategoryCode>geoscientificInformation</mri:MD_TopicCategoryCode>
      </mri:topicCategory>
      <mri:extent>
        <gex:EX_Extent>
          <gex:description>
            <gco:CharacterString>unknown</gco:CharacterString>
          </gex:description>
          <gex:geographicElement>
            <gex:EX_GeographicBoundingBox>
              <gex:westBoundLongitude>
                <gco:Decimal>109.108568</gco:Decimal>
              </gex:westBoundLongitude>
              <gex:eastBoundLongitude>
                <gco:Decimal>156.750215</gco:Decimal>
              </gex:eastBoundLongitude>
              <gex:southBoundLatitude>
                <gco:Decimal>-44.213268</gco:Decimal>
              </gex:southBoundLatitude>
              <gex:northBoundLatitude>
                <gco:Decimal>-9.363281</gco:Decimal>
              </gex:northBoundLatitude>
            </gex:EX_GeographicBoundingBox>
          </gex:geographicElement>
        </gex:EX_Extent>
      </mri:extent>
      <mri:resourceMaintenance>
        <mmi:MD_MaintenanceInformation>
          <mmi:maintenanceAndUpdateFrequency>
            <mmi:MD_MaintenanceFrequencyCode codeList="codeListLocation#MD_MaintenanceFrequencyCode" codeListValue="notPlanned"/>
          </mmi:maintenanceAndUpdateFrequency>
        </mmi:MD_MaintenanceInformation>
      </mri:resourceMaintenance>
      <mri:resourceFormat>
        <mrd:MD_Format>
          <mrd:formatSpecificationCitation>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>netCDF4_classic</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date gco:nilReason="missing"/>
                  <cit:dateType gco:nilReason="missing"/>
                </cit:CI_Date>
              </cit:date>
              <cit:edition>
                <gco:CharacterString>v4</gco:CharacterString>
              </cit:edition>
            </cit:CI_Citation>
          </mrd:formatSpecificationCitation>
          <mrd:formatDistributor>
            <mrd:MD_Distributor>
              <mrd:distributorContact>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="distributor"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>Geoscience Australia</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6249 9966</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6249 9960</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="facsimile"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:address>
                            <cit:CI_Address>
                              <cit:deliveryPoint>
                                <gco:CharacterString>GPO Box 378</gco:CharacterString>
                              </cit:deliveryPoint>
                              <cit:city>
                                <gco:CharacterString>Canberra</gco:CharacterString>
                              </cit:city>
                              <cit:administrativeArea>
                                <gco:CharacterString>ACT</gco:CharacterString>
                              </cit:administrativeArea>
                              <cit:postalCode>
                                <gco:CharacterString>2601</gco:CharacterString>
                              </cit:postalCode>
                              <cit:country>
                                <gco:CharacterString>Australia</gco:CharacterString>
                              </cit:country>
                              <cit:electronicMailAddress>
                                <gco:CharacterString>clientservices@ga.gov.au</gco:CharacterString>
                              </cit:electronicMailAddress>
                            </cit:CI_Address>
                          </cit:address>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </mrd:distributorContact>
            </mrd:MD_Distributor>
          </mrd:formatDistributor>
        </mrd:MD_Format>
      </mri:resourceFormat>
      <mri:descriptiveKeywords>
        <mri:MD_Keywords>
          <mri:keyword>
            <gco:CharacterString>National dataset</gco:CharacterString>
          </mri:keyword>
          <mri:type>
            <mri:MD_KeywordTypeCode codeList="codeListLocation#MD_KeywordTypeCode" codeListValue="theme"/>
          </mri:type>
        </mri:MD_Keywords>
      </mri:descriptiveKeywords>
      <mri:descriptiveKeywords>
        <mri:MD_Keywords>
          <mri:keyword>
            <gco:CharacterString>gravity</gco:CharacterString>
          </mri:keyword>
          <mri:type>
            <mri:MD_KeywordTypeCode codeList="codeListLocation#MD_KeywordTypeCode" codeListValue="theme"/>
          </mri:type>
        </mri:MD_Keywords>
      </mri:descriptiveKeywords>
      <mri:descriptiveKeywords>
        <mri:MD_Keywords>
          <mri:keyword>
            <gco:CharacterString>grid</gco:CharacterString>
          </mri:keyword>
          <mri:type>
            <mri:MD_KeywordTypeCode codeList="codeListLocation#MD_KeywordTypeCode" codeListValue="theme"/>
          </mri:type>
        </mri:MD_Keywords>
      </mri:descriptiveKeywords>
      <mri:descriptiveKeywords>
        <mri:MD_Keywords>
          <mri:keyword>
            <gco:CharacterString>NCI</gco:CharacterString>
          </mri:keyword>
          <mri:type>
            <mri:MD_KeywordTypeCode codeList="codeListLocation#MD_KeywordTypeCode" codeListValue="theme"/>
          </mri:type>
        </mri:MD_Keywords>
      </mri:descriptiveKeywords>
      <mri:descriptiveKeywords>
        <mri:MD_Keywords>
          <mri:keyword>
            <gco:CharacterString>Gravimetrics</gco:CharacterString>
          </mri:keyword>
          <mri:thesaurusName>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>Australian and New Zealand Standard Research Classification (ANZSRC)</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date>
                    <gco:DateTime>2011-01-01T00:00:00+11:00</gco:DateTime>
                  </cit:date>
                  <cit:dateType>
                    <cit:CI_DateTypeCode codeList="codeListLocation#CI_DateTypeCode" codeListValue="publication"/>
                  </cit:dateType>
                </cit:CI_Date>
              </cit:date>
              <cit:citedResponsibleParty>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="owner"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>Australian Bureau of Statistics (ABS)</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:onlineResource>
                            <cit:CI_OnlineResource>
                              <cit:linkage>
                                <gco:CharacterString>http://www.abs.gov.au/ausstats/abs@.nsf/Latestproducts/1297.0Main%20Features32008?opendocument&amp;tabname=Summary&amp;prodno=1297.0&amp;issue=2008&amp;num=&amp;view=</gco:CharacterString>
                              </cit:linkage>
                            </cit:CI_OnlineResource>
                          </cit:onlineResource>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </cit:citedResponsibleParty>
              <cit:ISBN>
                <gco:CharacterString>9780642483584</gco:CharacterString>
              </cit:ISBN>
              <cit:onlineResource>
                <cit:CI_OnlineResource>
                  <cit:linkage>
                    <gco:CharacterString>http://www.abs.gov.au/ausstats/abs@.nsf/Latestproducts/1297.0Main%20Features32008?opendocument&amp;tabname=Summary&amp;prodno=1297.0&amp;issue=2008&amp;num=&amp;view=</gco:CharacterString>
                  </cit:linkage>
                </cit:CI_OnlineResource>
              </cit:onlineResource>
            </cit:CI_Citation>
          </mri:thesaurusName>
        </mri:MD_Keywords>
      </mri:descriptiveKeywords>
      <mri:descriptiveKeywords>
        <mri:MD_Keywords>
          <mri:keyword>
            <gco:CharacterString>Isostatic anomaly</gco:CharacterString>
          </mri:keyword>
          <mri:type>
            <mri:MD_KeywordTypeCode codeList="codeListLocation#MD_KeywordTypeCode" codeListValue="theme"/>
          </mri:type>
        </mri:MD_Keywords>
      </mri:descriptiveKeywords>
      <mri:descriptiveKeywords>
        <mri:MD_Keywords>
          <mri:keyword>
            <gco:CharacterString>Geophysical National Coverage</gco:CharacterString>
          </mri:keyword>
          <mri:type>
            <mri:MD_KeywordTypeCode codeList="codeListLocation#MD_KeywordTypeCode" codeListValue="theme"/>
          </mri:type>
        </mri:MD_Keywords>
      </mri:descriptiveKeywords>
      <mri:descriptiveKeywords>
        <mri:MD_Keywords>
          <mri:keyword>
            <gco:CharacterString>Gravity Digital Data</gco:CharacterString>
          </mri:keyword>
          <mri:type>
            <mri:MD_KeywordTypeCode codeList="codeListLocation#MD_KeywordTypeCode" codeListValue="theme"/>
          </mri:type>
        </mri:MD_Keywords>
      </mri:descriptiveKeywords>
      <mri:resourceConstraints>
        <mco:MD_LegalConstraints>
          <mco:accessConstraints>
            <mco:MD_RestrictionCode codeList="codeListLocation#MD_RestrictionCode" codeListValue="license"/>
          </mco:accessConstraints>
        </mco:MD_LegalConstraints>
      </mri:resourceConstraints>
      <mri:resourceConstraints>
        <mco:MD_LegalConstraints>
          <mco:useConstraints>
            <mco:MD_RestrictionCode codeList="codeListLocation#MD_RestrictionCode" codeListValue="license"/>
          </mco:useConstraints>
          <mco:otherConstraints>
            <gco:CharacterString>Creative Commons Attribution 4.0 International Licence</gco:CharacterString>
          </mco:otherConstraints>
        </mco:MD_LegalConstraints>
      </mri:resourceConstraints>
      <mri:resourceConstraints>
        <mco:MD_SecurityConstraints>
          <mco:classification>
            <mco:MD_ClassificationCode codeList="codeListLocation#MD_ClassificationCode" codeListValue="unclassified"/>
          </mco:classification>
        </mco:MD_SecurityConstraints>
      </mri:resourceConstraints>
      <mri:defaultLocale>
        <lan:PT_Locale id="ENG">
          <lan:language>
            <lan:LanguageCode codeList="http://www.loc.gov/standards/iso639-2/" codeListValue="eng"/>
          </lan:language>
          <lan:characterEncoding>
            <lan:MD_CharacterSetCode codeList="codeListLocation#MD_CharacterSetCode" codeListValue="utf8"/>
          </lan:characterEncoding>
        </lan:PT_Locale>
      </mri:defaultLocale>
    </mri:MD_DataIdentification>
  </mdb:identificationInfo>
  <mdb:distributionInfo>
    <mrd:MD_Distribution>
      <mrd:distributionFormat>
        <mrd:MD_Format>
          <mrd:formatSpecificationCitation>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>html</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date gco:nilReason="missing"/>
                  <cit:dateType gco:nilReason="missing"/>
                </cit:CI_Date>
              </cit:date>
              <cit:edition>
                <gco:CharacterString>1</gco:CharacterString>
              </cit:edition>
            </cit:CI_Citation>
          </mrd:formatSpecificationCitation>
          <mrd:formatDistributor>
            <mrd:MD_Distributor>
              <mrd:distributorContact>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="distributor"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>National Computational Infrastructure</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6125 3437</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:address>
                            <cit:CI_Address>
                              <cit:deliveryPoint>
                                <gco:CharacterString>The Australian National University, 143 Ward Road</gco:CharacterString>
                              </cit:deliveryPoint>
                              <cit:city>
                                <gco:CharacterString>Acton</gco:CharacterString>
                              </cit:city>
                              <cit:administrativeArea>
                                <gco:CharacterString>ACT</gco:CharacterString>
                              </cit:administrativeArea>
                              <cit:postalCode>
                                <gco:CharacterString>2601</gco:CharacterString>
                              </cit:postalCode>
                              <cit:country>
                                <gco:CharacterString>Australia</gco:CharacterString>
                              </cit:country>
                              <cit:electronicMailAddress>
                                <gco:CharacterString>help@nci.org.au</gco:CharacterString>
                              </cit:electronicMailAddress>
                            </cit:CI_Address>
                          </cit:address>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </mrd:distributorContact>
              <mrd:distributorTransferOptions>
                <mrd:MD_DigitalTransferOptions>
                  <mrd:onLine>
                    <cit:CI_OnlineResource>
                      <cit:linkage>
                        <gco:CharacterString>http://dap.nci.org.au/thredds/remoteCatalogService?command=subset&amp;catalog=http://dapds00.nci.org.au/thredds/catalog/rr2/National_Coverages/IR_gravity_anomaly_Australia_V1/catalog.xml&amp;dataset=rr2-NatCov/IR_gravity_anomaly_Australia_V1/IR_gravity_anomaly_Australia_V1.nc</gco:CharacterString>
                      </cit:linkage>
                      <cit:protocol>
                        <gco:CharacterString>WWW:LINK-1.0-http--link</gco:CharacterString>
                      </cit:protocol>
                      <cit:name>
                        <gco:CharacterString>THREDDS catalog page for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:name>
                      <cit:description>
                        <gco:CharacterString>THREDDS catalog page for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:description>
                    </cit:CI_OnlineResource>
                  </mrd:onLine>
                </mrd:MD_DigitalTransferOptions>
              </mrd:distributorTransferOptions>
            </mrd:MD_Distributor>
          </mrd:formatDistributor>
        </mrd:MD_Format>
      </mrd:distributionFormat>
      <mrd:distributionFormat>
        <mrd:MD_Format>
          <mrd:formatSpecificationCitation>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>NetCDF</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date gco:nilReason="missing"/>
                  <cit:dateType gco:nilReason="missing"/>
                </cit:CI_Date>
              </cit:date>
              <cit:edition>
                <gco:CharacterString>1</gco:CharacterString>
              </cit:edition>
            </cit:CI_Citation>
          </mrd:formatSpecificationCitation>
          <mrd:formatDistributor>
            <mrd:MD_Distributor>
              <mrd:distributorContact>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="distributor"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>National Computational Infrastructure</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6125 3437</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:address>
                            <cit:CI_Address>
                              <cit:deliveryPoint>
                                <gco:CharacterString>The Australian National University, 143 Ward Road</gco:CharacterString>
                              </cit:deliveryPoint>
                              <cit:city>
                                <gco:CharacterString>Acton</gco:CharacterString>
                              </cit:city>
                              <cit:administrativeArea>
                                <gco:CharacterString>ACT</gco:CharacterString>
                              </cit:administrativeArea>
                              <cit:postalCode>
                                <gco:CharacterString>2601</gco:CharacterString>
                              </cit:postalCode>
                              <cit:country>
                                <gco:CharacterString>Australia</gco:CharacterString>
                              </cit:country>
                              <cit:electronicMailAddress>
                                <gco:CharacterString>help@nci.org.au</gco:CharacterString>
                              </cit:electronicMailAddress>
                            </cit:CI_Address>
                          </cit:address>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </mrd:distributorContact>
              <mrd:distributorTransferOptions>
                <mrd:MD_DigitalTransferOptions>
                  <mrd:onLine>
                    <cit:CI_OnlineResource>
                      <cit:linkage>
                        <gco:CharacterString>http://dapds00.nci.org.au/thredds/ncss/rr2/National_Coverages/dataset/dataset.nc/dataset.html</gco:CharacterString>
                      </cit:linkage>
                      <cit:protocol>
                        <gco:CharacterString>NCSS</gco:CharacterString>
                      </cit:protocol>
                      <cit:name>
                        <gco:CharacterString>NCSS for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:name>
                      <cit:description>
                        <gco:CharacterString>NetCDF Subset Service for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:description>
                    </cit:CI_OnlineResource>
                  </mrd:onLine>
                </mrd:MD_DigitalTransferOptions>
              </mrd:distributorTransferOptions>
            </mrd:MD_Distributor>
          </mrd:formatDistributor>
        </mrd:MD_Format>
      </mrd:distributionFormat>
      <mrd:distributionFormat>
        <mrd:MD_Format>
          <mrd:formatSpecificationCitation>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>NetCDF</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date gco:nilReason="missing"/>
                  <cit:dateType gco:nilReason="missing"/>
                </cit:CI_Date>
              </cit:date>
              <cit:edition>
                <gco:CharacterString>1</gco:CharacterString>
              </cit:edition>
            </cit:CI_Citation>
          </mrd:formatSpecificationCitation>
          <mrd:formatDistributor>
            <mrd:MD_Distributor>
              <mrd:distributorContact>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="distributor"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>National Computational Infrastructure</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6125 3437</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:address>
                            <cit:CI_Address>
                              <cit:deliveryPoint>
                                <gco:CharacterString>The Australian National University, 143 Ward Road</gco:CharacterString>
                              </cit:deliveryPoint>
                              <cit:city>
                                <gco:CharacterString>Acton</gco:CharacterString>
                              </cit:city>
                              <cit:administrativeArea>
                                <gco:CharacterString>ACT</gco:CharacterString>
                              </cit:administrativeArea>
                              <cit:postalCode>
                                <gco:CharacterString>2601</gco:CharacterString>
                              </cit:postalCode>
                              <cit:country>
                                <gco:CharacterString>Australia</gco:CharacterString>
                              </cit:country>
                              <cit:electronicMailAddress>
                                <gco:CharacterString>help@nci.org.au</gco:CharacterString>
                              </cit:electronicMailAddress>
                            </cit:CI_Address>
                          </cit:address>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </mrd:distributorContact>
              <mrd:distributorTransferOptions>
                <mrd:MD_DigitalTransferOptions>
                  <mrd:onLine>
                    <cit:CI_OnlineResource>
                      <cit:linkage>
                        <gco:CharacterString>http://dapds00.nci.org.au/thredds/fileServer/rr2/National_Coverages/IR_gravity_anomaly_Australia_V1/IR_gravity_anomaly_Australia_V1.nc</gco:CharacterString>
                      </cit:linkage>
                      <cit:protocol>
                        <gco:CharacterString>WWW:LINK-1.0-http--link</gco:CharacterString>
                      </cit:protocol>
                      <cit:name>
                        <gco:CharacterString>NetCDF file download via HTTP for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:name>
                      <cit:description>
                        <gco:CharacterString>NetCDF file download via HTTP for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:description>
                    </cit:CI_OnlineResource>
                  </mrd:onLine>
                </mrd:MD_DigitalTransferOptions>
              </mrd:distributorTransferOptions>
            </mrd:MD_Distributor>
          </mrd:formatDistributor>
        </mrd:MD_Format>
      </mrd:distributionFormat>
      <mrd:distributionFormat>
        <mrd:MD_Format>
          <mrd:formatSpecificationCitation>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>Zipped ERS</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date gco:nilReason="missing"/>
                  <cit:dateType gco:nilReason="missing"/>
                </cit:CI_Date>
              </cit:date>
              <cit:edition>
                <gco:CharacterString>1</gco:CharacterString>
              </cit:edition>
            </cit:CI_Citation>
          </mrd:formatSpecificationCitation>
          <mrd:formatDistributor>
            <mrd:MD_Distributor>
              <mrd:distributorContact>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="distributor"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>National Computational Infrastructure</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6125 3437</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:address>
                            <cit:CI_Address>
                              <cit:deliveryPoint>
                                <gco:CharacterString>The Australian National University, 143 Ward Road</gco:CharacterString>
                              </cit:deliveryPoint>
                              <cit:city>
                                <gco:CharacterString>Acton</gco:CharacterString>
                              </cit:city>
                              <cit:administrativeArea>
                                <gco:CharacterString>ACT</gco:CharacterString>
                              </cit:administrativeArea>
                              <cit:postalCode>
                                <gco:CharacterString>2601</gco:CharacterString>
                              </cit:postalCode>
                              <cit:country>
                                <gco:CharacterString>Australia</gco:CharacterString>
                              </cit:country>
                              <cit:electronicMailAddress>
                                <gco:CharacterString>help@nci.org.au</gco:CharacterString>
                              </cit:electronicMailAddress>
                            </cit:CI_Address>
                          </cit:address>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </mrd:distributorContact>
              <mrd:distributorTransferOptions>
                <mrd:MD_DigitalTransferOptions>
                  <mrd:onLine>
                    <cit:CI_OnlineResource>
                      <cit:linkage>
                        <gco:CharacterString>http://dapds00.nci.org.au/thredds/fileServer/rr2/National_Coverages/http/IR_gravity_anomaly_Australia_V1/IR_gravity_anomaly_Australia_V1.zip</gco:CharacterString>
                      </cit:linkage>
                      <cit:protocol>
                        <gco:CharacterString>WWW:LINK-1.0-http--link</gco:CharacterString>
                      </cit:protocol>
                      <cit:name>
                        <gco:CharacterString>Zipped ERS file download via HTTP for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:name>
                      <cit:description>
                        <gco:CharacterString>Zipped ERS file download via HTTP for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:description>
                    </cit:CI_OnlineResource>
                  </mrd:onLine>
                </mrd:MD_DigitalTransferOptions>
              </mrd:distributorTransferOptions>
            </mrd:MD_Distributor>
          </mrd:formatDistributor>
        </mrd:MD_Format>
      </mrd:distributionFormat>
      <mrd:distributionFormat>
        <mrd:MD_Format>
          <mrd:formatSpecificationCitation>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>html</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date gco:nilReason="missing"/>
                  <cit:dateType gco:nilReason="missing"/>
                </cit:CI_Date>
              </cit:date>
              <cit:edition>
                <gco:CharacterString>1</gco:CharacterString>
              </cit:edition>
            </cit:CI_Citation>
          </mrd:formatSpecificationCitation>
          <mrd:formatDistributor>
            <mrd:MD_Distributor>
              <mrd:distributorContact>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="distributor"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>National Computational Infrastructure</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6125 3437</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:address>
                            <cit:CI_Address>
                              <cit:deliveryPoint>
                                <gco:CharacterString>The Australian National University, 143 Ward Road</gco:CharacterString>
                              </cit:deliveryPoint>
                              <cit:city>
                                <gco:CharacterString>Acton</gco:CharacterString>
                              </cit:city>
                              <cit:administrativeArea>
                                <gco:CharacterString>ACT</gco:CharacterString>
                              </cit:administrativeArea>
                              <cit:postalCode>
                                <gco:CharacterString>2601</gco:CharacterString>
                              </cit:postalCode>
                              <cit:country>
                                <gco:CharacterString>Australia</gco:CharacterString>
                              </cit:country>
                              <cit:electronicMailAddress>
                                <gco:CharacterString>help@nci.org.au</gco:CharacterString>
                              </cit:electronicMailAddress>
                            </cit:CI_Address>
                          </cit:address>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </mrd:distributorContact>
              <mrd:distributorTransferOptions>
                <mrd:MD_DigitalTransferOptions>
                  <mrd:onLine>
                    <cit:CI_OnlineResource>
                      <cit:linkage>
                        <gco:CharacterString>http://dapds00.nci.org.au/thredds/dodsC/rr2/National_Coverages/IR_gravity_anomaly_Australia_V1/IR_gravity_anomaly_Australia_V1.nc</gco:CharacterString>
                      </cit:linkage>
                      <cit:protocol>
                        <gco:CharacterString>WWW:LINK-1.0-http--opendap</gco:CharacterString>
                      </cit:protocol>
                      <cit:name>
                        <gco:CharacterString>OPeNDAP for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:name>
                      <cit:description>
                        <gco:CharacterString>OPeNDAP Service for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:description>
                    </cit:CI_OnlineResource>
                  </mrd:onLine>
                </mrd:MD_DigitalTransferOptions>
              </mrd:distributorTransferOptions>
            </mrd:MD_Distributor>
          </mrd:formatDistributor>
        </mrd:MD_Format>
      </mrd:distributionFormat>
      <mrd:distributionFormat>
        <mrd:MD_Format>
          <mrd:formatSpecificationCitation>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>WCS</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date gco:nilReason="missing"/>
                  <cit:dateType gco:nilReason="missing"/>
                </cit:CI_Date>
              </cit:date>
              <cit:edition>
                <gco:CharacterString>1</gco:CharacterString>
              </cit:edition>
            </cit:CI_Citation>
          </mrd:formatSpecificationCitation>
          <mrd:formatDistributor>
            <mrd:MD_Distributor>
              <mrd:distributorContact>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="distributor"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>National Computational Infrastructure</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6125 3437</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:address>
                            <cit:CI_Address>
                              <cit:deliveryPoint>
                                <gco:CharacterString>The Australian National University, 143 Ward Road</gco:CharacterString>
                              </cit:deliveryPoint>
                              <cit:city>
                                <gco:CharacterString>Acton</gco:CharacterString>
                              </cit:city>
                              <cit:administrativeArea>
                                <gco:CharacterString>ACT</gco:CharacterString>
                              </cit:administrativeArea>
                              <cit:postalCode>
                                <gco:CharacterString>2601</gco:CharacterString>
                              </cit:postalCode>
                              <cit:country>
                                <gco:CharacterString>Australia</gco:CharacterString>
                              </cit:country>
                              <cit:electronicMailAddress>
                                <gco:CharacterString>help@nci.org.au</gco:CharacterString>
                              </cit:electronicMailAddress>
                            </cit:CI_Address>
                          </cit:address>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </mrd:distributorContact>
              <mrd:distributorTransferOptions>
                <mrd:MD_DigitalTransferOptions>
                  <mrd:onLine>
                    <cit:CI_OnlineResource>
                      <cit:linkage>
                        <gco:CharacterString>http://dapds00.nci.org.au/thredds/wcs/rr2/National_Coverages/IR_gravity_anomaly_Australia_V1/IR_gravity_anomaly_Australia_V1.nc</gco:CharacterString>
                      </cit:linkage>
                      <cit:protocol>
                        <gco:CharacterString>OGC:WCS</gco:CharacterString>
                      </cit:protocol>
                      <cit:name>
                        <gco:CharacterString>WCS for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:name>
                      <cit:description>
                        <gco:CharacterString>OGC Web Coverage Service for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:description>
                    </cit:CI_OnlineResource>
                  </mrd:onLine>
                </mrd:MD_DigitalTransferOptions>
              </mrd:distributorTransferOptions>
            </mrd:MD_Distributor>
          </mrd:formatDistributor>
        </mrd:MD_Format>
      </mrd:distributionFormat>
      <mrd:distributionFormat>
        <mrd:MD_Format>
          <mrd:formatSpecificationCitation>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>WMS</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date gco:nilReason="missing"/>
                  <cit:dateType gco:nilReason="missing"/>
                </cit:CI_Date>
              </cit:date>
              <cit:edition>
                <gco:CharacterString>1</gco:CharacterString>
              </cit:edition>
            </cit:CI_Citation>
          </mrd:formatSpecificationCitation>
          <mrd:formatDistributor>
            <mrd:MD_Distributor>
              <mrd:distributorContact>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="distributor"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>National Computational Infrastructure</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6125 3437</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:address>
                            <cit:CI_Address>
                              <cit:deliveryPoint>
                                <gco:CharacterString>The Australian National University, 143 Ward Road</gco:CharacterString>
                              </cit:deliveryPoint>
                              <cit:city>
                                <gco:CharacterString>Acton</gco:CharacterString>
                              </cit:city>
                              <cit:administrativeArea>
                                <gco:CharacterString>ACT</gco:CharacterString>
                              </cit:administrativeArea>
                              <cit:postalCode>
                                <gco:CharacterString>2601</gco:CharacterString>
                              </cit:postalCode>
                              <cit:country>
                                <gco:CharacterString>Australia</gco:CharacterString>
                              </cit:country>
                              <cit:electronicMailAddress>
                                <gco:CharacterString>help@nci.org.au</gco:CharacterString>
                              </cit:electronicMailAddress>
                            </cit:CI_Address>
                          </cit:address>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </mrd:distributorContact>
              <mrd:distributorTransferOptions>
                <mrd:MD_DigitalTransferOptions>
                  <mrd:onLine>
                    <cit:CI_OnlineResource>
                      <cit:linkage>
                        <gco:CharacterString>http://dapds00.nci.org.au/thredds/wms/rr2/National_Coverages/IR_gravity_anomaly_Australia_V1/IR_gravity_anomaly_Australia_V1.nc</gco:CharacterString>
                      </cit:linkage>
                      <cit:protocol>
                        <gco:CharacterString>OGC:WMS</gco:CharacterString>
                      </cit:protocol>
                      <cit:name>
                        <gco:CharacterString>WMS for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:name>
                      <cit:description>
                        <gco:CharacterString>OGC Web Mapping Service for dataset dbcc0c59-81e6-4eed-e044-00144fdd4fa6</gco:CharacterString>
                      </cit:description>
                    </cit:CI_OnlineResource>
                  </mrd:onLine>
                </mrd:MD_DigitalTransferOptions>
              </mrd:distributorTransferOptions>
            </mrd:MD_Distributor>
          </mrd:formatDistributor>
        </mrd:MD_Format>
      </mrd:distributionFormat>
      <mrd:distributionFormat>
        <mrd:MD_Format>
          <mrd:formatSpecificationCitation>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>html</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date gco:nilReason="missing"/>
                  <cit:dateType gco:nilReason="missing"/>
                </cit:CI_Date>
              </cit:date>
              <cit:edition>
                <gco:CharacterString>1</gco:CharacterString>
              </cit:edition>
            </cit:CI_Citation>
          </mrd:formatSpecificationCitation>
          <mrd:formatDistributor>
            <mrd:MD_Distributor>
              <mrd:distributorContact>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="distributor"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>Geoscience Australia</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6249 9966</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6249 9960</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="facsimile"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:address>
                            <cit:CI_Address>
                              <cit:deliveryPoint>
                                <gco:CharacterString>GPO Box 378</gco:CharacterString>
                              </cit:deliveryPoint>
                              <cit:city>
                                <gco:CharacterString>Canberra</gco:CharacterString>
                              </cit:city>
                              <cit:administrativeArea>
                                <gco:CharacterString>ACT</gco:CharacterString>
                              </cit:administrativeArea>
                              <cit:postalCode>
                                <gco:CharacterString>2601</gco:CharacterString>
                              </cit:postalCode>
                              <cit:country>
                                <gco:CharacterString>Australia</gco:CharacterString>
                              </cit:country>
                              <cit:electronicMailAddress>
                                <gco:CharacterString>clientservices@ga.gov.au</gco:CharacterString>
                              </cit:electronicMailAddress>
                            </cit:CI_Address>
                          </cit:address>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </mrd:distributorContact>
              <mrd:distributorTransferOptions>
                <mrd:MD_DigitalTransferOptions>
                  <mrd:onLine>
                    <cit:CI_OnlineResource>
                      <cit:linkage>
                        <gco:CharacterString>http://dx.doi.org/10.4225/25/561C7CC3D8937</gco:CharacterString>
                      </cit:linkage>
                      <cit:protocol>
                        <gco:CharacterString>WWW:LINK-1.0-http--link</gco:CharacterString>
                      </cit:protocol>
                      <cit:name>
                        <gco:CharacterString>Digital Object Identifier</gco:CharacterString>
                      </cit:name>
                      <cit:description>
                        <gco:CharacterString>Dataset DOI</gco:CharacterString>
                      </cit:description>
                    </cit:CI_OnlineResource>
                  </mrd:onLine>
                </mrd:MD_DigitalTransferOptions>
              </mrd:distributorTransferOptions>
            </mrd:MD_Distributor>
          </mrd:formatDistributor>
        </mrd:MD_Format>
      </mrd:distributionFormat>
      <mrd:distributionFormat>
        <mrd:MD_Format>
          <mrd:formatSpecificationCitation>
            <cit:CI_Citation>
              <cit:title>
                <gco:CharacterString>html</gco:CharacterString>
              </cit:title>
              <cit:date>
                <cit:CI_Date>
                  <cit:date gco:nilReason="missing"/>
                  <cit:dateType gco:nilReason="missing"/>
                </cit:CI_Date>
              </cit:date>
              <cit:edition>
                <gco:CharacterString>1</gco:CharacterString>
              </cit:edition>
            </cit:CI_Citation>
          </mrd:formatSpecificationCitation>
          <mrd:formatDistributor>
            <mrd:MD_Distributor>
              <mrd:distributorContact>
                <cit:CI_Responsibility>
                  <cit:role>
                    <cit:CI_RoleCode codeList="codeListLocation#CI_RoleCode" codeListValue="distributor"/>
                  </cit:role>
                  <cit:party>
                    <cit:CI_Organisation>
                      <cit:name>
                        <gco:CharacterString>Geoscience Australia</gco:CharacterString>
                      </cit:name>
                      <cit:contactInfo>
                        <cit:CI_Contact>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6249 9966</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="voice"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:phone>
                            <cit:CI_Telephone>
                              <cit:number>
                                <gco:CharacterString>+61 2 6249 9960</gco:CharacterString>
                              </cit:number>
                              <cit:numberType>
                                <cit:CI_TelephoneTypeCode codeList="codeListLocation#CI_TelephoneTypeCode" codeListValue="facsimile"/>
                              </cit:numberType>
                            </cit:CI_Telephone>
                          </cit:phone>
                          <cit:address>
                            <cit:CI_Address>
                              <cit:deliveryPoint>
                                <gco:CharacterString>GPO Box 378</gco:CharacterString>
                              </cit:deliveryPoint>
                              <cit:city>
                                <gco:CharacterString>Canberra</gco:CharacterString>
                              </cit:city>
                              <cit:administrativeArea>
                                <gco:CharacterString>ACT</gco:CharacterString>
                              </cit:administrativeArea>
                              <cit:postalCode>
                                <gco:CharacterString>2601</gco:CharacterString>
                              </cit:postalCode>
                              <cit:country>
                                <gco:CharacterString>Australia</gco:CharacterString>
                              </cit:country>
                              <cit:electronicMailAddress>
                                <gco:CharacterString>clientservices@ga.gov.au</gco:CharacterString>
                              </cit:electronicMailAddress>
                            </cit:CI_Address>
                          </cit:address>
                        </cit:CI_Contact>
                      </cit:contactInfo>
                    </cit:CI_Organisation>
                  </cit:party>
                </cit:CI_Responsibility>
              </mrd:distributorContact>
              <mrd:distributorTransferOptions>
                <mrd:MD_DigitalTransferOptions>
                  <mrd:onLine>
                    <cit:CI_OnlineResource>
                      <cit:linkage>
                        <gco:CharacterString>http://www.geoscience.gov.au/cgi-bin/mapserv?map=/nas/web/ops/prod/apps/mapserver/gadds/wms_map/gadds.map</gco:CharacterString>
                      </cit:linkage>
                      <cit:protocol>
                        <gco:CharacterString>WWW:LINK-1.0-http--link</gco:CharacterString>
                      </cit:protocol>
                      <cit:name>
                        <gco:CharacterString>Australian Geophisical Archive Data Delivery System</gco:CharacterString>
                      </cit:name>
                      <cit:description>
                        <gco:CharacterString>Download from Geoscience Australia Geophisical Archive Data Delivery System</gco:CharacterString>
                      </cit:description>
                    </cit:CI_OnlineResource>
                  </mrd:onLine>
                </mrd:MD_DigitalTransferOptions>
              </mrd:distributorTransferOptions>
            </mrd:MD_Distributor>
          </mrd:formatDistributor>
        </mrd:MD_Format>
      </mrd:distributionFormat>
    </mrd:MD_Distribution>
  </mdb:distributionInfo>
  <mdb:resourceLineage>
    <mrl:LI_Lineage>
      <mrl:statement>
        <gco:CharacterString>The gravity data set of onshore Australia contains more than 1.57 million reliable onshore stations gathered during more than 1800 surveys and held in the Australian National Gravity Database (ANGD). Continental Australia has a basic station spacing coverage of 11 km, with South Australia, Tasmania and part of New South Wales covered at a spacing of 7 km. Victoria has station coverage of approximately 1.5 km. Some areas of scientific or economic interest have been infilled with station spacings between 2 km and 4 km by recent Commonwealth, State and Territory Government initiatives. Other areas of detailed coverage have been surveyed by private companies for exploration purposes. Only open file data as held in the ANGD at March 2011 were used in the creation of the grid.
The data values contained in the grid are Isostatic Residual Gravity anomalies over Continental Australia. A depth to mantle model and subsequent isostatic corrections were produced using a modified version of the USGS program AIRYROOT (Simpson et al., 1983) provided by Intrepid Geophysics. Geoscience Australia's 2009 Bathymetry and Topography Grid (Whiteway, 2009) was used to calculate the depth to crustal bottom following the Airy-Heiskanen crustal-root model. The isostatic corrections were then applied to the complete Bouguer anomalies (Tracey and Nakamura, 2010) to produce the Isostatic Residual Gravity Anomaly Grid of Australia. The gravity anomalies are based on the Australian Absolute Gravity Datum 2007 and 1994 Geodetic Datum of Australia (Tracey et al., 2008).
A crustal density of 2.67 tonnes per cubic meter was used for the calculation, with an assumed density contrast between the crust and mantle of 0.4 tonnes per cubic meter. A depth to mantle at sea level of 37 km was used in the calculation.  This was derived from the average Australian depth to the Mohorovi&#191;i&#191; discontinuity (Moho) at sea level using data from seismic studies around Australia (Goncharov et al., 2007).
The original grid was converted from ERMapper (.ers) format to netCDF4_classic format using GDAL1.11.1. The main purpose of this conversion is to enable access to the data by relevant open source tools and software. The netCDF grid was created on 2016-03-29.
References
Goncharov, A., Deighton, I., Tischer, M. and Collins, C., 2007. Crustal thickness in Australia: where, how and what for?: ASEG Extended Abstracts, vol. 2007, pp. 1-4, ASEG2007 19th Geophysical Conference.
Simpson, R.W., Jachens, R.C. and Blakely, R.J., 1983. AIRYROOT: A FORTRAN program for calculating the gravitational attraction of an Airy isostatic root out to 166.7 km: US Geological Survey Open File Report 83-883.
Tracey, R., Bacchin, M., and Wynne, P., 2008. AAGD07: A new absolute gravity datum for Australian gravity and new standards for the Australian National Gravity Database: ASEG Extended Abstracts, vol. 2007, No.1, pp. 1-3, ASEG2007 19th Geophysical Conference.
Tracey, R. and Nakamura, A., 2010. Complete Bouguer Anomalies for the Australian National Gravity Database: ASEG Extended Abstracts, vol. 2010, pp. 1-3, ASEG2010 21st Geophysical Conference.
Whiteway, T.G., 2009. Australian Bathymetry and Topography Grid: Geoscience Australia Record 2009/21, 46pp.</gco:CharacterString>
      </mrl:statement>
      <mrl:scope>
        <mcc:MD_Scope>
          <mcc:level>
            <mcc:MD_ScopeCode codeList="codeListLocation#MD_ScopeCode" codeListValue="dataset"/>
          </mcc:level>
        </mcc:MD_Scope>
      </mrl:scope>
      <mrl:source>
        <mrl:LI_Source>
          <mrl:description>
            <gco:CharacterString>The 2011 gravity grid over Continental Australia is derived from observations recorded at more than 1.57 million gravity stations held in the Australian National Gravity Database (ANGD) by Geoscience Australia (GA). The onshore data were acquired by the Commonwealth, State and Territory Governments, the mining and exploration industry, universities and research organisations over the past 60 years.</gco:CharacterString>
          </mrl:description>
        </mrl:LI_Source>
      </mrl:source>
    </mrl:LI_Lineage>
  </mdb:resourceLineage>
  <mdb:metadataConstraints>
    <mco:MD_SecurityConstraints>
      <mco:classification>
        <mco:MD_ClassificationCode codeList="codeListLocation#MD_ClassificationCode" codeListValue="unclassified"/>
      </mco:classification>
    </mco:MD_SecurityConstraints>
  </mdb:metadataConstraints>
</mdb:MD_Metadata>"""

    # Instantiate empty MTLMetadata object and parse test string (strip all
    # EOLs first)
    xml_object = XMLMetadata()
    xml_object.read_string(TESTXML)

    assert xml_object.metadata_dict, 'No metadata_dict created'
    assert xml_object.tree_to_list(), 'Unable to create list from metadata_dict'
    #=========================================================================
    # assert xml_object.get_metadata('EODS_DATASET,ACQUISITIONINFORMATION,PLATFORMNAME'.split(',')), 'Unable to find value for key L1_METADATA_FILE,PRODUCT_METADATA,SPACECRAFT_ID'
    # assert xml_object.get_metadata('...,PLATFORMNAME'.split(',')), 'Unable to find value for key ...,SPACECRAFT_ID'
    # assert not xml_object.get_metadata('RUBBERCHICKEN'.split(',')), 'Found nonexistent key RUBBERCHICKEN'
    # xml_object.set_metadata_node('EODS_DATASET,ACQUISITIONINFORMATION,PLATFORMNAME'.split(','), 'Rubber Chicken')
    # assert xml_object.get_metadata('...,PLATFORMNAME'.split(',')), 'Unable to change ...,SPACECRAFT_ID to "Rubber Chicken"'
    # xml_object.merge_metadata_dicts({'RUBBERCHICKEN': 'Rubber Chicken'}, xml_object.metadata_dict)
    # assert xml_object.get_metadata('RUBBERCHICKEN'.split(',')), 'Unable to find value for key RUBBERCHICKEN'
    # xml_object.delete_metadata('RUBBERCHICKEN'.split(','))
    # assert not xml_object.get_metadata('RUBBERCHICKEN'.split(',')), 'Found value for key RUBBERCHICKEN'
    #=========================================================================
    print xml_object.tree_to_list()

if __name__ == '__main__':
    main()
