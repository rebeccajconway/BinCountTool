import streamlit as st
import urllib.parse

def help_sidebar():
    st.title("My Streamlit App")
    
    # Create a container for the help menu in the sidebar
    with st.sidebar:
        with st.expander("📋 Help & Support"):
            st.markdown("<h4 style='text-align: center;'>How can we assist you?</h4>", unsafe_allow_html=True)
            
            # Get Help option
            st.markdown("### Get Help")
            st.write("Have a question? We're here to help!")
            email = "abc@gmail.com"
            subject = urllib.parse.quote("Help Requested")
            body = urllib.parse.quote("Please describe what you need help with:")
            mailto_link = f"mailto:{email}?subject={subject}&body={body}"
            st.markdown(f"<a href='{mailto_link}' target='_blank' style='display: inline-block; padding: 8px 16px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 4px;'>Email Support</a>", unsafe_allow_html=True)
            
            st.markdown("<hr>", unsafe_allow_html=True)
            
            # Report a Bug option
            st.markdown("### Report a Bug")
            st.write("Found an issue? Let us know so we can fix it!")
            email = "abc@gmail.com"
            subject = urllib.parse.quote("Bug Reported")
            body = urllib.parse.quote("Please describe the bug you encountered:")
            mailto_link = f"mailto:{email}?subject={subject}&body={body}"
            st.markdown(f"<a href='{mailto_link}' target='_blank' style='display: inline-block; padding: 8px 16px; background-color: #FF5252; color: white; text-decoration: none; border-radius: 4px;'>Report Bug</a>", unsafe_allow_html=True)
    
    # Your app content
    st.write("Your app content goes here")