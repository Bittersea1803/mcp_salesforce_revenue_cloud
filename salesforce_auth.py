# salesforce_auth.py

import requests  # For making HTTP requests to the Salesforce token endpoint.
import os        # For accessing environment variables.
from dotenv import load_dotenv # To load variables from the .env file.

# Load environment variables from .env file into the script's environment.
load_dotenv()

# Retrieve Salesforce credentials from environment variables.
SALESFORCE_CLIENT_ID = os.getenv("SALESFORCE_CLIENT_ID")
SALESFORCE_CLIENT_SECRET = os.getenv("SALESFORCE_CLIENT_SECRET")
SALESFORCE_USERNAME = os.getenv("SALESFORCE_USERNAME")
SALESFORCE_PASSWORD = os.getenv("SALESFORCE_PASSWORD") # Should be password + security token
SALESFORCE_DOMAIN = os.getenv("SALESFORCE_DOMAIN")     # e.g., https://login.salesforce.com

# A simple in-memory cache for the session data (access token and instance URL).
# In a multi-user or stateless environment, this should be stored in a more robust cache (e.g., Redis).
_session_data = {}

def get_salesforce_session():
    """
    Authenticates with Salesforce using the Username-Password flow and retrieves an access token.
    Caches the session data to avoid re-authenticating on every call.
    
    Returns:
        dict: A dictionary containing 'access_token' and 'instance_url' if successful, None otherwise.
    """
    global _session_data # Allow modification of the global _session_data variable.

    # Check if we have a cached and valid session.
    # A more robust check would verify token expiration.
    if _session_data and 'access_token' in _session_data:
        print("INFO: Using cached Salesforce session.")
        return _session_data

    print("INFO: Attempting to get new Salesforce session via Username-Password flow...")
    
    # Construct the URL for the Salesforce token endpoint.
    auth_url = f"{SALESFORCE_DOMAIN}/services/oauth2/token"
    
    # Prepare the payload for the OAuth 2.0 Password Grant Type.
    # This grant type sends username and password directly, which is why it's less secure for many scenarios.
    payload = {
        'grant_type': 'password',
        'client_id': SALESFORCE_CLIENT_ID,
        'client_secret': SALESFORCE_CLIENT_SECRET,
        'username': SALESFORCE_USERNAME,
        'password': SALESFORCE_PASSWORD
    }

    try:
        # Make the POST request to the Salesforce token endpoint.
        response = requests.post(auth_url, data=payload)
        # Raise an HTTPError if the HTTP request returned an unsuccessful status code (4xx or 5xx).
        response.raise_for_status()
        
        # Parse the JSON response from Salesforce.
        auth_response_data = response.json()
        
        # Cache the access token and instance URL.
        _session_data = {
            'access_token': auth_response_data.get('access_token'),
            'instance_url': auth_response_data.get('instance_url')
        }
        print("INFO: Salesforce session obtained successfully.")
        return _session_data
        
    except requests.exceptions.RequestException as e:
        # Handle any errors during the HTTP request (network issues, Salesforce errors).
        print(f"ERROR: Salesforce authentication failed: {e}")
        if response is not None:
            # Print the response content if available, as it often contains useful error details from Salesforce.
            print(f"ERROR: Salesforce response content: {response.text}")
        return None

# This block allows testing the authentication directly when running this file.
if __name__ == '__main__':
    print("INFO: Testing Salesforce authentication...")
    session = get_salesforce_session()
    if session:
        # Print only a portion of the access token for brevity and security.
        print(f"Access Token (first 20 chars): {session['access_token'][:20]}...")
        print(f"Instance URL: {session['instance_url']}")
    else:
        print("ERROR: Failed to authenticate with Salesforce. Check .env settings and Salesforce Connected App.")