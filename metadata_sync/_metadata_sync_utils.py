'''
Shared functions for metadata_sync package
Created on 22May,2017

@author: Alex
'''
import os
import requests
import logging
from glob import glob
from xml.dom.minidom import parseString

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Initial logging level for this module

def get_xml_from_uuid(geonetwork_url, uuid):
    '''
    Function to return complete, native (ISO19115-3) XML text for metadata record with specified UUID
    '''
    xml_url = '%s/xml.metadata.get?uuid=%s' % (geonetwork_url, uuid)
    logger.debug('URL = %s' % xml_url)
    return requests.get(xml_url).content

def find_files(root_dir, file_template, extension_filter='.nc'):
    '''
    Function to simulate the result of a filtered Linux find command
    Uses glob with user-friendly file system wildcards instead of regular expressions for template matching
    '''
    #===========================================================================
    # file_path_list = sorted([filename for filename in subprocess.check_output(
    #     ['find', args.netcdf_dir, '-name', args.file_template]).split('\n') if re.search('\.nc$', filename)])
    #===========================================================================
    root_dir = os.path.abspath(root_dir)
    file_path_list = glob(os.path.join(root_dir, file_template))
    for topdir, subdirs, _files in os.walk(root_dir, topdown=True):
        for subdir in subdirs:
            file_path_list += [file_path 
                               for file_path in glob(os.path.join(topdir, subdir, file_template))
                               if os.path.isfile(file_path)
                               and os.path.splitext(file_path)[1] == extension_filter
                               ]
    file_path_list = sorted(file_path_list)    
    return file_path_list

def prettify_xml(xml_text):
    '''
    Helper function to return a prettified XML string
    '''
    return parseString(xml_text).toprettyxml(indent="", 
                                             newl="", 
                                             encoding="utf-8"
                                             )        


