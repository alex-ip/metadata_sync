#!/usr/bin/env python

"""survey Metadata module

Author: Alex Ip (alex.ip@ga.gov.au)
Written: 5/7/2016
"""
# TODO: Check potential issues with unicode vs str

import logging
import urllib
from lxml import etree
import os
import re
import sys
from pprint import pprint

from _metadata import Metadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Initial logging level for this module

class SurveyMetadata(Metadata):
    """Subclass of Metadata to manage survey data
    """
    
        # Class variable holding metadata type string
    _metadata_type_id = 'Survey'
    _filename_pattern = '.*'  # Default RegEx for finding metadata file.

    SURVEY_URL = 'http://www.ga.gov.au/www/argus.argus_api.survey?pSurveyNo=%d'
    
    MIN_SURVEY_ID = 20

    type_dict = {'g': 'GRAV',
                 'm': 'MAG',
                 'r': 'RAD'
                }
    
    state_dict = {'V': 'VIC',
                  'NS': 'NSW',
                  'A': 'ACT',
                  'Q': 'QLD',
                  'NT': 'NT',
                  'W': 'WA',
                  'S': 'SA',
                  'T': 'TAS'
                 }
    
    def decode_state(self, state_tag):
        return (SurveyMetadata.state_dict.get(state_tag[0]) or 
                SurveyMetadata.state_dict.get(state_tag[0:2]) or 
                state_tag)

    def __init__(self, source=None):
        """Instantiates SurveyMetadata object. Overrides Metadata method
        """
        self._metadata_dict = {}

        self.survey_fields = None
                
        if source:
            if isinstance(source, dict):
                self._metadata_dict = source
            else:
                survey_ids = None
                if type(source) == list: # list of survey_ids provided 
                    survey_ids = source
                else:
                    try: # Try to convert comma separated list to list of integers
                        survey_ids = [int(survey_id) for survey_id in self.list_from_string(source)]
                    except:
                        if type(source) == str:
                            self.read_file(source) # Parse survey IDs from filename
                        
                if survey_ids:
                    self.read_Survey_metadata(survey_ids)

                                     

    def merge_metadata_dict(self, survey_metadata_dict):
        '''
        Helper function to merge new metadata dict into comma-separated lists in 
        existing instance _metadata_dict. Need to avoid duplicates but preserve order.
        '''
        for key, values_string in survey_metadata_dict.iteritems():
            values = self.list_from_string(values_string)
            stored_values = self.list_from_string(self._metadata_dict.get(key) or '')

            self._metadata_dict[key] = ', '.join(stored_values +
                                                 [value for value in values if value not in stored_values]
                                                 )
            
    def read_Survey_metadata(self, survey_ids):
        '''Read metadata from survey API
        '''
        def get_survey_xml(survey_id): 
            return urllib.urlopen(SurveyMetadata.SURVEY_URL % survey_id).read()
              
        logger.info('Reading metadata from survey query with survey IDs %s', survey_ids)

        for survey_id in survey_ids:
            try:
                survey_metadata_dict = {}
                
                xml_text = get_survey_xml(survey_id)
                try:
                    xml_tree = etree.fromstring(xml_text)
                except Exception as e:
                    print xml_text
                    raise e
                    
                row_tree = xml_tree.find('ROW')
                for field_element in row_tree.iterchildren():
                    survey_metadata_dict[field_element.tag] = field_element.text
    
                self.merge_metadata_dict(survey_metadata_dict)
            except Exception as e:
                logger.warning('Unable to retrieve survey metadata for survey ID %d: %s' % (survey_id, e.message))
        
        assert self._metadata_dict, 'No survey metadata retrieved'        

    def read_file(self, filename=None):
        '''
        Function to read survey metadata from query and store the results in self._metadata_dict
        using survey_id(s) parsed from filename
        Only included for compatibility with file-based metadata
        Argument:
            filename: filename parsed to find survey_ids to query
        Returns:
            nested dict containing metadata

        '''
        logger.debug('read_file(%s) called', filename)
        
        if not filename:
            return

        basename = os.path.splitext(os.path.basename(filename))[0]
        
        # Check for conventional gridded dataset filename: e.g. mNSW0409.nc
        match = re.match('([a-z])(\D+)', basename)
        if not match: # Not a gridded filename
            dataset_type = None
            state = None
        else:    
            dataset_type = SurveyMetadata.type_dict.get(match.groups()[0].lower())
            state = self.decode_state(match.groups()[1].upper())
        
        survey_ids = [survey_id for survey_id in [int(survey_id) 
                                                  for survey_id in re.sub('\D+', ' ', basename).strip().split(' ')
                                                  ]
                      if survey_id > SurveyMetadata.MIN_SURVEY_ID
                      ]

        self.read_Survey_metadata(survey_ids)
        
        self._filename = filename
        
        survey_states = self.get_metadata('STATE')
        if state and state not in survey_states:
            logger.warning('Filename state "%s" inconsistent with survey state "%s"' % (state, survey_states))

        survey_dataset_types = self.get_metadata('DATATYPES')
        if dataset_type and dataset_type not in survey_dataset_types:
            logger.warning('Filename dataset type "%s" inconsistent with survey dataset type "%s"' % (dataset_type, survey_dataset_types))

        return self._metadata_dict

    def write_file(self, filename=None, save_backup=False):
        """Function write the metadata contained in self._metadata_dict to an survey file
        Argument:
            filename: Metadata file to be written
        """
        assert False, 'survey metadata is read-only'


def main():
    '''
    Main function for quick and dirty testing
    '''
    am = SurveyMetadata(*sys.argv[1:])
    pprint(am.metadata_dict)

if __name__ == '__main__':
    main()
