import os

from django.test import SimpleTestCase

from abdm_integrator.const import HealthInformationType
from abdm_integrator.hiu.fhir.const import HEALTH_INFO_TYPE_RESOURCES_MAP
from abdm_integrator.hiu.fhir.parser import FHIRUnsupportedHIType, parse_fhir_bundle
from abdm_integrator.utils import json_from_file

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
SAMPLE_FHIR_BUNDLES_DIR = os.path.join(CURRENT_DIR, 'data', 'sample_fhir_bundles')
EXPECTED_PARSED_OUTPUT_DIR = os.path.join(CURRENT_DIR, 'data', 'expected_parsed_output')


class TestFHIRParser(SimpleTestCase):
    """Used to test fhir parsing logic using sample fhir bundle data.
    The sample bundles are taken from 'https://nrces.in/ndhm/fhir/r4/index.html' with file data
    intentionally shortened to 'DUMMY'.Feel free to modify these as needed based on any change
    in config.json.
    """

    def test_parser_using_sample_bundles_all_hi_types(self):
        for health_info_type in HEALTH_INFO_TYPE_RESOURCES_MAP.keys():
            with self.subTest(health_info_type):
                bundle_file_name = f'Bundle-{health_info_type}.json'
                fhir_bundle = json_from_file(os.path.join(SAMPLE_FHIR_BUNDLES_DIR, bundle_file_name))

                expected_parsed_output_file_name = f'Parsed-{health_info_type}.json'
                expected_parsed_output = json_from_file(os.path.join(
                    EXPECTED_PARSED_OUTPUT_DIR,
                    expected_parsed_output_file_name
                ))

                result = parse_fhir_bundle(fhir_bundle)
                self.assertEqual(result, expected_parsed_output)

    def test_parser_unsupported_hi_type(self):
        bundle_file_name = f'Bundle-{HealthInformationType.PRESCRIPTION}.json'
        fhir_bundle = json_from_file(os.path.join(SAMPLE_FHIR_BUNDLES_DIR, bundle_file_name))
        fhir_bundle['entry'][0]['resource']['type']['coding'][0]['code'] = 'does_not_exist'

        with self.assertRaises(FHIRUnsupportedHIType) as error:
            parse_fhir_bundle(fhir_bundle)
        self.assertEqual(str(error.exception), 'Unsupported Health Info type with code: does_not_exist found.')
