import streamlit as st


st.set_page_config(
        page_title="Bin Count Tool and Simulation",
        # page_icon = "images/logo.png" # need to save logo here later
        menu_items={
            "Report a Bug": "mailto:rebecca.conway@autostoresystem.com", # hide my email address?
            "Get Help": "mailto:rebecca.conway@autostoresystem.com"
            },
    )

import pandas as pd
import time
import math
import datetime
import os



## Check SF Token / Access Eligibility
from check_token import verify_token, refresh_token_if_needed

# Verify the Salesforce token at startup
token_valid, sf = verify_token(use_mock=True) #update to remove mock statement in production

if not token_valid:
    st.info("FInitial token invalid, attempting to refresh...")
    token_valid, sf = refresh_token_if_needed()
    
    if not token_valid:
        st.error("Failed to establish Salesforce connection. Please reach out to Solutions for support")
        
    else:
        # st.success("Token refreshed successfully!")
        pass
else:
    # st.success("Salesforce connection established successfully!")
    pass

## UX for those who get SF approval:

st.title("Bin Count Tool and Simulation")

st.write("Welcome to the Bin Count Tool and Simulation. Use the sidebar to navigate to different sections")

#Instructions for using the application
st.header("Getting Started")
st.write("""
         1. Go to the Configuration page to set up your parameters
         2. Once configured and data is uploaded, start the Run from the Run page
         3. View your results in the Results page
         4. For and explaination of how the tool works, see page 'Explaination'
         """)

st.write("Version 2.1")


