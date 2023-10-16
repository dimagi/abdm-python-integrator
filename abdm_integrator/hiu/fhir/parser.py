# TODO Use logging for print statements

import os

# Same package as used in HQ
from jsonpath_ng import parse as parse_jsonpath

from abdm_integrator.hiu.fhir.const import HEALTH_INFO_TYPE_RESOURCES_MAP, SNOMED_CODE_HEALTH_INFO_TYPE_MAP
from abdm_integrator.utils import json_from_file

parser_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.json')
parser_config = json_from_file(parser_config_path)


class FHIRUnsupportedHIType(Exception):
    pass


class JsonpathError(Exception):
    pass


def simplify_list(seq):
    if len(seq) == 1:
        return seq[0]
    if not seq:
        return None
    return seq


def resource_value_using_json_path(json_path, resource):
    try:
        jsonpath_expr = parse_jsonpath(json_path)
    except Exception as err:
        raise JsonpathError from err
    matches = jsonpath_expr.find(resource)
    values = [m.value for m in matches]
    return simplify_list(values)


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
    Parses the fhir bundle into a format easier to be displayed on UI.
    Parsing is done on the basis of configuration defined at 'config.json'.
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
            print(f'Missing Configuration for {resource_type} obtained in HIType {health_information_type}')
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
            print(f"Invalid path for {resource_type}:{section_data['section']}:{section_entry['label']}"
                  f" and error: {err}")
        except Exception as err:
            print(f"Error for {resource_type}:{section_entry['label']} and error:{err}")
    return section_data
