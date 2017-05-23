#!/usr/bin/env python

#=========================================================================
# Copyright (c)  2014 Geoscience Australia
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither Geoscience Australia nor the names of its contributors may be
#       used to endorse or promote products derived from this software
#       without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#=========================================================================
'''
THREDDSCatalog Class
Created on 22/03/2016

@author: Alex Ip
'''
import os
import re
from collections import OrderedDict
import logging
import subprocess
#from osgeo import gdal, osr
import numpy as np
import netCDF4
from owslib.csw import CatalogueServiceWeb
from owslib.fes import PropertyIsEqualTo  # , PropertyIsLike, BBox
from datetime import datetime
import tempfile
import dateutil.parser
from dateutil import tz
import pytz
import yaml

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Logging level for this module

# Ignore failed import of URL modules
try:
    import urllib
except:
    logger.warning(
        'WARNING: Unable to import urllib. Any HTML function calls will fail.')

try:
    import lxml.html
except:
    logger.warning(
        'WARNING: Unable to import lxml.html. Any HTML function calls will fail.')


class THREDDSCatalog(object):
    '''
    Class definition for THREDDSCatalog
    '''
    # DEFAULT_THREDDS_CATALOGUE_URL = 'http://dapds00.nci.org.au/thredds/catalog.html'
    DEFAULT_THREDDS_CATALOGUE_URLS = 'http://dapds00.nci.org.au/thredds/catalog/rr2/National_Coverages/catalog.html,\
http://dapds00.nci.org.au/thredds/catalog/rr2/National_Coverages/http/catalog.html'

    def __init__(self, thredds_catalog_urls=None,
                 yaml_path=None, verbose=False):
        '''
        Constructor for class THREDDSCatalog
        Launches a crawler to examine every THREDDS catalog page underneath the nominated thredds_catalog_urls
        '''
        assert (yaml_path and not thredds_catalog_urls) or (
            thredds_catalog_urls and not yaml_path), 'yaml_path or thredds_catalog_urls should be specified, but not both.'
        self.verbose = verbose
        if yaml_path:
            self.load(yaml_path)
        else:
            thredds_catalog_urls = thredds_catalog_urls or self.DEFAULT_THREDDS_CATALOGUE_URLS
            self.thredds_catalog_url_list = [thredds_catalog_url.strip() for thredds_catalog_url in thredds_catalog_urls.split(',')]
            
            # Top level dict is an OrderedDict to implement prioritised search through specified catalogues                              
            self.thredds_catalog_dict = OrderedDict((thredds_catalog_url, self.get_thredds_dict(thredds_catalog_url))
                                                     for thredds_catalog_url in self.thredds_catalog_url_list 
                                                    )


    def get_thredds_dict(self, thredds_catalog_urls):
        '''
        get_thredds_dict - recursive function to parse specified THREDDS catalogue URL and return a nested dict
        Parameter: thredds_catalog_urls - string specifying URL of THREDDS catalog
        '''
        def get_absolute_url(href):
            # Create absolute URL
            if href.startswith(
                    '/'):  # Absolute href - should start with "/thredds/"
                return re.sub('/thredds/.*', href, thredds_catalog_urls)
            else:  # Relative href
                return re.sub('catalog.html$', href, thredds_catalog_urls)

        thredds_catalog_dict = {}

        if self.verbose:
            logger.info('Opening %s', thredds_catalog_urls)
        data = urllib.urlopen(thredds_catalog_urls).read()
        logger.debug('data = %s', data)

        tree = lxml.html.fromstring(data)

        title = tree.find('.//title')
        title_text = [e.strip() for e in title.xpath(
            './/text()') if len(e.strip()) > 0][0]
        logger.debug('title_text = %s', title_text)

        if title_text == 'Catalog Services':  # This is a landing page for a file
            # Iterate through all service endpoints for file
            for ol in tree.iterfind('.//ol'):
                for li in ol.iterfind('.//li'):
                    text = [e.strip() for e in li.xpath(
                        './/text()') if len(e.strip()) > 0]

                    if len(text) == 0:  # No li text found
                        continue

                    endpoint_type = text[0].replace(':', '')
                    url = get_absolute_url(text[1])

        #======================================================================
        #             # Not sure why a isn't found
        #             a = li.find('.//a')
        #             if a is None:
        #                 logger.debug('a not found')
        #                 continue
        #
        #             href = a.get('href')
        #             if href is None:
        #                 logger.debug('href not found')
        #                 continue
        #
        #             url = get_absolute_url(href)
        #======================================================================

                    logger.debug(
                        'Service endpoint: endpoint_type = %s, href = %s', endpoint_type, url)
                    thredds_catalog_dict[endpoint_type] = url
                break  # Only process first "<ol>"

        else:  # Catalog page for virtual subdirectory

            for table in tree.iterfind('.//table'):
                #                first_row = True
                for row in table.iterfind('.//tr'):
                    a = row.find('.//a')
                    if a is None:
                        continue

                    href = a.get('href')
                    logger.debug('href = %s', href)
                    if href is None:
                        continue

                    url = get_absolute_url(href)

                    if href.endswith('catalog.html'):  # Virtual subdirectory
                        logger.debug('Virtual subdirectory: url = %s', url)
                        thredds_catalog_dict[url] = self.get_thredds_dict(url)

                    elif href.startswith('catalog.html?dataset='):  # File
                        filename = os.path.basename(href)

                        logger.debug(
                            'File: filename = %s, url = %s', filename, url)
                        try:
                            thredds_catalog_dict[
                                url] = self.get_thredds_dict(url)
                        except Exception as e:
                            logger.error('ERROR: %s', e.message)

                    # Get rid of empty dicts
                    if thredds_catalog_dict.get(url) == {}:
                        del thredds_catalog_dict[url]

        logger.debug('thredds_catalog_dict = %s', thredds_catalog_dict)
        return thredds_catalog_dict

    def dump(self, yaml_path=None):
        yaml_path = os.path.abspath(yaml_path or (re.sub('\W', '_', re.sub(
            'http://', '', self.thredds_catalog_dict.keys()[0])) + '.yaml'))
        yaml_file = open(yaml_path, 'w')
        yaml.dump(self.thredds_catalog_dict, yaml_file)
        yaml_file.close()
        logger.info('THREDDS catalogue dumped to file %s', yaml_path)

    def load(self, yaml_path):
        yaml_file = open(yaml_path, 'r')
        self.thredds_catalog_dict = yaml.load(yaml_file)
        yaml_file.close()
        logger.info('THREDDS catalogue loaded from file %s', yaml_path)

    def endpoint_tuple_list(self, type_filter='.*',
                            url_filter='.*', catalog_dict=None):
        '''
        Function to return a list of (protocol, endpoint) tuples contained in the leaf nodes of self.thredds_catalog_dict
        Arguments:
            type_filter: regular expression string matching one or more of ['HTTPServer', 'NetcdfSubset', OPENDAP', 'WCS, 'WMS']
            url_filter: regular expression string to restrict URLs returned: e.g. '.*\.nc$' to return all NetCDF endpoints
        '''
        result_list = []
        catalog_dict = catalog_dict or self.thredds_catalog_dict

        for key in sorted(catalog_dict.keys()):
            value = catalog_dict[key]

            if isinstance(value, dict):
                result_list += self.endpoint_tuple_list(
                    type_filter, url_filter, catalog_dict[key])
            else:  # Leaf node
                if (re.search(type_filter, key)
                        and re.search(url_filter, value)):
                    result_list.append((key, value))

        return result_list

    def endpoint_list(self, type_filter='.*',
                      url_filter='.*', catalog_dict=None):
        '''
        Function to return a list of endpoints contained in the leaf nodes of self.thredds_catalog_dict
        Arguments:
            type_filter: regular expression string matching one or more of ['HTTPServer', 'NetcdfSubset', OPENDAP', 'WCS, 'WMS']
            url_filter: regular expression string to restrict URLs returned: e.g. '.*\.nc$' to return all NetCDF endpoints
        '''
        return [endpoint for _protocol, endpoint in self.endpoint_tuple_list(
            type_filter=type_filter, url_filter=url_filter, catalog_dict=catalog_dict)]

    def find_url_list(self, file_path):
        '''
        Function to return list of (<protocol>, <url>) tuples for a given filename
        Returns empty list for failed match.
        '''
        # Narrow down search to tuples matching basename
        basename = os.path.basename(file_path)
        base_list = self.endpoint_tuple_list(
            type_filter='.*', url_filter=basename)
        if base_list:
            logger.debug('%d possible URLs initially found for basename %s', len(
                base_list), basename)
        else:  # Nothing found
            logger.debug('No possible URLs found for basename %s', basename)
            return []

        # Find URL matches for longest possible sub-path
        find_path = os.path.abspath(file_path).replace(os.path.sep, '/') # Convert path separators to '/'
        find_list = []
        while find_path and not find_list:
            logger.debug('Searching for %s in URL list' % find_path)
            find_list = [(protocol, url)
                         for protocol, url in base_list if url.find(find_path)]
            if find_list:  # Matches found for maximum-length sub-path
                logger.debug('%d URLs found for %s', len(find_list), find_path)
                return find_list  # Search complete
            elif '/' in find_path:  # More leading directories to strip
                # Strip leading directory from find_path
                find_path = re.sub('^[^/]*/', '', find_path)
            else:  # Nothing found for basename - should never happen
                logger.debug('No URLs found for %s', find_path)
                return []

    def find_url_dict(self, file_path):
        '''
        Function to return dict of {<protocol>: <url>, <protocol>: <url>,...} for a given filename
        Returns empty dict for failed match, returns first of multiple URLs when duplicate protocols found
        '''
        # Convert list of tuples to dict - remove duplicate protocols
        result_dict = {}
        for protocol, url in self.find_url_list(file_path):
            existing_url = result_dict.get(protocol)
            # Keep the shorter of the two URLs when duplicate protocols found
            if existing_url is None:
                result_dict[protocol] = url

        return result_dict

    def find_catalogs(self, file_path, distribution_types=[
                      'NetcdfSubset'], catalog_dict=None):
        '''
        Recursive function to return list of catalog URLS containing specified distribution type(s) for specified file_path
        Returns empty dict for failed match, keeps the shorter of two URLs when duplicates found
        '''
        basename = os.path.basename(file_path)
        base_list = []
        catalog_dict = catalog_dict or self.thredds_catalog_dict

        for key in sorted(catalog_dict.keys()):
            value = catalog_dict[key]

            if isinstance(value, dict):
                if re.search(
                        basename + '$', key) and (set(distribution_types) <= set(value.keys())):
                    base_list.append(key)
                else:
                    base_list += self.find_catalogs(file_path,
                                                    distribution_types, value)

        if not base_list:
            return base_list

        # Find URL matches for longest possible sub-path
        find_path = os.path.abspath(file_path).replace(os.path.sep, '/')
        find_list = []
        while find_path and not find_list:
            logger.debug('Searching for %s in URL list' % find_path)
            find_list = [catalog_url for catalog_url in base_list if re.search(
                find_path + '$', catalog_url)]
            if find_list:  # Matches found for maximum-length sub-path
                logger.debug('%d URLs found for %s', len(find_list), find_path)
                return find_list  # Search complete
            elif '/' in find_path:  # More leading directories to strip
                # Strip leading directory from find_path
                find_path = re.sub('^[^/]*/', '', find_path)
            else:  # Nothing found for basename - should never happen
                logger.debug('No URLs found for %s', find_path)
                return []
            

    def indented_text(self, subtree_dict=None, level=0):
        '''
        Recursive function to return indented text representing catalog tree
        '''
        subtree_dict = subtree_dict or self.thredds_catalog_dict
        result = ''
        
        key_list = subtree_dict.keys()
        if type(subtree_dict) != OrderedDict:
            key_list = sorted(key_list)
            
        for key in key_list:
            result += ('  ' * level) + key
            value = subtree_dict[key]

            if type(value) == str:
                result += ': ' + value + '\n'
            elif type(value) == dict:
                result += '\n' + self.indented_text(value, level+1)
            else:
                raise Exception('Unrecognised value type')
            
        return result
        
        