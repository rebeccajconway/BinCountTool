import streamlit as st

def init_session_states():
    """initialize session_state variables if they do not exist"""

    if 'start_time' not in st.session_state:
        st.session_state['start_time'] = None
    if 'pick_orders_df' not in st.session_state:
        print("pick_orders_df re-written to blank")
        st.session_state['pick_orders_df'] = []  
    if 'pick_orders_output_csv' not in st.session_state:
        st.session_state['pick_orders_output_csv'] = [] 
    if 'pick_orders_lines_in_as' not in st.session_state:
        st.session_state['pick_orders_lines_in_as'] = []

    if 'save_interval' not in st.session_state:
        st.session_state['save_interval'] = 1000  # num iterations between saves
    if 'stop_button' not in st.session_state:
        st.session_state['stop_button']= False
    if 'skip_empty_bin_allowance' not in st.session_state:
        st.session_state['skip_empty_bin_allowance'] = 20
    if 'allowable_empties_counter' not in st.session_state:
        st.session_state['allowable_empties_counter'] = 0
    if 'enable_stop' not in st.session_state:
        st.session_state['enable_stop'] = False
    if 'stop_run' not in st.session_state:
        st.session_state['stop_run'] = False
    if 'stop_reason' not in st.session_state:
        st.session_state['stop_reason'] = "Stop and Save Button Pressed"
    