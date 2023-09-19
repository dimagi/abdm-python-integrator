# abdm-python-integrator

ABDM integrator is a REST API service packaged as a django app. 
It implements all the three milestones of [ABDM](https://sandbox.abdm.gov.in/abdm-docs/getting-started).
This package is intended to be used by developers aiming to perform integration with ABDM using python.

## Requirements
- python >= 3.8
- django >= 3.2
- djangorestframework >= 3.12
- requests

## Installation

```commandline
pip install abdm-python-integrator@git+https://github.com/dimagi/abdm-python-integrator.git
```

## Sub Apps
The `abdm_integrator` is split into below apps as per milestones:
1. abha - features related to milestone 1
2. hiu - features related to milestone 2

These sub apps can be added to Django `INSTALLED_APPS` setting based on what service is required for your project.

## Settings
1. Add required apps to Django `INSTALLED_APPS` setting.
```
    'abdm_integrator.abha',
    'abdm_integrator.hiu',
```

2. Include app urls into your Django root url config.
    ```
    url(r'^abdm/', include('abdm_integrator.urls')),
    ```

3. Add below settings to your Django settings file.
   [test_settings](test_settings.py)
    ```python
    ABDM_INTEGRATOR = {
        # Client ID provided by ABDM. 
        # Required setting.
        'CLIENT_ID': 'dummy-value',
        
        # Client Secret provided by ABDM.
        # Required setting.
        'CLIENT_SECRET': 'dummy-value',
        
        # Consent Manager ID for ABDM as per environment.
        # Required setting. Below value is for ABDM sandbox environment.
        'X_CM_ID': 'sbx',
        
        # Base URL for Abha APIS (M1).
        # Required setting. Below value is for ABDM sandbox environment.
        'ABHA_URL': 'https://healthidsbx.abdm.gov.in/api',
        
        # Base URL for Gateway APIS (M2/M3 and Access Token).
        # Required setting. Below value is for ABDM sandbox environment.
        'GATEWAY_URL': 'https://dev.abdm.gov.in/gateway',

        # User Model. Specify as 'app_label.Model'
        # Set as per your project requirements. Used for storing request user for consents and health information requests
        # Required setting. Below value uses Django User model.
        'USER_MODEL': 'auth.User',
        
        
        # Any Authentication class that is compatible with Rest Framework Authentication mechanism.
        # Set as per your project requirements. Used for APIs other than those exposed to ABDM Gateway.
        # Required setting. Below value uses REST Framework Token Authentication.
        'AUTHENTICATION_CLASS': 'rest_framework.authentication.TokenAuthentication',
        
        # Class responsible for checking if ABHA is already registered onto HRP system while creating new ABHA ID.
        # Implement interface 'HRPAbhaRegisteredCheck' as defined in 'integrations.py'
        # If this check is not needed, skip this setting or set the value to None.
        # Optional setting. Default value is None.
        'HRP_ABHA_REGISTERED_CHECK_CLASS': None,
    }
    ```

5. Run migrations

```commandline
python manage.py migrate abdm_hiu
```

## Testing
Run the below command to run test cases. Uses settings as defined in `test_settings.py`
```commandline
python manage.py test
```
