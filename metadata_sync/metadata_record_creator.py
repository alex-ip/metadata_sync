'''
Created on Apr 7, 2016

@author: Alex Ip, Geoscience Australia
'''
import re
import os
from datetime import datetime
from xml.dom.minidom import parseString
from jinja2 import Environment, FileSystemLoader, select_autoescape
from metadata_sync.metadata import Metadata
from minter import Minter
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Initial logging level for this module


class MetadataRecordCreator(object):
    '''
    Class definition
    '''
    def __init__(self, xml_template_path, xml_output_path, doi_minting_mode='test'):
        '''
        Base class MetadataRecordCreator constructor
        '''
        self.metadata_object = Metadata()
        
        self.xml_template_path = xml_template_path
        self.xml_output_path = xml_output_path
        self.doi_minting_mode = doi_minting_mode
        

    def prettify_xml(self, xml_text):
        '''
        Helper function to return a prettified XML string
        '''
        return parseString(xml_text).toprettyxml(indent="", 
                                                 newl="", 
                                                 encoding="utf-8"
                                                 )        
    
    def get_xml_text(self):
        '''
        Function to perform substitutions on XML template text AFTER building self.metadata_object contents
        '''
        #template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
        template_dir = os.path.dirname(self.xml_template_path)
        
        jinja_environment = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']
                                         )
                                        )
            
        xml_template = jinja_environment.get_template(os.path.basename(self.xml_template_path), parent=None)
        
        # Call functions to read available metadata and populate template values
        self.read_metadata()
        self.populate_template_values()        
            
        value_dict = dict(self.metadata_object.metadata_dict['Template']) # Copy template values
        
        # Convert multiple sets of comma-separated lists to lists of strings to a list of dicts
        #TODO: Make this slicker
        value_dict['keywords'] = []
        for keyword_list_key in [key for key in value_dict.keys() if re.match('^KEYWORD_\w+_LIST$', key)]:
            keywords = [keyword.strip() for keyword in value_dict[keyword_list_key].split(',')]
            keyword_code = value_dict[re.sub('_LIST$', '_CODE', keyword_list_key)]
            
            value_dict['keywords'] += [{'value': keyword,
                                        'code': keyword_code
                                        } for keyword in keywords
                                       ]
        
        # Create dict containing distribution info for DOI if required
        value_dict['distributions'] = []
        dataset_doi = self.metadata_object.get_metadata(['Calculated', 'DOI'])
        if dataset_doi:
            try:
                distribution_dict = {'formatSpecification': 'html',
                                     'distributor_name': self.metadata_object.get_metadata(['Template', 'ORGANISATION_NAME']),
                                     'distributor_telephone': self.metadata_object.get_metadata(['Template', 'ORGANISATION_PHONE']),
                                     'distributor_address': self.metadata_object.get_metadata(['Template', 'ORGANISATION_ADDRESS']),
                                     'distributor_city': self.metadata_object.get_metadata(['Template', 'ORGANISATION_CITY']),
                                     'distributor_state': self.metadata_object.get_metadata(['Template', 'ORGANISATION_STATE']),
                                     'distributor_postcode': self.metadata_object.get_metadata(['Template', 'ORGANISATION_POSTCODE']),
                                     'distributor_country': self.metadata_object.get_metadata(['Template', 'ORGANISATION_COUNTRY']),
                                     'distributor_email': self.metadata_object.get_metadata(['Template', 'ORGANISATION_EMAIL']),
                                     'url': dataset_doi,
                                     'protocol': 'WWW:LINK-1.0-http--link',
                                     'name': 'Digital Object Identifier for dataset %s' % self.metadata_object.get_metadata(['Calculated', 'UUID']),
                                     'description': 'Dataset DOI'
                                     }
                
                for key, value in distribution_dict.iteritems():
                    assert value, '%s has no value defined' % key
                
                value_dict['distributions'].append(distribution_dict)
            except Exception as e:
                logger.warning('WARNING: Unable to create DOI distribution: %s' % e.message)
        
        logger.debug('value_dict = %s' % value_dict)
        return self.prettify_xml(xml_template.render(**value_dict))
    
    def str2datetimelist(self, multi_datetime_string):
        '''
        Helper function to convert comma-separated string containing dates to a list of datetimes
        '''
        datetime_format_list = ['%d-%b-%y', 
                                '%Y-%m-%dT%H:%M:%S', 
                                '%Y-%m-%dT%H:%M:%S.%f', 
                                '%Y-%m-%dT%H:%M:%S%z', 
                                '%Y-%m-%dT%H:%M:%S.%f%z'
                                ]
        date_list = []
        for datetime_string in multi_datetime_string.split(','):
            for datetime_format in datetime_format_list:
                try:
                    date_list.append(datetime.strptime(datetime_string.strip(), datetime_format))
                    break
                except:
                    continue
        return date_list

    def str2datelist(self, multi_date_string):
        '''
        Helper function to convert comma-separated string containing dates to a list of dates
        '''
        return [datetime_value.date() for datetime_value in self.str2datetimelist(multi_date_string)]
    
    def read_metadata(self):
        '''
        Virtual function
        '''
        pass
    
    def populate_template_values(self):
        '''
        Virtual function to populate template metadata values
        '''
        pass
    
    def output_xml(self):
        
        xml_text = self.get_xml_text()
        logger.debug('xml_text = %s' % xml_text)
        xml_file = open(self.xml_output_path, 'w')
        xml_file.write(xml_text)
        xml_file.close()
        logger.info('XML written to %s' % self.xml_output_path)
        
        
    def get_doi(self, template_metadata_object, doi_minting_mode='test'):
        '''
        Function to populate temporary template_metadata_object and use this to mint a Digital Object Identifier
        '''
        try:
            doi_minter = Minter(doi_minting_mode)       
            doi_success, ecat_id, new_doi = doi_minter.get_a_doi( 
                                                                ecatid=template_metadata_object.get_metadata(["ECAT_ID"]), 
                                                                author_names=template_metadata_object.list_from_string(template_metadata_object.get_metadata(["DATASET_AUTHOR"])), 
                                                                title=template_metadata_object.get_metadata(["DATASET_TITLE"]),
                                                                resource_type='Dataset', 
                                                                publisher=template_metadata_object.get_metadata(["ORGANISATION_NAME"]), 
                                                                publication_year=datetime.now().year, 
                                                                subjects=template_metadata_object.list_from_string(template_metadata_object.get_metadata(["KEYWORD_THEME_LIST"])), 
                                                                description=template_metadata_object.get_metadata(["LINEAGE_SOURCE"]), 
                                                                record_url=None, # Use default URI format
                                                                output_file_path=None
                                                                )
            
            if doi_success:
                dataset_doi = 'http://dx.doi.org/' + str(new_doi)
                return dataset_doi
            else:
                logger.warning('WARNING: DOI minting failed with response code %s' % ecat_id)
        except Exception as e:
            logger.warning('WARNING: Error minting DOI: %s' % e.message)
                   
        return None
    
    
