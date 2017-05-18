#!/usr/bin/env python

"""ERS Metadata module

Author: Alex Ip (alex.ip@ga.gov.au)
Written: 2/3/2016
"""

import logging
import os
import re

from _metadata import Metadata

logger = logging.getLogger('root.' + __name__)


class ERSMetadata(Metadata):
    """Subclass of Metadata to manage ERS data
    """
    # Class variable holding metadata type string
    _metadata_type_id = 'ERS'
    # Default RegEx for finding metadata file.
    _filename_pattern = '.*\.(ers|isi)'

    def __init__(self, source=None):
        """Instantiates ERSMetadata object. Overrides Metadata method
        """
        Metadata.__init__(self, source)  # Call inherited constructor

    def read_file(self, filename=None):
        '''
        Function to read ERS metadata from .isi or .ers file and store the results in self._metadata_dict
        Argument:
            filename: ERS Metadata file to be parsed and stored
        Returns:
            nested dict containing metadata

        .isi file will be formatted as follows:
            MetaData Begin
            Name    = IR_gravity_anomaly_Australia_V1.ers
            Version    = "Intrepid v4.3.0 default for SunOS (sparc) by lee optimised build 567b22b07dd7 (Free Version)"
            IR_gravity_anomaly_Australia_V1 Begin
                GroupBy    = no
                DataType    = IEEE4ByteReal
                ByteOrder    = MSBFirst
                Bands    = 1
                Minimum    =  -1286.08496094
                Maximum    =   1207.94592285
                Mean    =  -11.7970361617
                Variance    =   66055.0473974
                Samples    = 10039386
                Nulls    = 13869108
                Projection    = "GEODETIC"
                Datum    = "GDA94"
                BandId    = "IR_gravity_anomaly V1"
            IR_gravity_anomaly_Australia_V1 End
            Extensions Begin
                JetStream Begin
                    Theme    = "GRAVITY"
                    LABEL    = "Isostatic_Residual_Gravity_Anomaly_Grid_Geodetic_Version_1"
                    DATE    = "2011"
                    CELLSIZE    = "0.00833"
                    FLAVOUR    = "Unknown"
                    LINESPACING    = "Unknown"
                    Surveyid    = "4105"
                    CSDATA    = "GDA94"
                    LICENCENO    = "1"
                JetStream End
            Extensions End
        MetaData End

    .ers file format is as follows:
        DatasetHeader Begin
                LastUpdated     = Tue Feb 28 05:16:57 GMT 2012
                Version = "5.0"
                DataSetType     = ERStorage
                DataType        = Raster
                HeaderOffset    = 512
                CoordinateSpace Begin
                        Projection      = "GEODETIC"
                        CoordinateType  = LATLONG
                        Datum   = "GDA94"
                        Rotation        = 0:0:0
                CoordinateSpace End
                ByteOrder       = LSBFirst
                RasterInfo Begin
                        CellType        = IEEE4ByteReal
                        NrOfLines       = 4182
                        NrOfCellsPerLine        = 5717
                        NrOfBands       = 1
                        NullCellValue   = -99999.00000000
                        CellInfo Begin
                                Xdimension      =      0.00833333
                                Ydimension      =      0.00833333
                        CellInfo End
                        RegistrationCellX       = 0
                        RegistrationCellY       = 0
                        RegistrationCoord Begin
                                Longitude       = 109:6:0.843442298
                                Latitude        = -9:21:17.81304202
                        RegistrationCoord End
                        BandId Begin
                                Value   = "IR_gravity_anomaly V1"
                        BandId End
                RasterInfo End
        DatasetHeader End

        '''
        logger.debug('read_file(%s) called', filename)

        filename = filename or self._filename
        assert filename, 'Filename must be specified'

        logger.debug('Parsing ERS/ISI file %s', filename)

        self._metadata_dict = {}
        section_list = []
        section_dict = self._metadata_dict
        parent_dict = None
        infile = open(filename, 'r')

        try:
            for line in infile:
                line = line.strip()
                logger.debug('line = %s' % line)
                match = re.match('(\w+) Begin$', line)
                if match is not None:
                    section = match.groups()[0]
                    logger.debug('Begin section %s' % section)
                    section_list.append(section)
                    section_dict[section] = {}
                    parent_dict = section_dict
                    section_dict = section_dict[section]
                else:
                    match = re.match('(\w+) End$', line)
                    if match is not None:
                        end_section = match.groups()[0]
                        assert end_section == section, 'Unmatched section end: %s' % line
                        logger.debug('End section %s' % section)
                        del section_list[-1]
                        if section_list:
                            section = section_list[-1]
                        else:
                            section = ''
                        section_dict = parent_dict
                    else:
                        try:
                            key, value = [element.strip()
                                          for element in line.split('=')]

                            # Strip quotes from string
                            value = value.replace('"', '')
                            #==================================================
                            # # Change numeric types to either integer or float
                            # try:
                            #     assert '.' not in value, 'Decimal point or period found'
                            #     value = int(value)
                            # except:
                            #     try:
                            #         value = float(value)
                            #     except:
                            #         value = value.replace('"', '') # Strip quotes from string
                            #==================================================

                            logger.debug('key = %s, value = %s' % (key, value))
                            section_dict[key] = value
                        except:
                            pass  # Ignore any line not of format "key = value"

            self._filename = filename
        finally:
            infile.close()

        return self._metadata_dict

    def write_file(self, filename=None, save_backup=False):
        """Function write the metadata contained in self._metadata_dict to an ERS file
        Argument:
            filename: Metadata file to be written
        """
        def write_ers_section(metadata_dict, outfile, indent=0):
            '''
            Recursive function to write
            '''
            for key in sorted(metadata_dict.keys()):
                #        print 'key=%s' % (parent_keys + [key])
                if isinstance(metadata_dict[key], dict):
                    outstring = '\t' * indent + key + ' Begin'
                    outfile.write(outstring)
                    write_ers_section(metadata_dict[key], outfile, indent + 1)
                else:
                    outstring = '\t' * indent + key + \
                        ' = ' + str(metadata_dict[key])
                    outfile.write(outstring)

        logger.debug('write_file(%s) called', filename)

        filename = filename or self._filename
        assert filename, 'Filename must be specified'

        if save_backup and os.path.exists(filename + '.bck'):
            os.remove(filename + '.bck')

        if os.path.exists(filename):
            if save_backup:
                os.rename(filename, filename + '.bck')
            else:
                os.remove(filename)

        # Open ERS document
        try:
            outfile = open(filename, 'w')
            assert outfile is not None, 'Unable to open ERS/ISI file ' + filename + ' for writing'

            logger.debug('Writing ERS file %s', filename)

            write_ers_section(self._metadata_dict, outfile)

        finally:
            outfile.close()


def main():
    pass
    # Test data from file LS7_ETM_OTH_P51_GALPGS01_092_085_20100315/scene01/LE7_20100315_092_085_L1T.ers
    #=========================================================================
    # TESTERS = ''''MetaData Begin
    #         Name    = IR_gravity_anomaly_Australia_V1.ers
    #         Version    = "Intrepid v4.3.0 default for SunOS (sparc) by lee optimised build 567b22b07dd7 (Free Version)"
    #         IR_gravity_anomaly_Australia_V1 Begin
    #             GroupBy    = no
    #             DataType    = IEEE4ByteReal
    #             ByteOrder    = MSBFirst
    #             Bands    = 1
    #             Minimum    =  -1286.08496094
    #             Maximum    =   1207.94592285
    #             Mean    =  -11.7970361617
    #             Variance    =   66055.0473974
    #             Samples    = 10039386
    #             Nulls    = 13869108
    #             Projection    = "GEODETIC"
    #             Datum    = "GDA94"
    #             BandId    = "IR_gravity_anomaly V1"
    #         IR_gravity_anomaly_Australia_V1 End
    #         Extensions Begin
    #             JetStream Begin
    #                 Theme    = "GRAVITY"
    #                 LABEL    = "Isostatic_Residual_Gravity_Anomaly_Grid_Geodetic_Version_1"
    #                 DATE    = "2011"
    #                 CELLSIZE    = "0.00833"
    #                 FLAVOUR    = "Unknown"
    #                 LINESPACING    = "Unknown"
    #                 Surveyid    = "4105"
    #                 CSDATA    = "GDA94"
    #                 LICENCENO    = "1"
    #             JetStream End
    #         Extensions End
    #     MetaData End'''
    #
    #
    # # Instantiate empty MTLMetadata object and parse test string (strip all EOLs first)
    # ers_object = ERSMetadata()
    # ers_object._populate_dict_from_node(ers.dom.minidom.parseString(TESTERS.translate(None, '\n')),
    #                                     ers_object.metadata_dict)
    # assert ers_object.metadata_dict, 'No metadata_dict created'
    # assert ers_object.tree_to_list(), 'Unable to create list from metadata_dict'
    # assert ers_object.get_metadata('EODS_DATASET,ACQUISITIONINFORMATION,PLATFORMNAME'.split(',')), 'Unable to find value for key L1_METADATA_FILE,PRODUCT_METADATA,SPACECRAFT_ID'
    # assert ers_object.get_metadata('...,PLATFORMNAME'.split(',')), 'Unable to find value for key ...,SPACECRAFT_ID'
    # assert not ers_object.get_metadata('RUBBERCHICKEN'.split(',')), 'Found nonexistent key RUBBERCHICKEN'
    # ers_object.set_metadata_node('EODS_DATASET,ACQUISITIONINFORMATION,PLATFORMNAME'.split(','), 'Rubber Chicken')
    # assert ers_object.get_metadata('...,PLATFORMNAME'.split(',')), 'Unable to change ...,SPACECRAFT_ID to "Rubber Chicken"'
    # ers_object.merge_metadata_dicts({'RUBBERCHICKEN': 'Rubber Chicken'}, ers_object.metadata_dict)
    # assert ers_object.get_metadata('RUBBERCHICKEN'.split(',')), 'Unable to find value for key RUBBERCHICKEN'
    # ers_object.delete_metadata('RUBBERCHICKEN'.split(','))
    # assert not ers_object.get_metadata('RUBBERCHICKEN'.split(',')), 'Found value for key RUBBERCHICKEN'
    # print ers_object.tree_to_list()
    #=========================================================================
if __name__ == '__main__':
    main()
