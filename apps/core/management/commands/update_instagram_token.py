# apps/core/management/commands/update_instagram_token.py

import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.models import GlobalSettings

class Command(BaseCommand):
    help = 'Exchanges a short-lived User Token for a Permanent Page Access Token and saves it.'

    def add_arguments(self, parser):
        parser.add_argument('short_lived_token', type=str, help='The short-lived User Access Token from Graph API Explorer')

    def handle(self, *args, **options):
        short_token = options['short_lived_token']
        app_id = settings.AWS_ACCESS_KEY_ID  # You might need to add FB_APP_ID to settings if not present, assuming use of env vars
        # Note: Ensure you have FB_APP_ID and FB_APP_SECRET in your .env and settings.py
        # For this script to work, we need specific Meta Creds. 
        # If they aren't in settings, you can hardcode them temporarily or add them.
        
        # Assuming these are available in settings.py:
        # FB_APP_ID = config('FB_APP_ID')
        # FB_APP_SECRET = config('FB_APP_SECRET')
        
        # If not, let's prompt or error. For now, I will assume they are needed.
        from decouple import config
        try:
            fb_app_id = config('FB_APP_ID')
            fb_app_secret = config('FB_APP_SECRET')
        except:
            self.stdout.write(self.style.ERROR("Error: FB_APP_ID and FB_APP_SECRET must be in your .env file."))
            return

        self.stdout.write("1. Exchanging Short-Lived User Token for Long-Lived User Token...")
        
        exchange_url = "https://graph.facebook.com/v19.0/oauth/access_token"
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': fb_app_id,
            'client_secret': fb_app_secret,
            'fb_exchange_token': short_token
        }
        
        resp = requests.get(exchange_url, params=params)
        if resp.status_code != 200:
            self.stdout.write(self.style.ERROR(f"Failed to exchange token: {resp.json()}"))
            return
            
        long_lived_user_token = resp.json().get('access_token')
        self.stdout.write(self.style.SUCCESS("Success! Got Long-Lived User Token."))

        self.stdout.write("2. Fetching Accounts/Pages to find the Permanent Page Token...")
        
        accounts_url = "https://graph.facebook.com/v19.0/me/accounts"
        page_params = {
            'access_token': long_lived_user_token,
            'fields': 'name,access_token,instagram_business_account'
        }
        
        resp_pages = requests.get(accounts_url, params=page_params)
        if resp_pages.status_code != 200:
            self.stdout.write(self.style.ERROR(f"Failed to fetch pages: {resp_pages.json()}"))
            return

        data = resp_pages.json().get('data', [])
        if not data:
            self.stdout.write(self.style.ERROR("No pages found for this user."))
            return

        # If multiple pages, simple logic to pick the one linked to our IG Business ID
        target_ig_id = settings.INSTAGRAM_BUSINESS_ACCOUNT_ID
        selected_token = None
        selected_page_name = None

        for page in data:
            ig_info = page.get('instagram_business_account', {})
            ig_id = ig_info.get('id')
            
            # If we match the specific IG account in settings, or if there is only one page
            if str(ig_id) == str(target_ig_id) or len(data) == 1:
                selected_token = page.get('access_token')
                selected_page_name = page.get('name')
                break
        
        if not selected_token:
            self.stdout.write(self.style.WARNING(f"Could not automatically match IG ID {target_ig_id}. Available Pages:"))
            for i, page in enumerate(data):
                self.stdout.write(f"{i}: {page.get('name')} (IG: {page.get('instagram_business_account', {}).get('id')})")
            
            idx = input("Enter the index number of the page to use: ")
            try:
                selected_token = data[int(idx)].get('access_token')
                selected_page_name = data[int(idx)].get('name')
            except:
                self.stdout.write(self.style.ERROR("Invalid selection."))
                return

        self.stdout.write(self.style.SUCCESS(f"Selected Page: {selected_page_name}"))
        self.stdout.write("3. Saving Permanent Page Token to GlobalSettings...")

        global_settings = GlobalSettings.objects.get() # Assuming one exists, get_or_create if safer
        global_settings.instagram_access_token = selected_token
        global_settings.save()

        self.stdout.write(self.style.SUCCESS("Done! The API is now using a never-expiring token."))