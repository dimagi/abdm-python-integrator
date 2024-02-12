import json

from django.test import SimpleTestCase
from rest_framework import serializers

from abdm_integrator.hiu.fhir.parser import parser_config_path


class FHIRParserConfigJSONSerializer(serializers.Serializer):

    class SectionSerializer(serializers.Serializer):

        class EntrySerializer(serializers.Serializer):
            path = serializers.CharField()
            label = serializers.CharField()

        section = serializers.CharField()
        entries = serializers.ListField(child=EntrySerializer())

    resource_type = serializers.CharField()
    sections = serializers.ListField(child=SectionSerializer())


class TestParserConfigJSON(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        with open(parser_config_path) as file:
            cls.config_json = json.load(file)

    def test_json_structure(self):
        self.assertTrue(isinstance(self.config_json, list))
        for index, config in enumerate(self.config_json):
            self.assertTrue(isinstance(config, dict))
            serializer = FHIRParserConfigJSONSerializer(data=config)
            self.assertTrue(serializer.is_valid(), f'Entry {index+1}: {serializer.errors}')
