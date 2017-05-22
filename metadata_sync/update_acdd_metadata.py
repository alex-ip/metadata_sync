'''
Utility to update ACDD global attributes in NetCDF files using metadata sourced from GeoNetwork
Created on Apr 7, 2016

@author: Alex Ip, Geoscience Australia
'''
import os
import netCDF4
import logging
import yaml
import numpy as np
import argparse

from geophys_utils import NetCDFGridUtils, NetCDFLineUtils, get_spatial_ref_from_crs
from metadata_sync.metadata import XMLMetadata
from geophys_utils import DataStats
from metadata_json import write_json_metadata
from _metadata_sync_utils import get_xml_from_uuid, find_files

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Initial logging level for this module

#GA_GEONETWORK_URL = 'https://internal.ecat.ga.gov.au/geonetwork/srv/eng' # internally-visible eCat CSW
GA_GEONETWORK_URL = 'http://ecat.ga.gov.au/geonetwork/srv/eng' # internally-visible eCat CSW
DECIMAL_PLACES = 12 # Number of decimal places to which geometry values should be rounded

# YAML file containing mapping from XML to ACDD expressed as a list of <acdd_attribute_name>:<xpath> tuples
# Note: List may contain tuples with duplicate <acdd_attribute_name> values which are evaluated as a searchlist
DEFAULT_MAPPING_FILE = 'ga_xml2acdd_mapping.yaml' 

def update_nc_metadata(netcdf_path, xml2nc_mapping,  do_stats=False, xml_path=None):
    '''
    Function to import all available metadata and set attributes in NetCDF file.
    Should be overridden in subclasses for each specific format but called first to perform initialisations
    '''
    assert os.path.exists(netcdf_path), 'NetCDF file %s does not exist.' % netcdf_path
        
    try:
        netcdf_dataset = netCDF4.Dataset(netcdf_path, mode='r+')
    except Exception as e:
        logger.error('Unable to open NetCDF file %s: %s',
                     (netcdf_path, e.message))
        raise

    uuid = netcdf_dataset.uuid # This will fail if no uuid attribute found
    
    xml_metadata = XMLMetadata(xml_path)
    if not xml_path: # Need to read XML from catalogue
        xml_metadata.read_string(get_xml_from_uuid(GA_GEONETWORK_URL, uuid))
    
    set_netcdf_metadata_attributes(netcdf_dataset, xml_metadata, xml2nc_mapping, do_stats=do_stats)
    
    netcdf_dataset.close()

    write_json_metadata(uuid, os.path.dirname(netcdf_path))
    logger.info('Finished updating ACDD metadata in netCDF file %s' % netcdf_path)

def set_netcdf_metadata_attributes(netcdf_dataset, xml_metadata, xml2nc_mapping, to_crs='EPSG:4326', do_stats=False):
    '''
    Function to set all NetCDF metadata attributes using xml2nc_mapping to map from XML metadata to ACDD attributes
    Parameter:
        to_crs: EPSG or WKT for spatial metadata
        do_stats: Boolean flag indicating whether minmax stats should be determined (slow)
    '''

    try:
        netcdf_utils = NetCDFGridUtils(netcdf_dataset)
    except:
        netcdf_utils = NetCDFLineUtils(netcdf_dataset)
        
    wgs84_bbox = np.array(netcdf_utils.wgs84_bbox)
    xmin = min(wgs84_bbox[:, 0])
    ymin = min(wgs84_bbox[:, 1])
    xmax = max(wgs84_bbox[:, 0])
    ymax = max(wgs84_bbox[:, 1])
    

    attribute_dict = dict(zip(['geospatial_lon_min', 'geospatial_lat_min', 'geospatial_lon_max', 'geospatial_lat_max'],
                              [xmin, ymin, xmax, ymax]
                              )
                          )
    try:
        attribute_dict['geospatial_lon_resolution'] = netcdf_utils.nominal_pixel_degrees[0]
        attribute_dict['geospatial_lat_resolution'] = netcdf_utils.nominal_pixel_degrees[1]
        attribute_dict['geospatial_lon_units'] = 'degrees'
        attribute_dict['geospatial_lat_units'] = 'degrees'
    except:
        pass

    convex_hull = netcdf_utils.get_convex_hull(to_crs)
    attribute_dict['geospatial_bounds'] = 'POLYGON((' + ', '.join([' '.join(
        ['%.4f' % ordinate for ordinate in coordinates]) for coordinates in convex_hull]) + '))'

    attribute_dict['geospatial_bounds_crs'] = get_spatial_ref_from_crs(to_crs).ExportToPrettyWkt()

    for key, value in attribute_dict.items():
        setattr(netcdf_dataset, key, value)

    # Set attributes defined in self.METADATA_MAPPING
    # Scan list in reverse to give priority to earlier entries
    #TODO: Improve this coding - it's a bit crap
    keys_read = []
    for key, metadata_path in xml2nc_mapping:
        # Skip any keys already read
        if key in keys_read:
            continue

        value = xml_metadata.get_metadata(metadata_path.split('/'))
        if value is not None:
            logger.debug('Setting %s to %s', key, value)
            # TODO: Check whether hierarchical metadata required
            setattr(netcdf_dataset, key, value)
            keys_read.append(key)
        else:
            logger.warning(
                'WARNING: Metadata path %s not found', metadata_path)

    unread_keys = sorted(
        list(set([item[0] for item in xml2nc_mapping]) - set(keys_read)))
    if unread_keys:
        logger.warning(
            'WARNING: No value found for metadata attribute(s) %s' % ', '.join(unread_keys))

    # Ensure only one DOI is stored - could be multiple, comma-separated
    # entries
    if hasattr(netcdf_dataset, 'doi'):
        url_list = [url.strip()
                    for url in netcdf_dataset.doi.split(',')]
        doi_list = [url for url in url_list if url.startswith(
            'http://dx.doi.org/')]
        if len(url_list) > 1:  # If more than one URL in list
            try:  # Give preference to proper DOI URL
                url = doi_list[0]  # Use first (preferably only) DOI URL
            except:
                url = url_list[0]  # Just use first URL if no DOI found
            url = url.replace('&amp;', '&')
            netcdf_dataset.doi = url

    # Set metadata_link to NCI metadata URL
    netcdf_dataset.metadata_link = 'https://pid.nci.org.au/dataset/%s' % netcdf_dataset.uuid

    netcdf_dataset.Conventions = 'CF-1.6, ACDD-1.3'

    if do_stats:
        datastats = DataStats(netcdf_dataset=netcdf_dataset,
                              netcdf_path=None, 
                              max_bytes=netcdf_utils.max_bytes)
        datastats.data_variable.actual_range = np.array(
            [datastats.value('min'), datastats.value('max')], dtype='float32')

    # Remove old fields - remove this later
    if hasattr(netcdf_dataset, 'id'):
        del netcdf_dataset.id
    if hasattr(netcdf_dataset, 'ga_uuid'):
        del netcdf_dataset.ga_uuid
    if hasattr(netcdf_dataset, 'keywords_vocabulary'):
        del netcdf_dataset.keywords_vocabulary
        
    netcdf_dataset.sync()
    

def main():
    # Define command line arguments
    parser = argparse.ArgumentParser()
    
    parser.add_argument("-n", "--netcdf_dir", help="NetCDF root directory", type=str, required=True)
    parser.add_argument("-f", "--file_template", help='NetCDF filename template (default="*.nc")', type=str, default="*.nc")
    parser.add_argument("-m", "--mapping_file", help="XML to ACDD mapping configuration file path", type=str)
    parser.add_argument("-x", "--xml_dir", help="XML directory for input files (optional)", type=str)
    
    args = parser.parse_args()
    
    xml2nc_mapping_path = args.mapping_file or os.path.join(os.path.dirname(__file__), 'config', DEFAULT_MAPPING_FILE)
    
    xml2nc_mapping_file = open(xml2nc_mapping_path)
    xml2nc_mapping = yaml.load(xml2nc_mapping_file)
    xml2nc_mapping_file.close()
    logger.debug('xml2nc_mapping = %s' % xml2nc_mapping)

    
    for nc_path in find_files(args.netcdf_dir, args.file_template):
        logger.info('Updating ACDD metadata in netCDF file %s' % nc_path)
        
        if args.xml_dir:
            xml_path = os.path.abspath(os.path.join(args.xml_dir, os.path.splitext(os.path.basename(nc_path))[0] + '.xml'))
        else:
            xml_path = None

        try:
            update_nc_metadata(nc_path, xml2nc_mapping,  do_stats=True, xml_path=xml_path)
        except Exception as e:
            logger.error('Metadata update failed: %s' % e.message)

if __name__ == '__main__':
    main()
