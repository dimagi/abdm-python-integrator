"""
This file contains Interfaces for features that require integration with other service of the client.
For e.g. To fetch health data from HRP.
Client should subclass the respective interface and implement the desired logic.
"""


class HRPIntegration:
    """Base interface that declares helper methods to communicate with HRP"""

    def check_if_abha_registered(self, abha, user, **kwargs):
        """
        Method to check if ABHA Id is already registered.
        OPTIONAL to Implement. If not implemented, this check is skipped.

        :param abha: ABHA health id
        :type abha: str
        :param user: Instance of model as defined in app_settings.USER_MODEL
        :type user: object
        :returns: Boolean value indicating if abha is registered on HRP
        :rtype: bool

        """
        msg = f'{self.__class__.__name__}.check_if_abha_registered() must be implemented.'
        raise NotImplementedError(msg)

    def fetch_health_data(self, care_context_reference, health_info_types, linked_care_context_details, **kwargs):
        """
        Method to return health data in FHIR format from HRP for a given care context reference.
        Must be implemented.

        :param care_context_reference: Care Context Reference of health data
        :type care_context_reference: str
        :param health_info_types: Valid health info types for which fhir data is required
        :type health_info_types: list
        :param linked_care_context_details: Additional Information stored while care context linking
        :type linked_care_context_details: dict
        :returns: List of FHIR records one for each health info type. Should return empty list if no health
        record available.
        :rtype: list

        """
        msg = f'{self.__class__.__name__}.fetch_health_data() must be implemented.'
        raise NotImplementedError(msg)

    def discover_patient_and_care_contexts(self, patient_details, hip_id, **kwargs):
        """
        Method to discover patient and their care contexts on HRP using the details shared by the patient.
        Must be implemented.
        :param patient_details: PatientDetails as defined 'abdm_integrator.hip.views.care_contexts.PatientDetails'
        :type patient_details: PatientDetails (object)
        :param hip_id: Health Information Provider ID
        :type hip_id: str
        :returns: If patient is discovered , returns matched patient and their care context details if any.
        :rtype: dict
        :raises: DiscoveryNoPatientFoundError: No patient was discovered
        :raises: DiscoveryMultiplePatientsFoundError: Multiple patients were discovered

        Structure of return Value
        .. code-block:: python
        {
            "referenceNumber": "string",    # unique id associated wih patient
            "display": "string",            # text value for patient
            "careContexts": [
              {
                "referenceNumber": "string",    # unique id associated wih patient health record
                "display": "string",            # text value for patient visit or health record
                "hiTypes": "list"               # List of HI Types associated with the care context
                "additionalInfo": {
                    "domain": "string",         # project name on HRP. Dummy value can be used if not applicable
                    "record_date": "datetime in iso format"     # health record date
                }
              }
            ],
            "matchedBy": [      # Matching identifier
              "MR"
            ]
        }
        """
        msg = f'{self.__class__.__name__}.discover_care_context() must be implemented.'
        raise NotImplementedError(msg)
