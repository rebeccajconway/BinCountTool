import streamlit as st
import pandas as pd
import time
import datetime
import matplotlib.pyplot as plt
import io

from assign_bins import Bins
from bincountcalc import BinCountCalculator
from components import download_button, select_file, HelpTexts, uf_to_df, stop_button
from assign_stacks import Start_Stacks
from simulation import Sim
from datasets import MasterDataSets
from clean_data import CleanData
from help import help_sidebar
from utils import init_session_states


st.set_page_config(
        page_title="Bin Count Tool and Simulation"
        )

help_sidebar()
init_session_states()

st.header("Calculations Page")
st.write("This is the page where you will configure the tool, run the calculations and see the summarized results and download files.") 

st.header("Configuration Your Run")
st.write("This is the page where the run can be personalized and edited")

st.subheader("Toggle on/off runs you wish to perform", help=HelpTexts.run_selection)
st.toggle("Run Bin Digging Simulation", key="dig_sim_toggle", value=True)
st.session_state['induction_toggle'] = True # Always True - Scenario where we wouldn't want this?
st.subheader("Bin Count Tool Inputs")
sku_file_label, sku_file = select_file(HelpTexts.sku_master, ["csv"], "Upload SKU Master File (.csv):")

st.subheader("Input Parameters")
st.selectbox("Bin Type:", [220, 330, 425], index=1, key="bin_type")
st.selectbox("Max Bin Utilization (%):", list(range(50, 105, 5)), index=4, help=HelpTexts.bin_utilization, key="bin_utilization")
st.selectbox("Max Compartments:", [1, 2, 4, 8], index=3, help=HelpTexts.max_compartments, key="max_compartments")
st.number_input("Max Bin Weight (kg)", min_value=0, value=25, help=HelpTexts.max_weight, key="bin_weight_limit")
st.number_input("Max Bins per SKU", min_value=1, value=20, help=HelpTexts.max_bins_per_sku, key="max_bins_per_sku")

if st.session_state['dig_sim_toggle'] is True:
    st.subheader("Bin Distribution Simulation Inputs")
    sim_file_label, outbound_uf = select_file(HelpTexts.outbound, ["csv"], "Upload outbound data")
    st.session_state['outbound_uf'] = outbound_uf
    
    st.subheader("Input Parameters")
    st.number_input("Stack Height",min_value=4,max_value=26, value = 18, key="stack_height")
    st.number_input("Percent Empty Bins", min_value=5, value=15, help=HelpTexts.percent_empty, key="empty_bins")
    st.number_input("Percent Holes in System", min_value=10, value=50, key="system_holes")

    if st.session_state["induction_toggle"]: #alwyas true for now
        st.number_input("Restock percent", min_value = 0, max_value= 95, value=20, help=HelpTexts.restock_percent, key="restock_percent") 

st.subheader("Delimiters and Separators")
st.text_input("Delimiter:", value=",", key= "sku_delimiter")
st.text_input("Decimal Separator:", value=".", key="sku_decimal")
st.text_input("Thousands Separator:", value="", key="sku_thousands")
st.selectbox("Dimension Units:", ["mm / kg", "in / lb"], index=1, key="sku_units")

st.subheader("Output Settings")
st.text_input("Output File Name:", value="data_tool_output", key="output_name")
            
with st.sidebar:
    with st.expander(label = ":pencil: Rename Columns"):
        sku_cols = {
            "SKU": st.text_input("SKU Column Name:", value="SKU"),
            "Length": st.text_input("Length Column Name:", value="Length"),
            "Width": st.text_input("Width Column Name:", value="Width"),
            "Height": st.text_input("Height Column Name:", value="Height"),
            "Weight": st.text_input("Weight Column Name:", value="Weight"),
            "Min Qty Per Bin": st.text_input("Min Qty Per Bin Column Name:", value="Min Qty Per Bin"),
            "Qty Stored": st.text_input("Qty Stored Column Name:", value="Qty Stored"),
        }

can_run = False
if sku_file is not None:
    if st.session_state["dig_sim_toggle"] is True and st.session_state['outbound_uf'] is not None:
        can_run = True
        print(f"dig sim toggle result (Config tab): {st.session_state['dig_sim_toggle']}")
    elif st.session_state["dig_sim_toggle"] is False:
        can_run = True
        print(f"dig sim toggle result (Config tab): {st.session_state['dig_sim_toggle']}")

st.session_state["can_run"] = can_run # stores run eligibility status in session state

inputs ={
            "bin_type": st.session_state['bin_type'],
            "bin_utilization": st.session_state['bin_utilization'],
            "max_compartments": st.session_state['max_compartments'],
            "bin_weight_limit": st.session_state['bin_weight_limit'],
            "max_bins_per_sku": st.session_state['max_bins_per_sku'],
            "sku_file": sku_file,
            "sku_delimiter": st.session_state['sku_delimiter'],
            "sku_decimal": st.session_state['sku_decimal'],
            "sku_thousands": st.session_state.get('sku_thousands'),
            "sku_units": st.session_state['sku_units'],
            "output_name": st.session_state['output_name'],
            "output_folder": None,
            "sku_cols": sku_cols,
        } 

if st.session_state['dig_sim_toggle'] == True:
    inputs.update({
        "outbound_uf": st.session_state.get('outbound_uf'),
        "stack_height": st.session_state['stack_height'],
        "empty_bins": st.session_state['empty_bins'],
        "system_holes": st.session_state['system_holes'],
        "restock_percent" : st.session_state['restock_percent']
    })

st.session_state['inputs'] = inputs

######################################################################################################

st.header("Run")

# checks that required data files have been uploaded
if "can_run" not in st.session_state or not st.session_state["can_run"]:
    st.write("When all required data has been input, Calculation button will appear below")
    st.warning("Please complete the configuration first and upload required files.")
    if st.button(label="help"):
        st.info("""
            Common issues: 
            1. SKU Master Data is required to run the program. 
            2. Outbound Data is not required, but Bin Distribution Simulation must be toggled to off if the CSV is not uploaded. 
            3. Make sure a .csv file has been uploaded (an excel workbook will not work)
            4. make sure the delimeter matches the delimiter in your file
            """)
    st.header("Results")
    st.stop()

if st.button(label="Calculate"):
    st.session_state['Calculate'] = True
    
    st.session_state['start_time'] = time.time()
    with st.spinner("Tool is running...", show_time= True):

        bincount = BinCountCalculator(st.session_state['inputs'], to_folder=False)
        
        if bincount.errors:
            st.error("Errors during initialization.")
            for error in bincount.errors:
                st.write(f"-{error}")
        else:
            bincount_output_df = bincount.calculate_bin_count()
            st.session_state['bincount_output_df'] = bincount_output_df # immediately save to session_state
            st.session_state['bincount.output'] = bincount.output
            if bincount.errors:
                st.error("Errors during bin count calculation: ")
                for error in bincount.errors:
                    st.write(f"-{error}")
            else:
                if st.session_state['dig_sim_toggle'] is True:
                    
                    # Set up Bins
                    outbound_df = uf_to_df(outbound_uf)
                    bins_instance = Bins()
                    bins_list, max_filled_bins = bins_instance._run(bincount_output_df)
                    st.session_state['bins_list_init'] = bins_list

                    # Set up Stacks
                    stack_instance = Start_Stacks(bins_list)
                    stack_contents = stack_instance._run(max_filled_bins, bins_list) # list stack_id with bin_id in each stack
                    
                    bincountoutput = bincount.output
                    
                    MasterDataSets.initialize_from_data(bincountoutput, bins_list, inputs, stack_contents)

                    if outbound_df is None:
                        st.error("outbound_uf is None!")
                    if outbound_df is not None:
                        prep_instance = CleanData()
                        prepped_outbound_df = prep_instance._prep_outbound(outbound_df) # num_incomplete_outbound tracks rows missing either sku, timestamp or qty
                        pick_orders = prepped_outbound_df # can use consistent variable names throughout and remove this
                       
                    elif outbound_df is None:
                        print("No Outbound CSV file detected or it is read improperly")

                    if pick_orders is not None:
                        st.session_state['enable_stop'] = True # now safe to enable the user to stop the simulation
                        
                        simulated_instance = Sim(bins_list, pick_orders, stack_contents, bincount_output_df) # creates a class instance
                        simulation_results, simulation_results_df = simulated_instance._run()
                        print("Successfully left simulation run file")
                        st.session_state['simulation_results'] = simulation_results
                        st.session_state['simulation_results_csv']=simulation_results
                        st.session_state['simulation_results_df']=simulation_results_df
                    
                    else:
                        st.warning("Please upload a valid outbound csv file") # this should already be checked previously
                elif st.session_state['stop_run'] is True:
                        simulation_results = st.session_state['pick_orders_output_csv']
                        simulation_results_df = st.session_state['pick_orders_df']
                else:
                    print("error in calculations for simulation")
            
            st.session_state["results_ready"] = True 
            elapsed_time = time.time() - st.session_state['start_time']
            formatted_time_elapsed = str(datetime.timedelta(seconds=int(elapsed_time)))
            st.session_state['formatted_time_elapsed'] = formatted_time_elapsed
            st.write(f"total run time: {st.session_state['formatted_time_elapsed']}")
            st.success("Run complete! See results below")

if st.session_state['stop_button'] is True:
   st.session_state['stop_run'] = True

if st.session_state['stop_run'] is True:
    st.warning(f"Stopping Run...")
    # checks the data storage type of pick_orders_df
    if not isinstance(st.session_state['pick_orders_df'], pd.DataFrame):
        # If it's a list, convert it to DataFrame
        if isinstance(st.session_state['pick_orders_df'], list):
            st.session_state['pick_orders_df'] = pd.DataFrame(st.session_state['pick_orders_df'])
        # If it's a string (the CSV), convert it back to DataFrame
        elif isinstance(st.session_state['pick_orders_df'], str):
            st.session_state['pick_orders_df'] = pd.read_csv(io.StringIO(st.session_state['pick_orders_df']))
    
    simulation_results_df = st.session_state['pick_orders_df']
    simulation_results = st.session_state['pick_orders_output_csv']

    st.session_state['simulation_results'] = simulation_results
    st.session_state['simulation_results_csv']= simulation_results
    st.session_state['simulation_results_df']= simulation_results_df 
    
    st.session_state["results_ready"] = True 
    elapsed_time = time.time() - st.session_state['start_time']
    formatted_time_elapsed = str(datetime.timedelta(seconds=int(elapsed_time)))
    st.session_state['formatted_time_elapsed'] = formatted_time_elapsed
    st.write(f"total run time: {st.session_state['formatted_time_elapsed']}")
    st.success("Run complete! See results below")

######################################################################################################


st.header("Results")
st.write("Use the Results to get a high level overview, sanity check values, and download the raw data")

if "results_ready" not in st.session_state or st.session_state["results_ready"] is False:
    st.warning("A simulation needs to be ran prior to seeing the results")
    st.stop()

elif st.session_state["results_ready"] is True:

    st.write(f"total run time: {st.session_state['formatted_time_elapsed']}")
    if st.session_state['stop_run']:
        st.write(f"Reason for stopping: {st.session_state['stop_reason']}")
            
    simulation_results_df = st.session_state['simulation_results_df']
    simulation_results = st.session_state['simulation_results']


    tab1, tab2, tab3, tab4, tab5 = st.tabs(['Summary', 'Simulation Results', 'Sanity Check', 'File Download', 'Debugging'])


    with tab1:
        st.subheader("Summary Statistics")

        bincount_df = pd.read_csv(io.StringIO(st.session_state['bincount.output']))
        total_bins_capped = bincount_df['Capped Bin Count'].sum() if 'Capped Bin Count' in bincount_df.columns else 0
        
        fit_count = bincount_df[bincount_df['Fit|No Fit'] == 'Fit'].shape[0] if 'Fit|No Fit' in bincount_df.columns else 0
        no_fit_count= bincount_df[bincount_df['Fit|No Fit'] == 'No Fit'].shape[0] if 'Fit|No Fit' in bincount_df.columns else 0
        no_dims_count= bincount_df[bincount_df['Fit|No Fit'] == 'No Dims'].shape[0] if 'Fit|No Fit' in bincount_df.columns else 0
        percent_fit = (fit_count)/(fit_count+no_fit_count+no_dims_count)
        percent_fit_formatted = f"{percent_fit:.1%}"
            
        if total_bins_capped is not None:
            col1, col2, col3 = st.columns(3)
            col1.metric(label = "Total Capped #  Bins", value = total_bins_capped)
            col2.metric(label = '# SKUs that Fit', value=fit_count)
            col3.metric(label = '% SKUs that Fit', value=percent_fit_formatted)

            # Fit|No Fit Pic Chart
            labels = ['Fit', 'No Fit', 'No Dimensions']
            sizes = [fit_count, no_fit_count, no_dims_count]
            colors = ["#8abbeb", '#ff9999', "#a9e0a9"]
            explode = (0.1, 0, 0)  # explode first slice
            col6, col7 = st.columns([1,1])
            with col6:
                fig, ax = plt.subplots(figsize=(4, 4))
                ax.pie(sizes, explode=explode, labels=labels, colors=colors,
                autopct='%1.1f%%', shadow=False, startangle=90)
                ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
                st.pyplot(fig)       

            with col7:
                summary_bins_values = {
                    'Status': ['Fits', 'Does Not Fit', 'No Dimensions'],
                    'Count': [fit_count, no_fit_count, no_dims_count]
                }
                summary_df = pd.DataFrame(summary_bins_values)
                st.table(summary_df.set_index('Status'))
        else: 
            st.error("error retrieving data")
        
        if st.session_state['dig_sim_toggle'] is True:
            st.subheader("Simulation Summary")
            num_lines_analyzed = st.session_state['count_line_fits']+st.session_state['count_line_no_fits']+st.session_state['count_lines_excluded']+st.session_state['count_insufficient_qty']
            pct_lines_through_AS = (st.session_state['count_line_fits'] / num_lines_analyzed)*100
            pct_lines_no_fit = (st.session_state['count_line_no_fits'] / num_lines_analyzed)*100
            pct_lines_excluded = (st.session_state['count_lines_excluded'] / num_lines_analyzed)*100
            pct_lines_insufficient_qty = (st.session_state['count_insufficient_qty'] / num_lines_analyzed)*100
            pct_lines_ran = (num_lines_analyzed / st.session_state['count_total_input_lines'])* 100

            if st.session_state['stop_run']: st.metric(label = "Percent of Total Lines Analyzed:", value=f"{pct_lines_ran:.1f}%")

            summary_bins_values = {
                'Status': ['Lines Through AS', "Lines Don't Fit", 'Lines Excluded', 'Insufficient Qty'],
                'Count': [st.session_state['count_line_fits'], st.session_state['count_line_no_fits'], st.session_state['count_lines_excluded'], st.session_state['count_insufficient_qty']],
                'Percent': [f"{pct_lines_through_AS:.1f}%", f"{pct_lines_no_fit:.1f}%", f"{pct_lines_excluded:.1f}%", f"{pct_lines_insufficient_qty:.1f}%"]
            }
            summary_df = pd.DataFrame(summary_bins_values)
            st.table(summary_df.set_index('Status'))

            col1c, col2c = st.columns(2)
            col1c.metric(label="Total Rows of Outbound Data", value = st.session_state['count_total_input_lines'] )

    with tab2:
        st.subheader("Bin Distribution Simulation Results")
        # Graph of Bin Distribution over days
        if st.session_state['dig_sim_toggle'] is True:
            col1, col2 = st.columns(2)
            col1.metric(label = "Number of Incomplete Rows in Outbound Data", value = st.session_state['number_incomplete_outbound'])
            col2.metric(label="# of Complete Rows in Outbound Data", value = st.session_state['number_complete_outbound'])
            
            simulation_results_df = simulation_results_df.copy()
            simulation_results_df['date'] = simulation_results_df['timestamp'].dt.date # Extract date from timestamp

            col1a, col2a = st.columns(2)
            with col1a:
                pick_orders_df = st.session_state['pick_orders_df'] #pd.DataFrame(st.session_state['pick_orders_df'])

                pick_orders_df = pick_orders_df.copy()
                pick_orders_df['date'] = pick_orders_df['timestamp'].dt.date

                pick_orders_df_filtered = pick_orders_df.dropna(subset=['bins_above'])

                timestamp_depth_pivot = pd.pivot_table(
                    data = pick_orders_df_filtered, 
                    values = "bins_above", 
                    index = "date", 
                    columns = None, 
                    aggfunc = "mean"
                    )
                
                # Create a second pivot table to count the number of picks per day
                count_pivot = pd.pivot_table(
                    data=pick_orders_df,
                    values="bins_above",  # You can use any column here
                    index="date",
                    aggfunc="count"
                )

                # Rename the column for clarity
                count_pivot.columns = ["num_picks"]

                # Merge the two pivot tables
                combined_pivot = pd.concat([timestamp_depth_pivot, count_pivot], axis=1)

                # rename the bins_above column for clarity
                combined_pivot.rename(columns={"bins_above": "avg_bins_above"}, inplace=True)

                # Display the combined pivot table
                st.dataframe(combined_pivot)

            with col2a:
                fig, ax = plt.subplots(figsize=(10, 6))

                # Plot the data
                timestamp_depth_pivot.plot(
                    kind='line',
                    marker='o',
                    ax=ax
                )

                # Customize the plot
                plt.title('Average Bins Above by Date')
                plt.xlabel('Date')
                plt.ylabel('Average Bins Above')
                plt.grid(True, linestyle='--', alpha=0.7)
                plt.xticks(rotation=45)
                plt.tight_layout()

                # Display the plot in Streamlit
                st.pyplot(fig)

            col1b, col2b = st.columns(2)
            with col1b:
                st.write("data")
                available_dates = ["All Dates"] + sorted(simulation_results_df['date'].unique().tolist())

                selected_date = st.selectbox(
                    "Select Date:",
                    options=available_dates,
                    index=0  # Default to "All Dates"
                    )
            
            with col2b:
                display_type = st.radio(
                    "Display Values As:",
                    options=["Percentage", "Count"],
                    index=0  # Default to Percentage
                )

            if selected_date == "All Dates":
                filtered_df = simulation_results_df
            else:
                filtered_df = simulation_results_df[simulation_results_df['date'] == selected_date]

            pivot = pd.pivot_table(
                data=filtered_df,
                values="timestamp",
                index="bins_above",
                columns="date",
                aggfunc="count"
            )

            if display_type == "Percentage":
                display_pivot = pivot.div(pivot.sum(axis=0), axis=1) * 100
            else:
                display_pivot = pivot

            st.dataframe(display_pivot)
            
    with tab3:
        st.subheader("Sanity Check")
        st.subheader("SKU Data: ")
        st.write("Sanity Check to make sure the units used in this analysis make sense")
        st.write(f"Units used {st.session_state['sku_units']}")

        if st.session_state['sku_units'] == "mm / kg":
            weight_units = "kg"
            length_units = "mm"
            max_weight = st.session_state['bincount_output_df']['Weight (kg)'].max()
            median_weight = st.session_state['bincount_output_df']['Weight (kg)'].median()
            max_length = st.session_state['bincount_output_df']['Length (mm)'].max()
            median_length = st.session_state['bincount_output_df']['Length (mm)'].median()
            max_width = st.session_state['bincount_output_df']['Width (mm)'].max()
            median_width = st.session_state['bincount_output_df']['Width (mm)'].median()
            max_height = st.session_state['bincount_output_df']['Height (mm)'].max()
            median_height = st.session_state['bincount_output_df']['Height (mm)'].median()
        else:
            weight_units = "lb"
            length_units = "in"
            max_weight = st.session_state['bincount_output_df']['Weight (lb)'].max()
            median_weight = st.session_state['bincount_output_df']['Weight (lb)'].median()
            max_length = st.session_state['bincount_output_df']['Length (in)'].max()
            median_length = st.session_state['bincount_output_df']['Length (in)'].median()
            max_width = st.session_state['bincount_output_df']['Width (in)'].max()
            median_width = st.session_state['bincount_output_df']['Width (in)'].median()
            max_height = st.session_state['bincount_output_df']['Height (in)'].max()
            median_height = st.session_state['bincount_output_df']['Height (in)'].median()
        
        col1, col2 = st.columns(2)
        st.write("Weight: ")
        with col1: st.metric(label="Max", value = f"{max_weight:.2f} {weight_units}")
        with col2: st.metric(label="Median", value = f"{median_weight:.2f} {weight_units}")

        col1, col2 = st.columns(2)
        st.write("Length: ")
        with col1: st.metric(label="Max", value = f"{max_length:.2f} {length_units}")
        with col2: st.metric(label="Median", value = f"{median_length:.2f} {length_units}")

        col1, col2 = st.columns(2)
        st.write("Width: ")
        with col1: st.metric(label="Max", value = f"{max_width:.2f} {length_units}")
        with col2: st.metric(label="Median", value = f"{median_width:.2f} {length_units}")

        col1, col2 = st.columns(2)
        st.write("Height: ")
        with col1: st.metric(label="Max", value = f"{max_height:.2f} {length_units}")
        with col2: st.metric(label="Median", value = f"{median_height:.2f} {length_units}")

    with tab4:
        st.subheader("Downloadable Files")

        download_button(st.session_state['bincount.output'], "bincounttool_output", "Download SKUs CSV File") 
        
    with tab5:
        st.subheader("Debug Files")

        if st.session_state["dig_sim_toggle"]:
            download_button(simulation_results, "simulation_results", "Download simulation results")

            st.session_state['bin_content_live_csv'] = MasterDataSets.bin_content_live_df.to_csv(index=False)
            download_button(st.session_state['bin_content_live_csv'], "bin_content_live", "bin_content_live")
            
            st.session_state['bins_capacity_df_csv'] = MasterDataSets.bins_capacity_df.to_csv(index = False)
            download_button(st.session_state['bins_capacity_df_csv'], "bins_capacity_df", "bins_capacity_df")

            st.session_state['sku_live_df_csv'] = MasterDataSets.sku_live_df.to_csv(index = False)
            download_button(st.session_state['sku_live_df_csv'], "sku_live_df_csv", "sku_live_df_csv")
            
st.write("refresh this page to start a new run - results will not be saved")



