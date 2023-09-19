SECRET_KEY = "psst"
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ROOT_URLCONF = "abdm_python_integrator.urls"

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework.authtoken",
    "abdm_python_integrator",
)

ABDM_INTEGRATOR = {
    "CLIENT_ID": 'dummy',
    "CLIENT_SECRET": 'dummy',
    "X_CM_ID": 'dummy',
    "ABHA_URL": '',
    "GATEWAY_URL": '',
    "AUTHENTICATION_CLASS": "rest_framework.authentication.TokenAuthentication",
    "HRP_ABHA_REGISTERED_CHECK_CLASS": None,
}
