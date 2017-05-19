#!/usr/bin/env python

"""NetCDF Metadata module

Author: Alex Ip (alex.ip@ga.gov.au)
Written: 5/7/2016
"""
# TODO: Check potential issues with unicode vs str

import logging
import os
import netCDF4
from shutil import copyfile

from _metadata import Metadata

logger = logging.getLogger(__name__)


class NetCDFMetadata(Metadata):
    """Subclass of Metadata to manage NetCDF data
    """
    # Class variable holding metadata type string
    _metadata_type_id = 'NetCDF'
    _filename_pattern = '.*\.nc$'  # Default RegEx for finding metadata file.

    def __init__(self, source=None):
        """Instantiates NetCDFMetadata object. Overrides Metadata method
        """
        if source:
            if isinstance(source, netCDF4.Dataset):
                self.read_netcdf_metadata(source)
            else:
                Metadata.__init__(self, source)  # Call inherited constructor

    def read_netcdf_metadata(self, netcdf_dataset):
        '''Read metadata from an open NetCDF Dataset object
        '''
        self._metadata_dict = {}

        # Copy all global attributes
        self._metadata_dict = dict(netcdf_dataset.__dict__)

        # Read all variable attributes
        for variable_name in netcdf_dataset.variables.keys():
            variable_dict = {}
            for key in netcdf_dataset.variables[variable_name].__dict__.keys():
                variable_dict[key] = netcdf_dataset.variables[variable_name].__dict__[key]
            self._metadata_dict[variable_name] = variable_dict

    def read_file(self, filename=None):
        '''
        Function to read NetCDF metadata from .nc file and store the results in self._metadata_dict
        Argument:
            filename: NetCDF file to be parsed and stored
        Returns:
            nested dict containing metadata

        '''
        logger.debug('read_file(%s) called', filename)

        filename = filename or self._filename
        assert filename, 'Filename must be specified'

        logger.debug('Reading metadata from NetCDF file %s', filename)

        nc = netCDF4.Dataset(filename)
        try:
            self.read_netcdf_metadata(nc)
            self._filename = filename
        finally:
            nc.close()

        return self._metadata_dict

    def write_netcdf_metadata(self, nc):
        '''Write metadata to an open NetCDF Dataset object
        '''
        for key, value in self._metadata_dict.items():
            if type(value) in [str, unicode]:
                setattr(nc, key, value)  # Set global attribute
            elif isinstance(value, dict):
                try:
                    assert nc.variables.get(
                        key), 'Variable %s does not exist' % key
                    for varattr_key, varattr_value in value.items():
                        # Set variable attribute
                        setattr(nc.variables[key], varattr_key, varattr_value)
                except Exception as e:
                    logger.warning(e.message)

    def write_file(self, filename=None, save_backup=False):
        """Function write the metadata contained in self._metadata_dict to an NetCDF file
        Argument:
            filename: Metadata file to be written
        """

        logger.debug('write_file(%s) called', filename)

        filename = filename or self._filename
        assert filename, 'Filename must be specified'

        if save_backup and os.path.exists(filename + '.bck'):
            os.remove(filename + '.bck')

        if os.path.exists(filename):
            if save_backup:
                os.remove(filename + '.bck')
                copyfile(filename, filename + '.bck')

        # Open NetCDF document
        try:
            nc = netCDF4.Dataset(filename)
            self.write_netcdf_metadata(nc)
        finally:
            nc.close()


def main():
    pass

if __name__ == '__main__':
    main()
