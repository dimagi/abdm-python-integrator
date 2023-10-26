SECRET_KEY = "psst"
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ROOT_URLCONF = "abdm_integrator.urls"

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework.authtoken",
    "abdm_integrator.abha",
    "abdm_integrator.hiu",
    "abdm_integrator.hip"
)

ABDM_INTEGRATOR = {
    "CLIENT_ID": 'dummy',
    "CLIENT_SECRET": 'dummy',
    "X_CM_ID": 'dummy',
    "ABHA_URL": '',
    "GATEWAY_URL": '',
    "USER_MODEL": "auth.User",
    "AUTHENTICATION_CLASS": "rest_framework.authentication.TokenAuthentication",
    "HRP_ABHA_REGISTERED_CHECK_CLASS": None,
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
