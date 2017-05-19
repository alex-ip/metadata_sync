'''
Created on 28Oct.,2016

@author: Alex Ip
'''
import os
import json
import dateutil.parser
from datetime import datetime
from dateutil import tz
import pytz
from glob import glob
import hashlib
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Initial logging level for this module

DEFAULT_EXCLUDED_EXTENSIONS = ['.bck', '.md5', '.uuid', '.json', '.tmp']

def read_iso_datetime_string(iso_datetime_string):
    '''
    Helper function to convert an ISO datetime string into a Python datetime object
    '''
    if not iso_datetime_string:
        return None

    try:
        iso_datetime = dateutil.parser.parse(iso_datetime_string)
    except ValueError as e:
        logger.warning(
            'WARNING: Unable to parse "%s" into ISO datetime (%s)', iso_datetime_string, e.message)
        iso_datetime = None

    return iso_datetime


def get_iso_utcnow(utc_datetime=None):
    '''
    Helper function to return an ISO string representing a UTC date/time. Defaults to current datetime.
    '''
    return (utc_datetime or datetime.utcnow()).replace(
        tzinfo=tz.gettz('UTC')).isoformat()


def get_utc_mtime(file_path):
    '''
    Helper function to return the UTC modification time for a specified file
    '''
    assert file_path and os.path.exists(
        file_path), 'Invalid file path "%s"' % file_path
    return datetime.fromtimestamp(os.path.getmtime(file_path), pytz.utc)



def get_filtered_md5sum_dict(md5dir, excluded_extensions=[]):
    '''
    Simulate filtered Linux md5sum command
    Code adapted from http://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file
    '''
    return get_md5sums([fname for fname in glob(os.path.join(md5dir, '*'))
                        if os.path.isfile(fname)
                        and os.path.splitext(fname)[1] not in excluded_extensions
                        ]
                       )
    
def get_md5sums(file_path_list, ashexstr=True):
    '''
    Generate MD5 checksums for all files named in file_path_list
    Code adapted from http://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file
    '''
    def hash_bytestr_iter(bytesiter, hasher, ashexstr=ashexstr):
        for block in bytesiter:
            hasher.update(block)
        return (hasher.hexdigest() if ashexstr else hasher.digest())
     
    def file_as_blockiter(afile, blocksize=65536):
        with afile:
            block = afile.read(blocksize)
            while len(block) > 0:
                yield block
                block = afile.read(blocksize)
                
    return {os.path.basename(fname): hash_bytestr_iter(file_as_blockiter(open(fname, 'rb')), hashlib.md5())
            for fname in file_path_list
            }

def write_json_metadata(uuid, dataset_folder, excluded_extensions=None):
    '''
    Function to write UUID, file_paths and current timestamp to .metadata.json
    '''
    excluded_extensions = excluded_extensions or DEFAULT_EXCLUDED_EXTENSIONS

    assert os.path.isdir(
        dataset_folder), 'dataset_folder is not a valid directory.'
    dataset_folder = os.path.abspath(dataset_folder)

    json_metadata_path = os.path.join(dataset_folder, '.metadata.json')
    md5_dict = get_filtered_md5sum_dict(dataset_folder, excluded_extensions)
    metadata_dict = {'uuid': uuid,
                     'time': get_iso_utcnow(),
                     'folder_path': dataset_folder,
                     'files': [{'file': os.path.basename(filename),
                                'md5': md5_dict[filename],
                                'mtime': get_utc_mtime(os.path.join(dataset_folder, filename)).isoformat()
                                }
                               for filename in sorted(md5_dict.keys())
                               ]
                     }

    json_output_file = open(json_metadata_path, 'w')
    json.dump(metadata_dict, json_output_file, indent=4)
    json_output_file.close()
    logger.info('Finished writing metadata file %s', json_metadata_path)


def read_json_metadata(dataset_folder):
    '''
    Function to read metadata_dict from .metadata.json
    '''
    assert os.path.isdir(
        dataset_folder), 'dataset_folder is not a valid directory.'
    dataset_folder = os.path.abspath(dataset_folder)

    json_metadata_path = os.path.join(dataset_folder, '.metadata.json')

    json_metadata_file = open(json_metadata_path, 'r')
    metadata_dict = json.load(json_metadata_file)
    json_metadata_file.close()

    return metadata_dict    


def check_json_metadata(uuid, dataset_folder, excluded_extensions=None):
    '''
    Function to check UUID, file_paths MD5 checksums from .metadata.json
    '''
    excluded_extensions = excluded_extensions or DEFAULT_EXCLUDED_EXTENSIONS
    
    metadata_dict = read_json_metadata(dataset_folder)

    report_list = []

    if metadata_dict['uuid'] != uuid:
        report_list.append('UUID Changed from %s to %s' % (
            metadata_dict['uuid'], uuid))

    if metadata_dict['folder_path'] != dataset_folder:
        report_list.append('Dataset folder Changed from %s to %s' % (
            metadata_dict['folder_path'], dataset_folder))

    calculated_md5_dict = get_filtered_md5sum_dict(dataset_folder, excluded_extensions)

    saved_md5_dict = {file_dict['file']:
                      file_dict['md5']
                      for file_dict in metadata_dict['files']
                      }

    for saved_filename, saved_md5sum in saved_md5_dict.items():
        calculated_md5sum = calculated_md5_dict.get(saved_filename)
        if not calculated_md5sum:
            new_filenames = [new_filename for new_filename, new_md5sum in calculated_md5_dict.items(
            ) if new_md5sum == saved_md5sum]
            if new_filenames:
                report_list.append('File %s has been renamed to %s' % (
                    saved_filename, new_filenames[0]))
            else:
                report_list.append(
                    'File %s does not exist' % saved_filename)
        else:
            if saved_md5sum != calculated_md5sum:
                report_list.append('MD5 Checksum for file %s has changed from %s to %s' % (
                    saved_filename, saved_md5sum, calculated_md5sum))

    if report_list:
        raise Exception('\n'.join(report_list))
    else:
        logger.info(
            'File paths and checksums verified OK in %s', dataset_folder)
