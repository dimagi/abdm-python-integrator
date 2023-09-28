# abdm-python-integrator

ABDM integrator is a REST API service packaged as a django app. 
It implements all the three milestones of [ABDM](https://sandbox.abdm.gov.in/abdm-docs/getting-started).
This package is intended to be used by developers aiming to perform integration with ABDM using python.

## Apps
The `abdm_integrator` includes below apps as per milestones:
1. abha - features related to milestone 1 
2. hip - features related to milestone 2 
3. hiu - features related to milestone 3

These apps can be added to Django `INSTALLED_APPS` setting based on what milestone/service 
is needed for integration.

## Requirements
- python >= 3.8
- celery

For python dependencies, refer `dependencies` section in [pyproject.toml](pyproject.toml)
For celery, add desired configuration in django settings. Refer [Celery documentation](https://docs.celeryq.dev/en/stable/getting-started/introduction.html).

## Installation

```commandline
pip install abdm-python-integrator@git+https://github.com/dimagi/abdm-python-integrator.git
```

## Settings

1. Add required apps to Django `INSTALLED_APPS` setting.
    ```
        'abdm_integrator.abha',
        'abdm_integrator.hiu',
        'abdm_integrator.hip',
    ```

2. Add below settings to your Django settings file.

    ```python
    ABDM_INTEGRATOR = {
        # REQUIRED setting.
        # Client ID provided by ABDM. 
        'CLIENT_ID': 'dummy-value',
    
        # REQUIRED setting.
        # Client Secret provided by ABDM.
        'CLIENT_SECRET': 'dummy-value',
        
        # REQUIRED setting.
        # Consent Manager ID for ABDM as per environment.
        # Below value is for ABDM sandbox environment.
        'X_CM_ID': 'sbx',
        
        # REQUIRED setting.
        # Base URL for Abha APIS (M1).
        # Below value is for ABDM sandbox environment.
        'ABHA_URL': 'https://healthidsbx.abdm.gov.in/api',
        
        # REQUIRED setting.
        # Base URL for Gateway APIS (M2/M3 and Access Token).
        # Below value is for ABDM sandbox environment.
        'GATEWAY_URL': 'https://dev.abdm.gov.in/gateway',
        
        # REQUIRED setting. Defaults to Django User model.
        # User Model. Specify as 'app_label.Model'
        # Used for storing request user for consents and health information requests
        'USER_MODEL': 'auth.User',
        
        # REQUIRED setting. 
        # Any Authentication class that is compatible with Rest Framework Authentication mechanism.
        # Used for APIs other than those exposed to ABDM Gateway.
        # REQUIRED setting. Below value uses REST Framework Token Authentication.
        'AUTHENTICATION_CLASS': 'rest_framework.authentication.TokenAuthentication',
        
        # OPTIONAL setting. Default value is None.
        # Class responsible for checking if ABHA is already registered onto HRP system while creating new ABHA ID.
        # Implement interface 'HRPAbhaRegisteredCheck' as defined in 'integrations.py'
        # If this check is not needed, skip this setting or set the value to None.
        'HRP_ABHA_REGISTERED_CHECK_CLASS': None,
    }
    ```

3. Run migrations.

    ```commandline
    python manage.py migrate abdm_hiu
    python manage.py migrate abdm_hip
    ```

4. Include app urls into your Django root url config.
    ```
    url(r'^abdm/', include('abdm_integrator.urls')),
    ```


## Testing
Run the below command to run test cases. Uses settings as defined in `test_settings.py`
```commandline
python manage.py test
```
