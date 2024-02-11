import logging
import os

# Same package as used in HQ
from jsonpath_ng import parse as parse_jsonpath

from abdm_integrator.hiu.fhir.const import HEALTH_INFO_TYPE_RESOURCES_MAP, SNOMED_CODE_HEALTH_INFO_TYPE_MAP
from abdm_integrator.utils import json_from_file

parser_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.json')
parser_config = json_from_file(parser_config_path)

logger = logging.getLogger('abdm_integrator')


class FHIRUnsupportedHIType(Exception):
    pass


class JsonpathError(Exception):
    pass


def simplify_list_as_string(seq):
    result = ",".join(str(element) for element in seq)
    return result


def resource_value_using_json_path(json_path, resource):
    try:
        jsonpath_expr = parse_jsonpath(json_path)
    except Exception as err:
        raise JsonpathError from err
    matches = jsonpath_expr.find(resource)
    values = [m.value for m in matches]
    return simplify_list_as_string(values)


def resource_type_to_resources_from_bundle(fhir_bundle):
    resource_type_to_resources = {}
    for entry in fhir_bundle['entry']:
        resource_type_to_resources.setdefault(entry['resource']['resourceType'], []).append(entry['resource'])
    return resource_type_to_resources


def get_config_for_resource_type(resource_type):
    return next((config for config in parser_config if config['resource_type'] == resource_type), None)


def snomed_code_title_from_bundle(resource_type_to_resources):
    composition = resource_type_to_resources['Composition'][0]
    code = composition['type']['coding'][0]['code']
    title = composition['type']['coding'][0]['display']
    return code, title


def parse_fhir_bundle(fhir_bundle):
    """
    Parses the fhir bundle into a format easier to be displayed on UI.Parsing is done on the basis of configuration
    defined at 'config.json'.
    limitations: Current config json and parsing logic does not support parsing multiple entries for a property.
    (Usually fhir bundle contains only one entry however can contain multiple)
    For e.g - the below config supports only 1st entry obtained in the name at index 0.
    {
        "path": "$.name[0].text",
        "label": "Patient Registered As"
    }
    """
    resource_type_to_resources = resource_type_to_resources_from_bundle(fhir_bundle)

    bundle_snomed_code, title = snomed_code_title_from_bundle(resource_type_to_resources)
    health_information_type = SNOMED_CODE_HEALTH_INFO_TYPE_MAP.get(bundle_snomed_code)
    if not health_information_type:
        raise FHIRUnsupportedHIType(f'Unsupported Health Info type with code: {bundle_snomed_code} found.')

    parsed_entry = {
        'title': title,
        'health_information_type': health_information_type
    }
    parsed_content = []
    for resource_type in HEALTH_INFO_TYPE_RESOURCES_MAP[health_information_type]:
        config = get_config_for_resource_type(resource_type)
        if not config:
            logger.error(
                'ABDM HIU Parsing Error: Missing Configuration for %s obtained in HIType %s',
                resource_type,
                health_information_type
            )
            continue
        for resource in resource_type_to_resources.get(resource_type, []):
            for section in config['sections']:
                section_data = _process_section(section, resource_type, resource)
                if section_data['entries']:
                    parsed_content.append(section_data)
    parsed_entry['content'] = parsed_content
    return parsed_entry


def _process_section(section, resource_type, resource):
    section_data = {'section': section['section'], 'resource': resource_type, 'entries': []}
    for section_entry in section['entries']:
        section_entry_data = {'label': section_entry['label']}
        try:
            section_entry_data['value'] = resource_value_using_json_path(section_entry['path'], resource)
            if section_entry_data['value']:
                section_data['entries'].append(section_entry_data)
        except JsonpathError as err:
            logger.error(
                'ABDM HIU Parsing Error: Invalid path for %s:%s:%s and error: %s',
                resource_type,
                section_data['section'],
                section_entry['label'],
                err
            )
        except Exception as err:
            logger.exception(
                'ABDM HIU Parsing Error: Error for %s:%s and error: %s',
                resource_type,
                section_entry['label'],
                err
            )
    return section_data
