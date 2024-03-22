from abdm_integrator.const import HealthInformationType

HEALTH_INFO_TYPE_RESOURCES_MAP = {
    HealthInformationType.PRESCRIPTION: ['Patient', 'Encounter', 'Practitioner', 'DocumentReference', 'Binary',
                                         'MedicationRequest', 'MedicationStatement'],

    HealthInformationType.OP_CONSULTATION: ['Patient', 'Encounter', 'Practitioner', 'DocumentReference',
                                            'Observation', 'AllergyIntolerance', 'Procedure',
                                            'FamilyMemberHistory', 'ServiceRequest', 'MedicationRequest',
                                            'MedicationStatement', 'Appointment'],

    HealthInformationType.DISCHARGE_SUMMARY: ['Patient', 'Encounter', 'Practitioner', 'Condition', 'Observation',
                                              'AllergyIntolerance', 'Procedure', 'FamilyMemberHistory',
                                              'DiagnosticReport', 'DiagnosticReportImaging', 'DiagnosticReportLab',
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


SNOMED_CODE_HEALTH_INFO_TYPE_MAP = {
    '721981007': HealthInformationType.DIAGNOSTIC_REPORT,
    '440545006': HealthInformationType.PRESCRIPTION,
    '371530004': HealthInformationType.OP_CONSULTATION,
    '373942005': HealthInformationType.DISCHARGE_SUMMARY,
    '41000179103': HealthInformationType.IMMUNIZATION_RECORD,
    '419891008': HealthInformationType.HEALTH_DOCUMENT_RECORD,
    'WellnessRecord': HealthInformationType.WELLNESS_RECORD,
}
