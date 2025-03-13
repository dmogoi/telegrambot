"""
Django settings for config project.

Generated by 'django-admin startproject' using Django 5.1.2.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""
import os
from pathlib import Path
from dotenv import load_dotenv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')  # Load .env from project root

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')

# Telegram Configuration
API_ID = os.getenv('TG_API_ID')
if API_ID is not None:
    API_ID = int(API_ID)  # Convert to integer

API_HASH = os.getenv('TG_API_HASH')
PHONE_NUMBER = os.getenv('TG_PHONE_NUMBER')

# SMS Configuration
MOBILESASA_TOKEN = 'YvC9Vl8fnsjXvcshyA1z2Aq7Ol4xG3BxZp6xcq0sD58S97wu3D4Ce3JURYAY'
SMS_SENDER_ID = 'MOBILESASA'  # Or your approved sender ID
TWILIO_SID = os.getenv('TWILIO_SID')
TWILIO_TOKEN = os.getenv('TWILIO_TOKEN')
OWNER_PHONE = os.getenv('OWNER_PHONE')


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-o5l)d3_u^5@3f#c^oc#%r3f06-v8d+xw1+x29u)is6l^4wj!_i'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['bot-x8m2.onrender.com', 'localhost', '127.0.0.1']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bot',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # <-- Add this
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}



#CELERY_BROKER_URL = 'redis://localhost:6379/0'
#CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_BROKER_URL = 'redis://red-cv998kd2ng1s73d1o3f0:6379/0'
CELERY_RESULT_BACKEND = 'redis://red-cv998kd2ng1s73d1o3f0:6379/0'


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'
# settings.py
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')



# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Only during development, serve media files
# if DEBUG:
#     from django.conf.urls.static import static
#     urlpatterns += static(MEDIA_URL, document_root=MEDIA_ROOT)

# config/settings.py
# config/settings.py
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        # Your application logs
        'bot': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        # Suppress Telethon debug logs
        'telethon': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'mtproto': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    }
}
