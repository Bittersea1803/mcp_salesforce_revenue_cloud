# salesforce_auth.py
import os
from simple_salesforce import Salesforce, SalesforceError
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

# Salesforce Credentials from .env - primarily for Session ID
SF_SESSION_ID = os.getenv("SALESFORCE_SESSION_ID")
SF_DOMAIN_URL = os.getenv("SALESFORCE_DOMAIN_URL") # Expected: https://yourinstance.my.salesforce.com

def get_salesforce_client():
    """
    Creates and returns a Salesforce client instance using simple-salesforce,
    exclusively using a pre-obtained Session ID.
    """
    print("INFO: salesforce_auth.py - Attempting Salesforce authentication using provided Session ID...")

    if not SF_SESSION_ID:
        raise ValueError("CRITICAL ERROR: SALESFORCE_SESSION_ID is not set in the .env file. This is required.")
    if not SF_DOMAIN_URL:
        raise ValueError("CRITICAL ERROR: SALESFORCE_DOMAIN_URL is not set in the .env file (e.g., 'https://yourinstance.my.salesforce.com'). This is required.")

    parsed_url = urlparse(SF_DOMAIN_URL)
    if not parsed_url.scheme or not parsed_url.netloc: # Provjerava je li URL ispravan
        raise ValueError("CRITICAL ERROR: SALESFORCE_DOMAIN_URL in .env is not a valid full URL. It must include scheme (e.g., 'https://') and netloc (e.g., 'yourinstance.my.salesforce.com').")
    
    instance_url_for_session = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    try:
        sf = Salesforce(
            session_id=SF_SESSION_ID,
            instance_url=instance_url_for_session
        )
        
        print("INFO: salesforce_auth.py - Verifying Session ID with a limits() call...")
        sf.limits() # This call verifies the session is active
        print(f"INFO: salesforce_auth.py - Salesforce authentication with Session ID successful. Connected to instance: {sf.sf_instance}")
        return sf
        
    except SalesforceError as se:
        error_code = getattr(se, 'code', 'N/A')
        error_message_detail = getattr(se, 'message', 'No specific message')
        error_content = getattr(se, 'content', 'No additional content')
        print(f"ERROR: salesforce_auth.py - Salesforce API error during Session ID validation or client instantiation: Code: {error_code}, Message: {error_message_detail}, Content: {error_content}")
        print("       Please ensure your SALESFORCE_SESSION_ID is current and valid, and SALESFORCE_DOMAIN_URL is correct.")
        raise # Re-raise to be caught by app.py or the caller
    except Exception as e:
        print(f"ERROR: salesforce_auth.py - Unexpected error during Salesforce client initialization with Session ID: {e}")
        raise # Re-raise

if __name__ == '__main__':
    # Testni blok za direktno pokretanje ove datoteke
    print("INFO: Testing Salesforce authentication (salesforce_auth.py - Session ID Only)...")
    try:
        client = get_salesforce_client()
        if client:
            print(f"INFO: Successfully obtained Salesforce client. Instance: {client.sf_instance}")
            limits = client.limits() 
            print(f"INFO: API usage (DailyApiRequests): {limits['DailyApiRequests']['Remaining']}/{limits['DailyApiRequests']['Max']}")
            print("INFO: Salesforce authentication test using Session ID successful.")
    except Exception as e:
        print(f"ERROR: Salesforce authentication test failed: {e}")
        print("       Ensure SALESFORCE_SESSION_ID and SALESFORCE_DOMAIN_URL are correctly set in your .env file and the session is active.")
