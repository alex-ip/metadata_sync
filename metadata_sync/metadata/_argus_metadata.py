#!/usr/bin/env python

"""Argus Metadata module

Author: Alex Ip (alex.ip@ga.gov.au)
Written: 5/7/2016
"""
# TODO: Check potential issues with unicode vs str

import logging
import cx_Oracle
import os
import re
import sys
from pprint import pprint

from _metadata import Metadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Initial logging level for this module

class ArgusMetadata(Metadata):
    """Subclass of Metadata to manage Argus data
    """
    
        # Class variable holding metadata type string
    _metadata_type_id = 'Argus'
    _filename_pattern = '.*'  # Default RegEx for finding metadata file.

    # Murray's Argus query
    # N.B: Need to use text substitution for multiple survey IDs - can't use parameterised query
    ARGUS_QUERY = '''SELECT
       A.SURVEYS.SURVEYID,
       A.SURVEYS.SURVEYNAME,
       A.SURVEYS.STATE,
       A.SURVEYS.OPERATOR,
       A.SURVEYS.CONTRACTOR,
       A.SURVEYS.PROCESSOR,
       DECODE(ARGUS.AIRSURVEYS.SURVEY_TYPE,'DETL','Detailed',
                                'NGMA','NGMA',
                                'REGN','Regional',
                                'SEMI-DETL','Semi-detailed',
                                ARGUS.AIRSURVEYS.SURVEY_TYPE) as SURVEY_TYPE,
        A.SURVEYS.DATATYPES,
        A.SURVEYS.VESSEL,
        DECODE(A.SURVEYS.VESSEL_TYPE,'FW', 'Plane',
                           'RW', 'Helicopter',
                           'FW/RW', 'Plane and Helicopter',
                           A.SURVEYS.VESSEL_TYPE) as VESSEL_TYPE,
        A.SURVEYS.RELEASEDATE,
        A.SURVEYS.ON_OFF || 'shore' as ONSHORE_OFFSHORE,
        A.SURVEYS.STARTDATE,
        A.SURVEYS.ENDDATE,
        A.SURVEYS.WLONG,
        A.SURVEYS.ELONG,
        A.SURVEYS.SLAT,
        A.SURVEYS.NLAT,
        ARGUS.AIRSURVEYS.LINE_KM,
        ARGUS.AIRSURVEYS.TOT_KM as TOTAL_KM,
        A.SURVEYS.SPACEMIN as LINE_SPACING,
        ARGUS.AIRSURVEYS.LINE_DIR AS LINE_DIRECTION,
        ARGUS.AIRSURVEYS.TIE_SPG as TIE_SPACING,
        ARGUS.AIRSURVEYS.AREA as SQUARE_KM,
        ARGUS.AIRRAD.XT_VOL as CRYSTAL_VOLUME,
        ARGUS.AIRRAD.XT_VUP as UP_CRYSTAL_VOLUME,
        ARGUS.AIRSURVEYS.DIGITAL_DATA,
        A.SURVEYS.GEODETIC_DATUM,
        ARGUS.AIRSURVEYS.ASL,
        ARGUS.AIRSURVEYS.AGL,
        ARGUS.AIRMAG.INSTRUMENT MAG_INSTRUMENT,
        ARGUS.AIRRAD.INSTRUMENT RAD_INSTRUMENT
from a.surveys
join a.entities using (eno)
join a.entity_types using (entity_type)
join argus.airsurveys using (eno)
left join argus.airdem using (eno)
left join argus.airmag using (eno)
left join argus.airrad using (eno)
where A.SURVEYS.SURVEYID in ({SURVEY_IDS})'''
    
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
        return (ArgusMetadata.state_dict.get(state_tag[0]) or 
                ArgusMetadata.state_dict.get(state_tag[0:2]) or 
                state_tag)

    def __init__(self, db_user, db_password, db_alias, source=None):
        """Instantiates ArgusMetadata object. Overrides Metadata method
        """
        self._metadata_dict = {}

        self.argus_fields = None
                
        self.connection = cx_Oracle.connect('%s/%s@%s' % (db_user, db_password, db_alias))
        self.cursor = self.connection.cursor()
        
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
                    self.read_Argus_metadata(survey_ids)

                                     

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
            
    def read_Argus_metadata(self, survey_ids):
        '''Read metadata from Argus query
        '''
            
        logger.info('Reading metadata from Argus query with survey IDs %s', survey_ids)

        # N.B: Need to use text substitution for multiple survey IDs - can't use parameterised query
        SQL = ArgusMetadata.ARGUS_QUERY.format(**{'SURVEY_IDS': 
                                                  ', '.join(["'" + str(survey_id) + "'"
                                                             for survey_id in survey_ids
                                                             ]
                                                            )
                                                  }
                                               )
        query_result = self.cursor.execute(SQL)
        
        if not self.argus_fields:
            self.argus_fields = [field_desc[0] for field_desc in query_result.description]
                
        for argus_record in query_result:
            #print argus_record
            survey_metadata_dict = dict(zip(self.argus_fields, [str(field) if field else '' 
                                                                for field in argus_record
                                                                ]
                                            )
                                        )
            self.merge_metadata_dict(survey_metadata_dict)

    def read_file(self, filename=None):
        '''
        Function to read Argus metadata from query and store the results in self._metadata_dict
        using survey_id(s) parsed from filename
        Only included for compatibility with file-based metadata
        Argument:
            filename: Argus survey_id to query
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
            
        dataset_type = ArgusMetadata.type_dict.get(match.groups()[0].lower())
        state = self.decode_state(match.groups()[1].upper())
        
        survey_ids = [survey_id for survey_id in [int(survey_id) 
                                                  for survey_id in re.sub('\D+', ' ', basename).strip().split(' ')
                                                  ]
                      if survey_id > ArgusMetadata.MIN_SURVEY_ID
                      ]

        self.read_Argus_metadata(survey_ids)
        
        self._filename = filename
        
        argus_states = self.get_metadata('STATE')
        if state not in argus_states:
            logger.warning('Filename state "%s" inconsistent with Argus state "%s"' % (state, argus_states))

        argus_dataset_types = self.get_metadata('DATATYPES')
        if dataset_type not in argus_dataset_types:
            logger.warning('Filename dataset type "%s" inconsistent with Argus dataset type "%s"' % (dataset_type, argus_dataset_types))

        return self._metadata_dict

    def write_file(self, filename=None, save_backup=False):
        """Function write the metadata contained in self._metadata_dict to an Argus file
        Argument:
            filename: Metadata file to be written
        """
        assert False, 'Argus metadata is read-only'


def main():
    '''
    Main function for quick and dirty testing
    '''
    am = ArgusMetadata(*sys.argv[1:])
    pprint(am.metadata_dict)

if __name__ == '__main__':
    main()
