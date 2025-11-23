from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-&)pt3d)j$yj8kyu3!*v+0=+i%8nlft05r49n&n!^xst(fzs8pf'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    'morphotic-squally-jericho.ngrok-free.dev',
    'morphotic-squally-jericho.ngrok-free.app',
    '18.224.202.124',
    'ec2-18-224-202-124.us-east-2.compute.amazonaws.com',
    'speakupsurrey-app.s3-website.us-east-2.amazonaws.com',
    'loudsurrey.online',
    'www.loudsurrey.online'
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',

    # Third-party apps
    'corsheaders',      # Ensure this is here
    'rest_framework',
    'solo',

    # Your apps
    'api',              # Assuming this is one of your apps
    'apps.core',
    'apps.users',
    'apps.posts',
    'apps.moderation',
    'apps.payments',
]

# CORRECTED: Middleware order is crucial for CORS to function correctly.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # CorsMiddleware should be placed as high as possible, especially before any middleware
    # that can generate responses such as CommonMiddleware.
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # The duplicate CommonMiddleware line has been removed.
]

# CORRECTED: Using a specific whitelist is more secure than allowing all origins.
CORS_ALLOWED_ORIGINS = [
    "https://localhost:5173",
    "https://127.0.0.1:5173", 
    "http://speakupsurrey-app.s3-website.us-east-2.amazonaws.com"
]

CSRF_TRUSTED_ORIGINS = [
    "https://localhost:5173" 
    "https://127.0.0.1:5173", 
    "http://speakupsurrey-app.s3-website.us-east-2.amazonaws.com",
    'https://loudsurrey.online',
    'https://www.loudsurrey.online'
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# This line is commented out because CORS_ALLOWED_ORIGINS is safer.
# CORS_ALLOW_ALL_ORIGINS = True

# This setting correctly allows the browser to send cookies.
CORS_ALLOW_CREDENTIALS = True

# For cross-site API calls, SameSite must be 'None'.
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

ROOT_URLCONF = 'sbe.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sbe.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'sslmode': config('DB_SSLMODE', default='require')
        },
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# In your settings.py

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # This tells DRF *not* to use Django's session/CSRF system.
        # This will globally fix your 403 error for all API views.
        
        # If you add Token or JWT auth later, you'll add it here, e.g.:
        # 'rest_framework.authentication.TokenAuthentication',
    ],
    
    # You can also set AllowAny as the default for now
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ]
}

# --- CELERY CONFIGURATION ---
# This is the URL of your message broker (the 'in-tray').
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'

# This is the backend where Celery stores the results of tasks.
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = config('S3_BUCKET_NAME')
AWS_S3_REGION_NAME = config('AWS_REGION_NAME')
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
# AWS_DEFAULT_ACL = 'public-read'

# Instagram API Configuration
INSTAGRAM_BUSINESS_ACCOUNT_ID = config('IG_BUSINESS_ACCOUNT_ID')
ACCESS_TOKEN = config('IG_PAGE_ACCESS_TOKEN')
GRAPH_API_VERSION = 'v24.0' # Note: Use a recent, valid version like v19.0 or v20.0

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY')
STRIPE_API_SECRET_KEY = config('STRIPE_API_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET')
