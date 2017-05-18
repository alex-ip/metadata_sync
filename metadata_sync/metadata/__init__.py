from _metadata import Metadata, MetadataException
from _template_metadata import TemplateMetadata
from _mtl_metadata import MTLMetadata
from _report_metadata import ReportMetadata
from _xml_metadata import XMLMetadata
from _ers_metadata import ERSMetadata
from _netcdf_metadata import NetCDFMetadata
from _jetcat_metadata import JetCatMetadata
from _survey_metadata import SurveyMetadata

try:
    from _argus_metadata import ArgusMetadata # This needs cx_Oracle - can't run outside GA
except:
    pass


def metadata_class(metadata_type_tag):
    metadata_class_map = {'MTL': MTLMetadata,
                          'REPORT': ReportMetadata,
                          'XML': XMLMetadata,
                          'ERS': ERSMetadata,
                          'ISI': ERSMetadata,
                          'NetCDF': NetCDFMetadata,
                          'JetCat': JetCatMetadata,
                          'Survey': SurveyMetadata
                          }

    try:
        metadata_class_map['Argus'] = ArgusMetadata
    except:
        pass


    return metadata_class_map.get(metadata_type_tag.strip().upper())
