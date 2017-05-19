#!/usr/bin/env python

"""JetCat Metadata module

Author: Alex Ip (alex.ip@ga.gov.au)
Written: 5/7/2016
"""
# TODO: Check potential issues with unicode vs str

import logging
import os
import re
import sys
from pprint import pprint

from _metadata import Metadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Initial logging level for this module

class JetCatMetadata(Metadata):
    """Subclass of Metadata to manage JetCat data
    """
    
        # Class variable holding metadata type string
    _metadata_type_id = 'JetCat'
    _filename_pattern = '.*'  # Default RegEx for finding metadata file.
    
    JETCAT_PATH = '\\\\nas\\cdsm\\application\\GADDS\\JETCAT.dat' # Only works within GA

    JETCAT_FIELDS = [
        'NAME',
        'LON1',   
        'LAT1',   
        'LON2',   
        'LAT2',   
        'LON3',   
        'LAT3',   
        'LON4',   
        'LAT4',   
        'CS',   
        'THEME',   
        'DATATYPE',   
        'KSIZE',   
        'DODS_URL',   
        'LABEL',   
        'DATE',   
        'CELLSIZE',   
        'FLAVOUR',   
        'LINESPACING',   
        'SURVEYID',   
        'CSDATA',   
        'LICENCENO',   
        'CELLSIZE_M',   
        ]

    THEME_DICT = {'g': 'GRAVITY',
                 'm': 'MAGNETICS',
                 'r': 'RADIOMETRICS'
                }
    
    STATE_DICT = {'V': 'VIC',
                  'NS': 'NSW',
                  'A': 'ACT',
                  'Q': 'QLD',
                  'NT': 'NT',
                  'W': 'WA',
                  'S': 'SA',
                  'T': 'TAS'
                 }
    
    MIN_SURVEY_ID = 20

    def decode_state(self, state_tag):
        return (JetCatMetadata.STATE_DICT.get(state_tag[0]) or 
                JetCatMetadata.STATE_DICT.get(state_tag[0:2]) or 
                state_tag)

    def __init__(self, source=None, theme=None, jetcat_path=None):
        """Instantiates JetCatMetadata object. Overrides Metadata method
        """
        self._metadata_dict = {}
        
        self.jetcat_fields = None

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
                            self.read_file(source, jetcat_path) # Parse survey IDs from filename
                        
                if survey_ids:
                    self.read_jetcat_metadata(survey_ids, theme=theme, jetcat_path=jetcat_path)
                

    def list_from_string(self, comma_separated_string):
        '''
        Helper function to return a list of strings from a string containing a comma separated list
        '''
        if comma_separated_string:
            return [value_string.strip() for value_string in comma_separated_string.split(',') if value_string.strip()]
        else:
            return []
    
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
            
    def read_jetcat_metadata(self, survey_ids, theme=None, jetcat_path=None):
        jetcat_path = jetcat_path or JetCatMetadata.JETCAT_PATH
        
        jetcat_file = open(jetcat_path, 'r')
        self.jetcat_fields = None
        for line in jetcat_file:
            line = line.replace('\n', '')
            values = [value.strip() for value in line.split('\t')]
            
            if self.jetcat_fields is None: # First line contains headers
                self.jetcat_fields = [value.upper() for value in values] # Convert headers to upper case
                assert self.jetcat_fields == JetCatMetadata.JETCAT_FIELDS, 'Invalid JetCat file format'
                continue
            
            jetcat_values = dict(zip(self.jetcat_fields, values))
            
            try:
                survey_id = int(jetcat_values['SURVEYID'])
            except:
                survey_id = None
            
            if survey_id in survey_ids and  (not theme or theme in self.list_from_string(jetcat_values['THEME'])):
                self.merge_metadata_dict(jetcat_values)
    

    def read_file(self, filename=None, jetcat_path=None):
        '''
        Function to read JetCat metadata from query and store the results in self._metadata_dict
        using survey_id(s) parsed from filename
        Only included for compatibility with file-based metadata
        Argument:
            filename: Dataset filename to look up in jetcat file
        Returns:
            nested dict containing metadata

        '''
        logger.debug('read_file(%s) called', filename)
        
        if not filename:
            return

        basename = os.path.splitext(os.path.basename(filename))[0]
        
        match = re.match('([a-z])(\D+)', basename)
        if not match:
            return
            
        try:
            theme = JetCatMetadata.THEME_DICT.get(match.groups()[0].lower())
        except:
            theme = None

#        state = self.decode_state(match.groups()[1].upper())
        
        survey_ids = [int(survey_id) for survey_id in re.sub('\D+', ' ', basename).strip().split(' ')]

        self.read_jetcat_metadata(survey_ids, theme=theme, jetcat_path=jetcat_path)
        
        self._filename = filename
        
#===============================================================================
#         jetCat_states = self.get_metadata('STATE')
#         if state not in jetCat_states:
#             logger.warning('Filename state "%s" inconsistent with JetCat state "%s"' % (state, jetCat_states))
# 
#         jetCat_dataset_types = self.get_metadata('DATATYPES')
#         if dataset_type not in jetCat_dataset_types:
#             logger.warning('Filename dataset type "%s" inconsistent with JetCat dataset type "%s"' % (dataset_type, jetCat_dataset_types))
#===============================================================================

        return self._metadata_dict

    def write_file(self, filename=None, save_backup=False):
        """Function write the metadata contained in self._metadata_dict to a JetCat file
        Argument:
            filename: Metadata file to be written
        """
        assert False, 'JetCat metadata is read-only'


def main():
    '''
    Main function for quick and dirty testing
    '''
    jm = JetCatMetadata(*sys.argv[1:])
    pprint(jm.metadata_dict)

if __name__ == '__main__':
    main()
