"""
This file contains Interfaces for features that require integration with other service of the client.
For e.g. To fetch health data from HRP.
Client should subclass the respective interface and implement the desired logic.
"""


class HRPAbhaRegisteredCheck:

    def check_if_abha_registered(self, user, abha, **kwargs):
        msg = f'{self.__class__.__name__}.check_if_abha_registered() must be implemented.'
        raise NotImplementedError(msg)
