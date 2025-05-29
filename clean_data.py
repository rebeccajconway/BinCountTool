import streamlit as st
import pandas as pd
from bincountcalc import import_sku_file

class CleanData:
    
    def __init__(self):
        self.errors:list[str] = []
    
    
    def prep_sku_master(self, inputs):
        # purpose of this function is to check that the uploaded csv file for sku master data is formatted appropriately

        # prepare data
        errors = self.errors
        skus = import_sku_file(inputs, errors)
        # st.write(f"skus data type in check: {type(skus)}")
        approval_to_run = True

        return approval_to_run # make true or false
    
    def _prep_outbound(self, outbound_df):
        # purpose is to make sure the outbound file is properly formatted and fix it if it is not

        outbound_df_copy = outbound_df.copy()

        # Clean column names - strip whitespace and lowercase for column names only
        outbound_df_copy.columns = outbound_df_copy.columns.str.strip().str.lower()
        
        # Handle timestamp conversion with error handling
        try:
            if 'timestamp' in outbound_df_copy.columns:
                outbound_df_copy['timestamp'] = pd.to_datetime(outbound_df_copy['timestamp'], errors='coerce')
        except Exception as e:
            st.error(f"Error converting timestamps: {e}")
            # Set invalid timestamps to NaT
            outbound_df_copy['timestamp'] = pd.to_datetime(outbound_df_copy['timestamp'], errors='coerce')
        
        # Clean SKUs - strip whitespace but preserve case
        if 'sku' in outbound_df_copy.columns:
            # Convert to string first
            outbound_df_copy['sku'] = outbound_df_copy['sku'].astype(str)
            # Remove leading/trailing whitespace but preserve case
            outbound_df_copy['sku'] = outbound_df_copy['sku'].str.strip()
        
        # Clean and convert quantities with error handling
        if 'qty' in outbound_df_copy.columns:
            # First strip any whitespace if string type
            if pd.api.types.is_string_dtype(outbound_df_copy['qty']):
                outbound_df_copy['qty'] = outbound_df_copy['qty'].str.strip()
            
            # Try to convert to numeric, with error handling
            try:
                outbound_df_copy['qty'] = pd.to_numeric(outbound_df_copy['qty'], errors='coerce')
            except Exception as e:
                st.error(f"Error converting quantities: {e}")
                outbound_df_copy['qty'] = pd.to_numeric(outbound_df_copy['qty'], errors='coerce')
        
        
        # converting all skus to string data type to reduce potential errors
        outbound_df_copy['sku'] = outbound_df_copy['sku'].astype(str)
        
        # Identify rows with missing critical data
        missing_mask = outbound_df_copy['timestamp'].isna() | outbound_df_copy['sku'].isna() | outbound_df_copy['qty'].isna()
        
        # Extract incomplete rows to a separate dataframe
        incomplete_df = outbound_df_copy[missing_mask].copy()
        
        # Get only the complete rows for processing
        complete_df = outbound_df_copy[~missing_mask].copy()
        
        # Store the count of incomplete rows
        st.session_state['number_incomplete_outbound'] = len(incomplete_df)
        st.session_state['number_complete_outbound'] = len(complete_df)

        complete_df['original_order'] = range(len(complete_df)) # Create a temporary index column to preserve original order
        complete_df = complete_df.sort_values(['timestamp', 'original_order']) # Sort by timestamp first, then by original order
        complete_df = complete_df.drop('original_order', axis=1) # Drop the temporary column
    
        sorted_outbound_df = complete_df.reset_index(drop=True) # Reset the index to ensure it's sequential

        return sorted_outbound_df
    

