"""
This program validates the token provided by Salesforce to determine if user has access
Backend and has no impact on UI 
"""

import os
from simple_salesforce import Salesforce
import requests
from dotenv import load_dotenv
import streamlit as st

# Load environment variables from a .env file (for local development)
load_dotenv()

def verify_token(access_token=None, instance_url=None, use_mock=False):
    """
    Verifies if the provided Salesforce access token is valid.
    Returns a tuple of (is_valid, sf_connection) where:
    - is_valid: Boolean indicating if token is valid
    - sf_connection: Salesforce connection object if valid, None otherwise
    """

    # For mock mode testing:
    if use_mock or os.gentenv("SF_USE_MOCK")== "True":
        st.write("Using mock Salesforce connection")
        return True, get_mock_connection()

    # Use provided tokens or get from environment
    access_token = access_token or os.getenv("SF_ACCESS_TOKEN")
    instance_url = instance_url or os.getenv("SF_INSTANCE_URL")
    
    if not access_token or not instance_url:
        return False, None
    
    try:
        # Attempt to connect
        sf = Salesforce(instance_url=instance_url, session_id=access_token)
        
        # Test the connection with a lightweight query
        sf.query("SELECT Id FROM Account LIMIT 1")
        
        # If we reach here, the token is valid
        return True, sf
    except Exception as e:
        print(f"Token verification failed: {str(e)}")
        return False, None

def refresh_token_if_needed():
    """
    Attempts to refresh the token if it's invalid or expired.
    Returns a tuple of (success, sf_connection)
    """
    # First check if current token is valid
    is_valid, sf = verify_token()
    
    if is_valid:
        return True, sf
    
    # Token is invalid, try to refresh
    client_id = os.getenv("SF_CLIENT_ID")
    client_secret = os.getenv("SF_CLIENT_SECRET")
    refresh_token = os.getenv("SF_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        return False, None
    
    try:
        payload = {
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token
        }
        
        token_url = os.getenv("SF_TOKEN_URL", "https://login.salesforce.com/services/oauth2/token")
        
        response = requests.post(token_url, data=payload)
        if response.status_code == 200:
            response_data = response.json()
            access_token = response_data['access_token']
            instance_url = response_data['instance_url']
            
            # Store new token in environment (for this session)
            os.environ["SF_ACCESS_TOKEN"] = access_token
            os.environ["SF_INSTANCE_URL"] = instance_url
            
            # Now verify the new token works
            return verify_token(access_token, instance_url)
        else:
            print(f"Failed to refresh token: {response.text}")
            return False, None
    except Exception as e:
        print(f"Error refreshing token: {str(e)}")
        return False, None

#if __name__ == "__main__":
    # This allows you to run this file directly to test token verification
#    is_valid, _ = verify_token()
#    print(f"Token verification result: {'Valid' if is_valid else 'Invalid'}")


def get_mock_connection():
    """Returns a mock Salesforce connection for testing"""
    class MockSalesforce:
        def query(self, *args, **kwargs):
            return {"records": [{"Id": "001MOCKID"}]}
        # Add any other Salesforce methods you need to mock
    
    return MockSalesforce()