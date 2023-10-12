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
        :returns: List of FHIR records one for each health info type
        :rtype: list

        """
        msg = f'{self.__class__.__name__}.fetch_health_data() must be implemented.'
        raise NotImplementedError(msg)
