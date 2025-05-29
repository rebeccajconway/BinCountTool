import streamlit as st
import pandas as pd



def metric_format():

    st.markdown("""
    <style>
        /* Target metric labels specifically */
        [data-testid="stMetricLabel"] {
            overflow-wrap: break-word !important;
            word-break: break-all !important;
            white-space: normal !important;
            color: inherit;
            max-width: 100% !important;
        }
        
        /* Target the column containers to ensure they respect widths */
        [data-testid="column"] > div {
            width: 100% !important;
        }
        
        /* Target the metric container to ensure proper sizing */
        [data-testid="metric-container"] {
            width: 100% !important;
        }
    </style>
    """, unsafe_allow_html=True)

