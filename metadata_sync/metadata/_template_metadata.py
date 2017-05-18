'''
Created on 20Jan.,2017

@author: Alex Ip
'''
import re
import json

from _metadata import Metadata

class TemplateMetadata(Metadata):
    """Subclass of Metadata to manage template metadata
    """
    # Class variable holding metadata type string
    _metadata_type_id = 'Template'
    _filename_pattern = '.*\.json$'  # Default RegEx for finding metadata file.

    def __init__(self, source, metadata_object=None):
        self._metadata_dict = {}
        self.metadata_object = None
        
        template_json_file = open(source)  
        self.template = {str(key): str(value) for key, value in json.load(template_json_file).iteritems()} # Convert from unicode
        template_json_file.close()
        
        # Find all elements in templates
        element_set = set()
        for attribute_text in self.template.values():
            for s in re.finditer('%%(.+?)%%', attribute_text):
                element_set.add(s.group(1))
        
        self.key_value_dict = {element: None for element in element_set}
        
        if metadata_object:
            self.update_text(metadata_object)
            
    
    def update_text(self, metadata_object):
        self.metadata_object = metadata_object
        
        # Update metadata dict from metadata object
        for element in self.key_value_dict.keys():
            self.key_value_dict[element] = metadata_object.get_metadata(element.split('/')) or 'UNKNOWN'
           
        for attribute_name, attribute_text in self.template.iteritems():
            for s in re.finditer('%%(.+?)%%', attribute_text):
                element = s.group(1)
                attribute_text = attribute_text.replace('%%' + element + '%%', str(self.key_value_dict[element]))
            self._metadata_dict[attribute_name.upper()] = attribute_text

        

        
