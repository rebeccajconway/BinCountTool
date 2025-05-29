import streamlit as st


st.set_page_config(
        page_title="Bin Count Tool and Simulation"
        )



st.title("Explaination of Tool")
st.write("This page explains what is happening behind the scenes in this tool")

tab1, tab2, tab3 = st.tabs(['Bin Count Tool', 'Bin Distribution Simulation', 'Assumptions'])

with tab1:
    st.subheader("Bin Count Tool")
    st.write("The Bin Count Tool is used to quickly size out the number of bins required for an AutoStore system based on customer SKU data and quantities stored.")
    

with tab2:
    st.subheader("Bin Distribution Simulation")
    # Example chart - replace with your actual simulation data
    st.write("The purpose of the Bin Distribution Simulation is to get a better estimate of what the Bin Distribution will look like in a working system." \
    "")
    
    st.write("""
        The Bin Distribution Simulation is built upon the data gathered in the Bin Count Tool.

                """)
with tab3:
    st.subheader("Assumptions")
