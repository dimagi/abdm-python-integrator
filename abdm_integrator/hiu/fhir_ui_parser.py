# TODO Refactor
# TODO Consider using constants and basically python dict for configs

import os

# Same package as used in HQ
from jsonpath_ng import parse as parse_jsonpath

from abdm_integrator.const import HealthInformationType
from abdm_integrator.utils import json_from_file

parser_config_json_file = 'fhir_ui_parser_config.json'
parser_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), parser_config_json_file)
parser_config = json_from_file(parser_config_path)

HEALTH_INFO_RESOURCES = {
    HealthInformationType.PRESCRIPTION: ['Patient', 'Encounter', 'Practitioner', 'DocumentReference', 'Binary',
                                         'MedicationRequest', 'MedicationStatement'],

    HealthInformationType.OP_CONSULTATION: ['Patient', 'Encounter', 'Practitioner', 'DocumentReference',
                                            'OPConsultRecord', 'Observation', 'AllergyIntolerance', 'Procedure',
                                            'FamilyMemberHistory', 'ServiceRequest', 'MedicationRequest',
                                            'MedicationStatement', 'Appointment'],

    HealthInformationType.DISCHARGE_SUMMARY: ['Patient', 'Encounter', 'Practitioner', 'Condition', 'Observation',
                                              'AllergyIntolerance', 'Procedure', 'FamilyMemberHistory',
                                              'DiagnosticReport','DiagnosticReportImaging', 'DiagnosticReportLab',
                                              'MedicationRequest', 'MedicationStatement', 'CarePlan',
                                              'DocumentReference'],

    HealthInformationType.DIAGNOSTIC_REPORT: ['Patient', 'Encounter', 'Practitioner', 'DiagnosticReport',
                                              'DiagnosticReportImaging', 'DiagnosticReportLab'],


    HealthInformationType.IMMUNIZATION_RECORD: ['Patient', 'Encounter', 'Practitioner', 'DocumentReference',
                                                'Immunization', 'ImmunizationRecommendation'],


    HealthInformationType.HEALTH_DOCUMENT_RECORD: ['Patient', 'Encounter', 'Practitioner', 'DocumentReference'],

    HealthInformationType.WELLNESS_RECORD: ['Patient', 'Encounter', 'Practitioner',
                                            'ObservationVitalSigns', 'ObservationBodyMeasurement',
                                            'ObservationPhysicalActivity', 'ObservationGeneralAssessment',
                                            'ObservationWomenHealth', 'ObservationLifestyle', 'Condition',
                                            'Observation', 'DocumentReference']
}


SNOMED_CODE_HEALTH_INFO_MAPPING = {
    '721981007' : HealthInformationType.DIAGNOSTIC_REPORT,
    '440545006': HealthInformationType.PRESCRIPTION,
    '371530004': HealthInformationType.OP_CONSULTATION,
    '373942005': HealthInformationType.DISCHARGE_SUMMARY,
    '41000179103': HealthInformationType.IMMUNIZATION_RECORD,
    '419891008': HealthInformationType.HEALTH_DOCUMENT_RECORD,
    'WellnessRecord': HealthInformationType.WELLNESS_RECORD,
}


class FHIRUIConfigNotFound(Exception):
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


def resources_dict_from_bundle(fhir_bundle):
    resource_type_to_resources = {}
    for entry in fhir_bundle["entry"]:
        resource_type_to_resources.setdefault(entry["resource"]["resourceType"], [])
        resource_type_to_resources[entry["resource"]["resourceType"]].append(entry["resource"])
    return resource_type_to_resources


def ui_config_for_resource_type(resource_type):
    return next((config for config in parser_config if config['resource_type'] == resource_type), None)


def get_resource_type_from_bundle(resource_type_to_resources):
    composition = resource_type_to_resources['Composition'][0]
    print(composition)
    record_snomed_code = composition['type']['coding'][0]['code']
    title = composition['type']['coding'][0]['display']
    return title, SNOMED_CODE_HEALTH_INFO_MAPPING[record_snomed_code]


def generate_display_fields_for_bundle(fhir_bundle):
    """
    Generates display fields to be used in UI based on config defined at 'fhir_ui_parser_config.json'.
    """
    # TODO Add Custom Exception here probably and raise it
    resource_type_to_resources = resources_dict_from_bundle(fhir_bundle)
    title, health_information_type = get_resource_type_from_bundle(resource_type_to_resources)
    entry = {
        'title': title,
        'health_information_type': health_information_type
    }

    if not HEALTH_INFO_RESOURCES.get(health_information_type):
        raise FHIRUIConfigNotFound(f"FHIR UI config not defined for: '{health_information_type}'")

    parsed_result = []

    for resource_type in HEALTH_INFO_RESOURCES[health_information_type]:
        resources = resource_type_to_resources.get(resource_type, [])
        for resource in resources:
            if resource_type == 'Composition':
                continue
            config = ui_config_for_resource_type(resource_type)
            if not config:
                print(f'Missing Configuration for {resource_type} obtained in HIType {health_information_type}')
                continue
            # for resource in HEALTH_INFO_RESOURCES[health_information_type]:
            for section in config["sections"]:
                data = {'section': section['section'], 'resource': resource_type, 'entries': []}
                for section_entry in section['entries']:
                    # print(section)
                    # print(resource)
                    data_entry = {'label': section_entry['label']}
                    # TODO Check if want to create multiple entries for multiple values
                    try:
                        data_entry['value'] = resource_value_using_json_path(section_entry['path'], resource)
                        if data_entry['value']:
                            data['entries'].append(data_entry)
                        else:  # TODO Remove this (only for test)
                            print(f"Value not found for section:{data['section']} "
                                  f"and path:{section_entry['path']}")
                    # TODO Use logging instead
                    except JsonpathError as err:
                        print(f"Invalid path for {data['section']} and {section_entry['path']} and error: {err}")
                    except Exception as err:
                        print(f'Error for {resource_type} and {section_entry}: {err}')
                if data['entries']:
                    parsed_result.append(data)
    entry['content'] = parsed_result
    return entry
