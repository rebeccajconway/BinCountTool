import streamlit as st
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler
import io
import os
from datetime import datetime


def select_file(helptext, file_types: list[str], label: str="Select a file") -> tuple:
    """File upload component for Streamlit."""
    file = st.file_uploader(label, type=file_types, help=helptext)
    if file is not None:
        return file.name, file
    return "No file selected", None


def download_button(output: str, file_name: str, label_button) -> None:
    """Creates a output button with a downloadable file."""
    st.header("Download")
    st.download_button(
        label=label_button,
        data=output,
        file_name=file_name + ".csv",
        mime="text/csv",
    )

class HelpTexts:
    """Help Messages to be displayed throughout Program"""
    run_selection = "The Bin Count Tool is always ran. To run the Bin Distribution Tool, you will an outbound csv file with columns: timestamp, sku, and quantity"
    sku_master = "csv file with columns matching those shown on the left of the screen under 'Required Columns'"
    bin_utilization = "Max Bin Utilization looks at what % of a bin can be volumetrically filled with product"
    max_compartments = "Max # of compartments allowable in a bin"
    max_weight = "Current guidelines say a full height 330mm or 220mm bin system is 25kg. Up to 30kg is allowed for 16 x 330 or 22 x 220mm and less"
    max_bins_per_sku = "If a sku requires more bins thank this number, only this number of bins will be stored in the system. The full # that would be required will eb output in another column."
    outbound = "csv file with 'sku', 'timestamp', and 'qty' columns. case-insensitive."
    percent_empty = "desired % of empty bins in the system"
    restock_percent = "Stock will be triggered to replinish when this % of initial inventory is reached"
    rename_columns = "If the uploaded CSV column names don't match the required names, update corresponding column names in the CSV here"

def uf_to_df(uf):
    """translates a UploadFile to a dataframe"""

    if uf is not None:
        try:
            file_content = uf.read() # Read the content of the file
            if isinstance(file_content, bytes): # Convert from bytes to string if necessary
                file_content = file_content.decode('utf-8')
            file_buffer = io.StringIO(file_content) # Create a StringIO object from the content        
            file_buffer.seek(0) # Reset buffer position to the start
            thousands_sep = st.session_state.inputs.get('sku_thousands', ',')
            
            # Check if thousands separator is valid (must be a single character or None)
            if thousands_sep and len(thousands_sep) > 1:
                st.warning(f"Thousands separator '{thousands_sep}' is invalid. Must be a single character. Using default ',' instead.")
                thousands_sep = ','
            elif thousands_sep == '':
                thousands_sep = None
            
            # Read the CSV into a DataFrame using pandas
            df = pd.read_csv(
                file_buffer,
                delimiter=st.session_state.inputs['sku_delimiter'],
                thousands=thousands_sep,
                decimal=st.session_state.inputs['sku_decimal']
            )
            # st.write(df.head()) # Debugging
            return df

        except pd.errors.EmptyDataError:
            st.error("The CSV file has no columns to parse. Please check the file format and delimiter.")
        except Exception as e:
            st.error(f"Error reading CSV file: {str(e)}")
    else:
        st.warning("No outbound file selected. Please upload a CSV file.")

def setup_logger():
   
    # Get the directory of the current Python file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(base_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create a NEW timestamp-based log filename each time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(logs_dir, f'streamlit_app_{timestamp}.log')
    
    # Important: Get a NEW logger name each time using the timestamp
    # This ensures we don't reuse the previous logger
    logger_name = f"streamlit_logger_{timestamp}"
    logger = logging.getLogger(logger_name)
    
    # Force the logger level (don't rely on root logger configuration)
    logger.setLevel(logging.DEBUG)
    
    # Make sure propagation is disabled to avoid duplicate logs
    logger.propagate = False
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create and add file handler
    file_handler = logging.FileHandler(log_filename, mode='w')  # Use 'w' mode to start fresh
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Create and add console handler
    #console_handler = logging.StreamHandler()
    #console_handler.setFormatter(formatter)
    #logger.addHandler(console_handler)
    
    # Log test message to verify setup
    logger.info(f"New logger '{logger_name}' initialized successfully")
    
    # Print confirmation to console for debugging
    print(f"Created new log file: {log_filename}")
    
    return logger

def stop_button():
    if st.session_state['enable_stop']:
        st.button(label = "stop and save", key = "stop_button")
    