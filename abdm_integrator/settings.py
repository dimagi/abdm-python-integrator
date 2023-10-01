from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from rest_framework.settings import perform_import

DEFAULTS = {
    'CLIENT_ID': None,
    'CLIENT_SECRET': None,
    'X_CM_ID': None,
    'ABHA_URL': None,
    'GATEWAY_URL': None,
    'USER_MODEL': 'auth.user',
    'AUTHENTICATION_CLASS': None,
    'HRP_INTEGRATION_CLASS': 'abdm_integrator.integrations.HRPIntegration',
    'CELERY_APP': None,
    'CELERY_QUEUE': None,
}

IMPORT_STRINGS = (
    'AUTHENTICATION_CLASS',
    'HRP_INTEGRATION_CLASS',
    'CELERY_APP'
)


class AppSettings:
    """
    Derived from DRF APISettings class
    """

    setting_name = 'ABDM_INTEGRATOR'

    def __init__(self, defaults=None, import_strings=None):
        self.defaults = defaults or DEFAULTS
        self.import_strings = import_strings or IMPORT_STRINGS
        self._cached_attrs = set()

    @property
    def user_settings(self):
        if not hasattr(self, '_user_settings'):
            self._user_settings = getattr(settings, self.setting_name, {})
        return self._user_settings

    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError("Invalid ABDM_INTEGRATOR setting: '%s'" % attr)
        try:
            val = self.user_settings[attr]
        except KeyError:
            val = self.defaults[attr]
        if attr in self.import_strings:
            val = perform_import(val, attr)
        self._cached_attrs.add(attr)
        setattr(self, attr, val)
        return val

    def reload(self):
        for attr in self._cached_attrs:
            delattr(self, attr)
        self._cached_attrs.clear()
        if hasattr(self, '_user_settings'):
            delattr(self, '_user_settings')


app_settings = AppSettings(DEFAULTS, IMPORT_STRINGS)


@receiver(setting_changed)
def reload_package_settings(*args, **kwargs):
    setting = kwargs['setting']
    if setting == app_settings.setting_name:
        app_settings.reload()
