'''
Utility to create updated XML files from metadata sourced from GeoNetwork

Created on 1Aug.,2016

@author: Alex
'''
import os
import re
import netCDF4
import argparse
import tempfile
import logging
from lxml import etree
from metadata_sync.thredds_catalog import THREDDSCatalog
from metadata_sync.metadata_json import read_json_metadata
from _metadata_sync_utils import get_xml_from_uuid, find_files, prettify_xml

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Initial logging level for this module

class XMLUpdater(object):

#===============================================================================
#     # GA_GEONETWORK = 'http://ecat.ga.gov.au/geonetwork/srv/eng' # GA's
#     # externally-facing GeoNetwork - DO NOT USE!!!
#     # GA's internal GeoNetwork via port forward. Need to use this to obtain
#     # complete metadata
#     GA_GEONETWORK = 'http://localhost:8081/geonetwork/srv/eng'
#     #GA_GEONETWORK = 'http://intranet.ga.gov.au/geonetwork/srv/eng'
# 
#     #THREDDS_ROOT_DIR = '/g/data2/uc0/rr2_dev/rcb547/AWAGS_Levelled_Grids/'
#     #THREDDS_CATALOG_URLS = 'http://dapds00.nci.org.au/thredds/catalog/uc0/rr2_dev/rcb547/AWAGS_Levelled_Grids/catalog.html'
# 
#     THREDDS_ROOT_DIR = '/g/data1/rr2/National_Coverages/'
#     # Comma-separated list of one or more URLS in search order
#     #THREDDS_CATALOG_URLS = 'http://dapds00.nci.org.au/thredds/catalogs/rr2/catalog.html'
#     THREDDS_CATALOG_URLS = '\
# http://dap-wms.nci.org.au/thredds/catalog/rr2/National_Coverages/catalog.html,\
# http://dapds00.nci.org.au/thredds/catalog/rr2/National_Coverages/catalog.html,\
# http://dapds00.nci.org.au/thredds/catalog/rr2/National_Coverages/http/catalog.html,\
# http://dap-wms.nci.org.au/thredds/catalog/rr2/National_Coverages/http/catalog.html'
# 
#     # print 'thredds_catalog_urls = %s' % THREDDS_CATALOG_URLS
#===============================================================================

    def __init__(self, geonetwork_url, thredds_root_urls, update_bounds=True, update_distributions=True, xml_dir=None):

        # TODO: Work out some way of making this faster.
        def get_thredds_catalog(thredds_catalog_urls):
            '''
            Function to return a THREDDSCatalog object either from a pre-cached YAML file or read from specified THREDDS catalog
            '''
            # Generate unique(?) YAML filename from THREDDS URLs
            yaml_path = os.path.abspath(os.path.join(tempfile.gettempdir(), 
                                                     os.path.splitext(re.sub('\W', # Substitute underscores for non-alphanumeric characters
                                                                             '_', 
                                                                             re.sub('(http.*/thredds/)|(\.html)', # Strip ".../thredds/" from start and '.html' from end
                                                                                    '',  
                                                                                    thredds_catalog_urls))
                                                                      )[0] + '.yaml'))
            logger.debug('yaml_path = %s' % yaml_path)

            if os.path.isfile(yaml_path):
                print 'Loading previously cached catalogue tree from %s' % yaml_path
                tc = THREDDSCatalog(yaml_path=yaml_path)
            else:
                print 'Crawling THREDDS catalog %s\nWARNING: This operation may take several hours to complete!' % thredds_catalog_urls
                tc = THREDDSCatalog(thredds_catalog_urls=thredds_catalog_urls, verbose=True)
                print tc
                tc.dump(yaml_path)

            return tc

        self.update_bounds = update_bounds
        self.update_distributions = update_distributions

        if self.update_distributions:
            self.thredds_catalog = get_thredds_catalog(
                thredds_root_urls)
        else:
            self.thredds_catalog = None
            
        logger.debug('self.thredds_catalog = %s' % self.thredds_catalog)
        
        self.xml_dir = xml_dir

    def update_xml(self, nc_path, geonetwork_url):
        '''
        Function to read, update and write XML metadata for specified NetCDF file
        N.B: Requires UUID & DOI global attributes to be pre-populated in NetCDF file
        Currently creates or replaces distributionInfo element using template XML file
        '''
        def update_bounds(nc_dataset, xml_tree):
            '''
            Read the following ACDD global attributes from the NetCDF file and set the mri:extent values in the XML:

                :geospatial_bounds = "POLYGON((112.502532442 -9.0256618335, 154.662515579 -9.0256618335, 154.662515579 -43.9289812055, 112.502532442 -43.9289812055, 112.502532442 -9.0256618335))" ;
                :geospatial_bounds_crs = "GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563,AUTHORITY[\"EPSG\",\"7030\"]],AUTHORITY[\"EPSG\",\"6326\"]],PRIMEM[\"Greenwich\",0,AUTHORITY[\"EPSG\",\"8901\"]],UNIT[\"degree\",0.0174532925199433,AUTHORITY[\"EPSG\",\"9122\"]],AUTHORITY[\"EPSG\",\"4326\"]]" ;
                :geospatial_lat_max = -9.0256618335 ;
                :geospatial_lat_min = -43.9289812055 ;
                :geospatial_lat_resolution = 0.000833332999995662 ;
                :geospatial_lat_units = "degrees_north" ;
                :geospatial_lon_max = 154.6625155785 ;
                :geospatial_lon_min = 112.5025324425 ;
                :geospatial_lon_resolution = 0.000833332999974346 ;
                :geospatial_lon_units = "degrees_east" ;
            '''
            # Attempt to read temporal coverage values from netCDF file, set to empty string if not found
            try:
                time_coverage_start = nc_dataset.time_coverage_start
            except:
                time_coverage_start = ''
                
            try:
                time_coverage_end = nc_dataset.time_coverage_end
            except:
                time_coverage_end = ''
            
            # Template for mri:extent subtree
            source_tree = etree.fromstring('''
<mdb:MD_Metadata xmlns:mdb="http://standards.iso.org/iso/19115/-3/mdb/1.0"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:cat="http://standards.iso.org/iso/19115/-3/cat/1.0"
  xmlns:cit="http://standards.iso.org/iso/19115/-3/cit/1.0" xmlns:gcx="http://standards.iso.org/iso/19115/-3/gcx/1.0"
  xmlns:gex="http://standards.iso.org/iso/19115/-3/gex/1.0" xmlns:lan="http://standards.iso.org/iso/19115/-3/lan/1.0"
  xmlns:srv="http://standards.iso.org/iso/19115/-3/srv/2.0" xmlns:mas="http://standards.iso.org/iso/19115/-3/mas/1.0"
  xmlns:mcc="http://standards.iso.org/iso/19115/-3/mcc/1.0" xmlns:mco="http://standards.iso.org/iso/19115/-3/mco/1.0"
  xmlns:mda="http://standards.iso.org/iso/19115/-3/mda/1.0" xmlns:mds="http://standards.iso.org/iso/19115/-3/mds/1.0"
  xmlns:mdt="http://standards.iso.org/iso/19115/-3/mdt/1.0" xmlns:mex="http://standards.iso.org/iso/19115/-3/mex/1.0"
  xmlns:mmi="http://standards.iso.org/iso/19115/-3/mmi/1.0" xmlns:mpc="http://standards.iso.org/iso/19115/-3/mpc/1.0"
  xmlns:mrc="http://standards.iso.org/iso/19115/-3/mrc/1.0" xmlns:mrd="http://standards.iso.org/iso/19115/-3/mrd/1.0"
  xmlns:mri="http://standards.iso.org/iso/19115/-3/mri/1.0" xmlns:mrl="http://standards.iso.org/iso/19115/-3/mrl/1.0"
  xmlns:mrs="http://standards.iso.org/iso/19115/-3/mrs/1.0" xmlns:msr="http://standards.iso.org/iso/19115/-3/msr/1.0"
  xmlns:mdq="http://standards.iso.org/iso/19157/-2/mdq/1.0" xmlns:mac="http://standards.iso.org/iso/19115/-3/mac/1.0"
  xmlns:gco="http://standards.iso.org/iso/19115/-3/gco/1.0" xmlns:gml="http://www.opengis.net/gml/3.2"
  xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:geonet="http://www.fao.org/geonetwork"
  xsi:schemaLocation="http://standards.iso.org/iso/19115/-3/cat/1.0 http://standards.iso.org/iso/19115/-3/cat/1.0/cat.xsd http://standards.iso.org/iso/19115/-3/cit/1.0 http://standards.iso.org/iso/19115/-3/cit/1.0/cit.xsd http://standards.iso.org/iso/19115/-3/gcx/1.0 http://standards.iso.org/iso/19115/-3/gcx/1.0/gcx.xsd http://standards.iso.org/iso/19115/-3/gex/1.0 http://standards.iso.org/iso/19115/-3/gex/1.0/gex.xsd http://standards.iso.org/iso/19115/-3/lan/1.0 http://standards.iso.org/iso/19115/-3/lan/1.0/lan.xsd http://standards.iso.org/iso/19115/-3/srv/2.0 http://standards.iso.org/iso/19115/-3/srv/2.0/srv.xsd http://standards.iso.org/iso/19115/-3/mas/1.0 http://standards.iso.org/iso/19115/-3/mas/1.0/mas.xsd http://standards.iso.org/iso/19115/-3/mcc/1.0 http://standards.iso.org/iso/19115/-3/mcc/1.0/mcc.xsd http://standards.iso.org/iso/19115/-3/mco/1.0 http://standards.iso.org/iso/19115/-3/mco/1.0/mco.xsd http://standards.iso.org/iso/19115/-3/mda/1.0 http://standards.iso.org/iso/19115/-3/mda/1.0/mda.xsd http://standards.iso.org/iso/19115/-3/mdb/1.0 http://standards.iso.org/iso/19115/-3/mdb/1.0/mdb.xsd http://standards.iso.org/iso/19115/-3/mds/1.0 http://standards.iso.org/iso/19115/-3/mds/1.0/mds.xsd http://standards.iso.org/iso/19115/-3/mdt/1.0 http://standards.iso.org/iso/19115/-3/mdt/1.0/mdt.xsd http://standards.iso.org/iso/19115/-3/mex/1.0 http://standards.iso.org/iso/19115/-3/mex/1.0/mex.xsd http://standards.iso.org/iso/19115/-3/mmi/1.0 http://standards.iso.org/iso/19115/-3/mmi/1.0/mmi.xsd http://standards.iso.org/iso/19115/-3/mpc/1.0 http://standards.iso.org/iso/19115/-3/mpc/1.0/mpc.xsd http://standards.iso.org/iso/19115/-3/mrc/1.0 http://standards.iso.org/iso/19115/-3/mrc/1.0/mrc.xsd http://standards.iso.org/iso/19115/-3/mrd/1.0 http://standards.iso.org/iso/19115/-3/mrd/1.0/mrd.xsd http://standards.iso.org/iso/19115/-3/mri/1.0 http://standards.iso.org/iso/19115/-3/mri/1.0/mri.xsd http://standards.iso.org/iso/19115/-3/mrl/1.0 http://standards.iso.org/iso/19115/-3/mrl/1.0/mrl.xsd http://standards.iso.org/iso/19115/-3/mrs/1.0 http://standards.iso.org/iso/19115/-3/mrs/1.0/mrs.xsd http://standards.iso.org/iso/19115/-3/msr/1.0 http://standards.iso.org/iso/19115/-3/msr/1.0/msr.xsd http://standards.iso.org/iso/19157/-2/mdq/1.0 http://standards.iso.org/iso/19157/-2/mdq/1.0/mdq.xsd http://standards.iso.org/iso/19115/-3/mac/1.0 http://standards.iso.org/iso/19115/-3/mac/1.0/mac.xsd http://standards.iso.org/iso/19115/-3/gco/1.0 http://standards.iso.org/iso/19115/-3/gco/1.0/gco.xsd http://www.opengis.net/gml/3.2 http://schemas.opengis.net/gml/3.2.1/gml.xsd http://www.w3.org/1999/xlink http://www.w3.org/1999/xlink.xsd">
  <mdb:identificationInfo>
    <mri:MD_DataIdentification>
      <mri:extent>
        <gex:EX_Extent>
          <gex:temporalElement>
            <gex:EX_TemporalExtent>
              <gex:extent>
                <gml:TimePeriod gml:id="A1234">
                  <gml:beginPosition>%s</gml:beginPosition>
                  <gml:endPosition>%s</gml:endPosition>
                </gml:TimePeriod>
              </gex:extent>
            </gex:EX_TemporalExtent>
          </gex:temporalElement>
        </gex:EX_Extent>
      </mri:extent>
      <mri:extent>
        <gex:EX_Extent>
          <gex:description>
            <gco:CharacterString>Orthogonal WGS84 Bounding Box</gco:CharacterString>
          </gex:description>
          <gex:geographicElement>
            <gex:EX_GeographicBoundingBox>
              <gex:westBoundLongitude>
                <gco:Decimal>%f</gco:Decimal>
              </gex:westBoundLongitude>
              <gex:eastBoundLongitude>
                <gco:Decimal>%f</gco:Decimal>
              </gex:eastBoundLongitude>
              <gex:southBoundLatitude>
                <gco:Decimal>%f</gco:Decimal>
              </gex:southBoundLatitude>
              <gex:northBoundLatitude>
                <gco:Decimal>%f</gco:Decimal>
              </gex:northBoundLatitude>
            </gex:EX_GeographicBoundingBox>
          </gex:geographicElement>
        </gex:EX_Extent>
      </mri:extent>
    </mri:MD_DataIdentification>
  </mdb:identificationInfo>
</mdb:MD_Metadata>
''' % (time_coverage_start,
       time_coverage_end,
       nc_dataset.geospatial_lon_min,
       nc_dataset.geospatial_lon_max,
       nc_dataset.geospatial_lat_min,
       nc_dataset.geospatial_lat_max,
       )
            )

            dest_MD_DataIdentification_tree = xml_tree.find(
                path='.//mri:MD_DataIdentification', namespaces=xml_tree.nsmap)
            assert dest_MD_DataIdentification_tree is not None, 'dest_MD_DataIdentification_tree element does not exist'

            # Process both temporal & spatial extents
            for source_extent_tree in source_tree.iterfind(
                path='.//mri:extent', namespaces=xml_tree.nsmap):
                if source_extent_tree.find('gex:EX_Extent/gex:temporalElement', namespaces=xml_tree.nsmap) is not None:
                    # If source_extent_tree contains the temporal extent
                    # Delete any existing mri:extent elements for temporal extents
                    for dest_extent_tree in dest_MD_DataIdentification_tree.iterfind(
                        path='mri:extent', namespaces=xml_tree.nsmap):
                    
                        if dest_extent_tree.find('gex:EX_Extent/gex:temporalElement', namespaces=xml_tree.nsmap) is not None:
                            print 'Removing existing temporal mri:extent subtree'
                            dest_MD_DataIdentification_tree.remove(dest_extent_tree)                
            
                    if time_coverage_start: # Add a new temporal mri:extent element only if start of period is defined, 
                        preceding_tree = dest_MD_DataIdentification_tree.find(
                            path='mri:topicCategory', namespaces=xml_tree.nsmap)
                        print 'Creating new mri:extent temporal subtree after mri:topicCategory'
        
                        dest_MD_DataIdentification_tree.insert(dest_MD_DataIdentification_tree.index(preceding_tree)+1, 
                                                               source_extent_tree)
                        
                elif source_extent_tree.find('gex:EX_Extent/gex:geographicElement', namespaces=xml_tree.nsmap) is not None:
                    # If source_extent_tree contains the geographic extent
                    # Delete any existing mri:extent elements for spatial extents
                    for dest_extent_tree in dest_MD_DataIdentification_tree.iterfind(
                        path='mri:extent', namespaces=xml_tree.nsmap):
                    
                        if dest_extent_tree.find('gex:EX_Extent/gex:geographicElement', namespaces=xml_tree.nsmap) is not None:
                            print 'Removing existing spatial mri:extent subtree'
                            dest_MD_DataIdentification_tree.remove(dest_extent_tree)                
            
                    preceding_tree = dest_MD_DataIdentification_tree.find(
                        path='mri:extent', namespaces=xml_tree.nsmap) 
                    if preceding_tree is None:
                        preceding_tree = dest_MD_DataIdentification_tree.find(
                            path='mri:topicCategory', namespaces=xml_tree.nsmap)
                        print 'Creating new spatial mri:extent subtree after mri:topicCategory'
                    else:
                        print 'Creating new spatial mri:extent subtree after temporal mri:extent'
        
                    dest_MD_DataIdentification_tree.insert(dest_MD_DataIdentification_tree.index(preceding_tree)+1, 
                                                           source_extent_tree)

            return

        def update_distributions(xml_tree):
            nc_distribution_dict = self.thredds_catalog.find_url_dict(nc_path)
            assert nc_distribution_dict, 'No THREDDS endpoints found for %s' % nc_path
            
            # Calculate file info
            nc_size_mb = os.stat(nc_path).st_size / 1000000.0 # Powers of 10 used instead of powers of 2 for a more conservative number            
            metadata_dict = read_json_metadata(os.path.dirname(nc_path))
            nc_md5sum = [file_dict['md5'] 
                         for file_dict in metadata_dict['files'] 
                         if file_dict['file'] == os.path.basename(nc_path)
                         ][0]

            zip_path = os.path.splitext(nc_path)[0] + '.zip'
            zip_distribution_dict = self.thredds_catalog.find_url_dict(
                zip_path)  # Optional - could be an empty dict
    #        assert nc_distribution_dict, 'No THREDDS endpoints found for %s' % zip_path

            thredds_catalog_list = self.thredds_catalog.find_catalogs(nc_path)
            assert thredds_catalog_list, 'No THREDDS catalogue found for %s' % nc_path

            template_dict = {
                'UUID': uuid,
                'DOI': doi,
                'NC_FILE_PATH': os.path.abspath(nc_path),
                'NC_FILE_SIZE_MB': str(nc_size_mb),
                'NC_FILE_MD5SUM': nc_md5sum,
                'THREDDS_CATALOG_URL': thredds_catalog_list[0],
                'NC_HTTP_URL': nc_distribution_dict.get('HTTPServer'),
                'NCSS_URL': nc_distribution_dict.get('NetcdfSubset'),
                'OPENDAP_URL': nc_distribution_dict.get('OPENDAP'),
                'WCS_URL': nc_distribution_dict.get('WCS'),
                'WMS_URL': nc_distribution_dict.get('WMS'),
                'ZIP_HTTP_URL': zip_distribution_dict.get('HTTPServer'),
            }
            logger.debug('template_dict = %s' % template_dict)

            # Read XML template file
            distributionInfo_template_file = open(
                '../templates/distributionInfo_template.xml')
            distributionInfo_template_text = distributionInfo_template_file.read()
            distributionInfo_template_file.close()

            # Perform any global substitutions
            distributionInfo_template_text.replace(
                'sales@ga.gov.au', 'clientservices@ga.gov.au')

            # Perform specialised text substitutions
            for key in sorted(template_dict.keys()):
                if template_dict[key] is None:
                    print 'WARNING: %s not set in template XML' % key
                else:
                    distributionInfo_template_text = re.sub(
                        '%%%%%s%%%%' %
                        key,
                        template_dict[key],
                        distributionInfo_template_text)

            #print distributionInfo_template_text
            source_distributionInfo_tree = etree.fromstring(distributionInfo_template_text).find(
                path='mdb:distributionInfo', namespaces=xml_tree.nsmap)

            # Purge any distributionFormat with un-substituted expressions
            source_MD_Distribution_tree = source_distributionInfo_tree.find(
                path='mrd:MD_Distribution', namespaces=xml_tree.nsmap)
            for source_distributionFormat_tree in source_MD_Distribution_tree.iterfind(
                    path='mrd:distributionFormat', namespaces=xml_tree.nsmap):
                for text in source_distributionFormat_tree.itertext():
                    if re.search('%.*%', text):
                        print 'Removing incomplete distributionFormat %s from updated template XML' % source_distributionFormat_tree.tag
                        source_MD_Distribution_tree.remove(
                            source_distributionFormat_tree)
                        break

            # Create or replace distributionInfo element
            dest_distributionInfo_tree = xml_tree.find(
                path='mdb:distributionInfo', namespaces=xml_tree.nsmap)
            if dest_distributionInfo_tree is None:
                print 'Creating new distributionInfo subtree from template'
                xml_tree.append(source_distributionInfo_tree)
            else:
                #            xml_tree.replace(dest_distributionInfo_tree, distributionInfo_template_tree)
                dest_MD_Distribution_tree = dest_distributionInfo_tree.find(
                    path='mrd:MD_Distribution', namespaces=xml_tree.nsmap)
                if dest_MD_Distribution_tree is None:  # Destination mrd:MD_Distribution not found
                    print 'Creating new mrd:MD_Distribution subtree from template'
                    dest_distributionInfo_tree.append(
                        source_MD_Distribution_tree)
                else:
                    print 'Adding or replacing individual mrd:distributionFormat subtrees from template'
                    source_distributionFormat_count = 0
                    replaced_distributionFormat_count = 0
                    new_distributionFormat_count = 0

                    for source_distributionFormat_tree in source_MD_Distribution_tree.iterfind(
                            path='mrd:distributionFormat', namespaces=xml_tree.nsmap):
                        source_distributionFormat_count += 1
                        source_OnlineResource_tree = source_distributionFormat_tree.find(
                            path='.//cit:CI_OnlineResource', namespaces=xml_tree.nsmap)
                        assert source_OnlineResource_tree is not None, 'Unable to find source cit:CI_OnlineResource under mrd:distributionFormat'

                        source_protocol = source_OnlineResource_tree.find(
                            'cit:protocol', namespaces=xml_tree.nsmap).find(
                            'gco:CharacterString', namespaces=xml_tree.nsmap).text
                        source_linkage = source_OnlineResource_tree.find(
                            'cit:linkage', namespaces=xml_tree.nsmap).find(
                            'gco:CharacterString', namespaces=xml_tree.nsmap).text
                        match = re.match(
                            '(\w+)://([^/]*)((/[^/\?]+){0,2}).*/([^/]+)$', source_linkage)
                        if match is None:
                            print 'Unable to parse %s' % source_linkage
                            continue

                        source_link_protocol = match.group(1)
                        source_host = match.group(2)
                        source_dir = match.group(3)
                        source_file = match.group(5)

    # print 'Processing %s: protocol=%s, link_protocol=%s, host=%s, root=%s,
    # file=%s' % (source_linkage, source_protocol, source_link_protocol,
    # source_host, source_dir, source_file)

                        # Check all distributions for match
                        distribution_match_found = False
                        for dest_distributionFormat_tree in dest_MD_Distribution_tree.iterfind(
                                path='mrd:distributionFormat', namespaces=xml_tree.nsmap):
                            dest_OnlineResource_tree = dest_distributionFormat_tree.find(
                                path='.//cit:CI_OnlineResource', namespaces=xml_tree.nsmap)
                            assert dest_OnlineResource_tree is not None, 'Unable to find destination cit:CI_OnlineResource'

                            dest_protocol = dest_OnlineResource_tree.find(
                                'cit:protocol', namespaces=xml_tree.nsmap).find(
                                'gco:CharacterString', namespaces=xml_tree.nsmap).text
                            dest_linkage = dest_OnlineResource_tree.find(
                                'cit:linkage', namespaces=xml_tree.nsmap).find(
                                'gco:CharacterString', namespaces=xml_tree.nsmap).text
                            match = re.match(
                                '(\w+)://([^/]*)((/[^/\?]+){0,2}).*/([^/]+)$', dest_linkage)
                            if match is None:
                                print 'Unable to parse %s' % dest_linkage
                                continue

                            dest_link_protocol = match.group(1)
                            dest_host = match.group(2)
                            dest_dir = match.group(3)
                            dest_file = match.group(5)

    # print 'Checking %s: protocol=%s, link_protocol=%s, host=%s, root=%s,
    # file=%s' % (dest_linkage, dest_protocol, dest_link_protocol, dest_host,
    # dest_dir, dest_file)

                            # Determine match based on protocol, host and file
                            distribution_match_found = (((source_protocol == dest_protocol) and
                                                         (source_link_protocol == dest_link_protocol) and
                                                         (source_host == dest_host) and
                                                         (source_dir == dest_dir) and
                                                         (source_file == dest_file))
                                                        or
                                                        ((re.search('thredds/.*[c|C]atalog', source_dir) is not None) and  # Special case for THREDDS catalog page
                                                         (re.search('thredds/.*[c|C]atalog', dest_dir) is not None) and
                                                         (source_protocol == dest_protocol) and
                                                         (source_link_protocol == dest_link_protocol) and
                                                         (source_file == dest_file)))

                            if distribution_match_found:  # Update existing distribution
                                # print 'Match found %s: protocol=%s,
                                # link_protocol=%s, host=%s, dir=%s, file=%s' %
                                # (dest_linkage, dest_protocol,
                                # dest_link_protocol, dest_host, dest_dir,
                                # dest_file)
                                dest_MD_Distribution_tree.replace(
                                    dest_distributionFormat_tree, source_distributionFormat_tree)
                                replaced_distributionFormat_count += 1
                                break

                        if not distribution_match_found:  # Add new distribution
                            # print 'No match found. Adding new
                            # mrd:distributionFormat subtree for %s' %
                            # source_linkage
                            dest_MD_Distribution_tree.append(
                                source_distributionFormat_tree)
                            new_distributionFormat_count += 1

            print '%d complete distributions from template. %d replaced and %d added. %d final distributions' % (source_distributionFormat_count,
                                                                                                                 replaced_distributionFormat_count,
                                                                                                                 new_distributionFormat_count,
                                                                                                                 len(
                                                                                                                     dest_MD_Distribution_tree)
                                                                                                                 )

        if not nc_path.startswith('http'):
            nc_path = os.path.abspath(nc_path)

        # Read required values from NetCDF file
        nc_dataset = netCDF4.Dataset(nc_path)

        try:
            uuid = nc_dataset.uuid
        except:
            raise Exception('UUID not found in %s' % nc_path)

        try:
            doi = nc_dataset.doi
        except:
            raise Exception('DOI not found in %s' % nc_path)

        print 'Processing Dataset %s with UUID %s' % (nc_path, uuid)
        
        xml_path = os.path.abspath(os.path.join(self.xml_dir, '%s.xml' % os.path.splitext(os.path.basename(nc_path))[0]))

        # Read XML from file if it exists
        if os.path.isfile(xml_path):
            xml_file = open(xml_path, 'r')
            xml_text = xml_file.read()
            xml_file.close()
        else: # Get XML from web service query
            xml_text = get_xml_from_uuid(geonetwork_url, uuid)
            
        # Attempt to read XML text into etree
        try:
            xml_tree = etree.fromstring(xml_text)
        except Exception as e:
            print xml_text
            raise e
        
        logger.debug('xml_text = %s' % xml_text)

        # Create backup directory if it doesn't exist
        backup_dir = os.path.abspath(os.path.join(self.xml_dir, 'backup'))
        if not os.path.isdir(backup_dir):
            os.mkdir(backup_dir) 
                                                   
        # Write original XML into backup file
        backup_path = os.path.join(backup_dir, '%s.bck' % os.path.basename(xml_path))
        backup_file = open(backup_path, 'w')
        backup_file.write(prettify_xml(xml_text)) # Maybe this shouldn't be prettified
        backup_file.close()
        
        if self.update_bounds:
            update_bounds(nc_dataset, xml_tree)

        nc_dataset.close()  # Finished reading stuff from NetCDF file - close it

        if self.update_distributions:
            update_distributions(xml_tree)

        xml_file = open(xml_path, 'w')
   
        xml_file.write(prettify_xml(etree.tostring(xml_tree, 
                                                        encoding="utf-8",
                                                        pretty_print=False,
                                                        with_tail=False
                                                        )
                                         )
                       )

        xml_file.close()
        print 'Finished writing XML to file %s' % xml_path
        
def main():
    # Define command line arguments
    parser = argparse.ArgumentParser()
    
    parser.add_argument("-n", "--netcdf_dir", help="NetCDF root directory", type=str, required=True)
    parser.add_argument("-f", "--file_template", help='NetCDF filename template (default="*.nc")', type=str, default="*.nc")
    parser.add_argument("-g", "--geonetwork_url", help="GeoNetwork URL for metadata", type=str, required=True)
    parser.add_argument("-x", "--xml_dir", help="XML input/output directory", type=str, required=True)
    parser.add_argument("-t", "--thredds_root_urls", help="Comma-separated list of THREDDS root URLs to search", type=str)
    parser.add_argument('-b', '--update_bounds', 
                        dest='update_bounds', 
                        action='store_const', 
                        const=True, default=False,
                        help='Boolean flag to update geospatial bounds in metadata record from netCDF')
    parser.add_argument('-d', '--update_distributions', 
                        dest='update_distributions', 
                        action='store_const', 
                        const=True, default=False,
                        help='Boolean flag to update online distributions in metadata record from THREDDS catalogue')
    
    
    args = parser.parse_args()


    xml_updater = XMLUpdater(args.geonetwork_url, 
                             thredds_root_urls=args.thredds_root_urls, 
                             update_bounds=args.update_bounds, 
                             update_distributions=args.update_distributions, 
                             xml_dir=args.xml_dir)

    for nc_path in find_files(args.netcdf_dir, args.file_template):
        if True:#try:
            xml_updater.update_xml(nc_path, args.geonetwork_url)
        else:#except Exception as e:
            print 'XML update failed for %s:\n%s' % (nc_path, e.message)


if __name__ == '__main__':
    main()
