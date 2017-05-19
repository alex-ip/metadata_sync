'''
geophysics_survey_metadata_record_creator.py
XML Metadata record creator for geophysical survey datasets

Created on May 17, 2017
Refactored from create_xml_metadata.py

@author: Alex Ip, Geoscience Australia
'''
import netCDF4
import re
import os
import uuid
from datetime import datetime
import argparse
import logging
from metadata_sync.metadata import SurveyMetadata, NetCDFMetadata #, JetCatMetadata
from geophys_utils import NetCDFGridUtils, NetCDFLineUtils
from metadata_sync.metadata import TemplateMetadata
from metadata_json import read_json_metadata

from metadata_sync.metadata_record_creator import MetadataRecordCreator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Initial logging level for this module


# Try to import Oracle metadata reader - will fail if no cx_Oracle package installed
try:
    from metadata_sync.metadata import ArgusMetadata
except:
    pass

class GeophysicsSurveyMetadataRecordCreator(MetadataRecordCreator):
    '''
    Class definition
    '''
    def __init__(self, xml_template_path, xml_output_path, netcdf_path, json_text_template_path,
                 doi_minting_mode = 'test',
                 db_user=None, db_password=None, db_alias=None):
        '''
        GeophysicsSurveyMetadataRecordCreator Constructor
        '''
        MetadataRecordCreator.__init__(self, xml_template_path, xml_output_path, doi_minting_mode) # Call base class consstructor
        
        self.netcdf_path = netcdf_path
        self.netcdf_dataset = netCDF4.Dataset(self.netcdf_path, 'r+') # Allow for updating of netCDF attributes like uuid
        
        self.json_text_template_path = json_text_template_path
        
        self.db_user = db_user
        self.db_password = db_password
        self.db_alias = db_alias
    

    def read_metadata(self):
        '''
        Function to read metadata from netCDF file, survey API or Oracle DB into common framework
        '''
        # Read metadata from NetCDF file
        netcdf_metadata = NetCDFMetadata()
        netcdf_metadata.read_netcdf_metadata(self.netcdf_dataset)
        self.metadata_object.merge_root_metadata_from_object(netcdf_metadata)

        # JetCat and Survey metadata can either take a list of survey IDs as source(s) or a filename from which to parse them
        try:
            survey_ids = self.netcdf_dataset.survey_id
            logger.info('Survey ID "%s" found in netCDF attributes' % survey_ids)
            source = [int(value_string.strip()) for value_string in survey_ids.split(',') if value_string.strip()]
        except:
            source = self.netcdf_path
    
    #    jetcat_metadata = JetCatMetadata(source, jetcat_path=jetcat_path)
    #    metadata_object.merge_root_metadata_from_object(jetcat_metadata)
    
        try:
            survey_metadata = SurveyMetadata(source)
            self.metadata_object.merge_root_metadata_from_object(survey_metadata)
        except Exception as e:
            logger.warning('Unable to read from Survey API:\n%s\nAttempting direct Oracle DB read' % e.message)
            try:
                survey_metadata = ArgusMetadata(self.db_user, self.db_password, self.db_alias, source) # This will fail if we haven't been able to import ArgusMetadata 
                self.metadata_object.merge_root_metadata('Survey', survey_metadata.metadata_dict, overwrite=True) # Fake Survey metadata from DB query
            except Exception as e:
                logger.error('Unable to perform direct Oracle DB read: %s' % e.message)
    
        survey_id = self.metadata_object.get_metadata(['Survey', 'SURVEYID'])
        try:
            dataset_survey_id = str(self.netcdf_dataset.survey_id)
            assert (set([int(value_string.strip()) for value_string in dataset_survey_id.split(',') if value_string.strip()]) == 
                    set([int(value_string.strip()) for value_string in survey_id.split(',') if value_string.strip()])), 'NetCDF survey ID %s is inconsistent with %s' % (dataset_survey_id, survey_id)
        except:
            self.netcdf_dataset.survey_id = str(survey_id)
            self.netcdf_dataset.sync()
            logger.info('Survey ID %s written to netCDF file' % survey_id)

    
    def populate_template_values(self):
        '''
        '''
        def get_uuid():
                    
            dataset_uuid = self.metadata_object.get_metadata(['NetCDF', 'uuid'])
            
            if dataset_uuid: # UUID read from netCDF file - all good
                return dataset_uuid
            
            try:
                dataset_uuid = read_json_metadata(os.path.dirname(self.netcdf_path)).get('uuid')
            except:
                logger.warning('Unable to read UUID from metadata.json file')
            
            if not dataset_uuid:
                # Create a new UUID and write it to the netCDF file 
                dataset_uuid = str(uuid.uuid4())
                logger.debug('dataset_uuid = %s' % dataset_uuid)
                
            self.netcdf_dataset.uuid = dataset_uuid
            self.netcdf_dataset.sync()
            logger.info('UUID %s written to netCDF file' % dataset_uuid)
                
            return dataset_uuid   
        
        def get_doi():
            # Need to populate temporary template before minting DOI
            template_metadata_object = TemplateMetadata(self.json_text_template_path, self.metadata_object)
            dataset_doi = self.get_doi(template_metadata_object, 
                                       self.doi_minting_mode,
                                       ) 
            logger.info('DOI "%s" minted' % dataset_doi)
            if dataset_doi and self.doi_minting_mode == 'prod':
                self.netcdf_dataset.doi = dataset_doi
                self.netcdf_dataset.sync()
                logger.info('Freshly-minted DOI "%s" written to NetCDF file' % dataset_doi)
        
            return dataset_doi
        
        
        calculated_values = {}
        # Splice the calculated_values dict directly into self.metadata_object.metadata_dict 
        self.metadata_object.metadata_dict['Calculated'] = calculated_values 
        
        calculated_values['FILENAME'] = os.path.basename(self.netcdf_path)
        
        try: # Try to treat this as a gridded dataset
            netcdf_utils = NetCDFGridUtils(self.netcdf_dataset)
            logger.info('%s is a gridded dataset' % self.netcdf_path)
        
            #calculated_values['CELLSIZE'] = str((nc_grid_utils.pixel_size[0] + nc_grid_utils.pixel_size[1]) / 2.0)
            calculated_values['CELLSIZE_M'] = str(int(round((netcdf_utils.nominal_pixel_metres[0] + netcdf_utils.nominal_pixel_metres[1]) / 20.0) * 10))
            calculated_values['CELLSIZE_DEG'] = str(round((netcdf_utils.nominal_pixel_degrees[0] + netcdf_utils.nominal_pixel_degrees[1]) / 2.0, 8))
    
        except: # Try to treat this as a line dataset
            netcdf_utils = NetCDFLineUtils(self.netcdf_dataset)
            logger.info('%s is a line dataset' % self.netcdf_path)
            
        WGS84_extents = [min([coordinate[0] for coordinate in netcdf_utils.wgs84_bbox]),
                         min([coordinate[1] for coordinate in netcdf_utils.wgs84_bbox]),
                         max([coordinate[0] for coordinate in netcdf_utils.wgs84_bbox]),
                         max([coordinate[1] for coordinate in netcdf_utils.wgs84_bbox])
                         ]
            
        calculated_values['WLON'] = str(WGS84_extents[0])
        calculated_values['SLAT'] = str(WGS84_extents[1])
        calculated_values['ELON'] = str(WGS84_extents[2])
        calculated_values['NLAT'] = str(WGS84_extents[3])
        
        try:
            calculated_values['START_DATE'] = min(self.str2datelist(str(self.metadata_object.get_metadata(['Survey', 'STARTDATE'])))).isoformat()
        except ValueError:
            calculated_values['START_DATE'] = None   
        
        try:
            calculated_values['END_DATE'] = max(self.str2datelist(str(self.metadata_object.get_metadata(['Survey', 'ENDDATE'])))).isoformat()
        except ValueError:
            calculated_values['END_DATE'] = None 
        
        # Find survey year from end date isoformat string
        try:
            calculated_values['YEAR'] = re.match('^(\d{4})-', calculated_values['END_DATE']).group(1)
        except:
            calculated_values['YEAR'] = 'UNKNOWN' 
        
        #history = "Wed Oct 26 14:34:42 2016: GDAL CreateCopy( /local/el8/axi547/tmp/mWA0769_770_772_773.nc, ... )"
        #date_modified = "2016-08-29T10:51:42"
        try:
            try:
                conversion_datetime_string = re.match('^(.+):.*', str(self.metadata_object.get_metadata(['NetCDF', 'history']))).group(1)
                conversion_datetime_string = datetime.strptime(conversion_datetime_string, '%a %b %d %H:%M:%S %Y').isoformat()
            except:
                conversion_datetime_string = self.metadata_object.get_metadata(['NetCDF', 'date_modified']) or 'UNKNOWN'
        except:
            conversion_datetime_string = 'UNKNOWN'
            
        calculated_values['CONVERSION_DATETIME'] = conversion_datetime_string
    
        calculated_values['UUID'] = get_uuid()
        
        calculated_values['DOI'] = self.metadata_object.get_metadata(['NetCDF', 'doi'])
        
        if not calculated_values['DOI']:
            calculated_values['DOI'] = get_doi()

        # Populate final template
        template_metadata_object = TemplateMetadata(self.json_text_template_path, self.metadata_object)
        self.metadata_object.merge_root_metadata_from_object(template_metadata_object)
    
def main():
    # Define command line arguments
    parser = argparse.ArgumentParser()
    
    parser.add_argument("-j", "--json_template", help="JSON text template path", type=str, required=True)
    parser.add_argument("-t", "--xml_template", help="XML template path", type=str, required=True)
    parser.add_argument("-n", "--netcdf", help="netcdf file path", type=str, required=True)
    parser.add_argument("-o", "--output", help="XML output path", type=str, required=True)
    parser.add_argument("-m", "--doi_mode", help="DOI minting mode (test or prod)", type=str, default='test')
    parser.add_argument("-d", "--db_alias", help="Oracle DB alias (optional)", type=str)
    parser.add_argument("-u", "--db_user", help="Oracle DB user (optional)", type=str)
    parser.add_argument("-p", "--db_password", help="Oracle DB password (optional)", type=str)
    
    args = parser.parse_args()
    
    record_creator = GeophysicsSurveyMetadataRecordCreator(xml_template_path=args.xml_template,
                                                           xml_output_path=args.output, 
                                                           netcdf_path=args.netcdf, 
                                                           json_text_template_path=args.json_template,
                                                           doi_minting_mode=args.doi_mode,
                                                           db_alias=args.db_alias,
                                                           db_user=args.db_user, 
                                                           db_password=args.db_password
                                                           )
        
    logger.debug('record_creator.__dict__ = %s' % record_creator.__dict__)
    record_creator.output_xml()

if __name__ == '__main__':
    main()
