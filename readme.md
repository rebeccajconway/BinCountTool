# README for Bin Count Tool

## Overview
The Bin Count Tool is a Python-based application designed to calculate the optimal number of Bins required to store customer SKUs (items) based on their dimensions, weight, qty and other user-defined parameters. The Bin Count Tool is now integrating Bin Distribution Simulation capabilities. This will emulate bin picking and replinishment based on the skus added to the system with the initial Bin Count Tool file.

## Getting started
To get started the packages in requirements.txt must be installed. This can be done by running the following command in the terminal:
```bash
pip install -r requirements.txt
```
There are also UI options in VS Code.

To run the program submit the following command in the terminal:
```bash
streamlit run main.py
```

A local streamlit server is now started on your PC and a browser window opens with the UI of the tool. Refer to the streamlit documentation for more information.

## Features
Calculates the maximum quantity of items (SKUs) that can fit into different bin configurations.
Supports both metric (mm/kg) and imperial (in/lb) units.
Handles various bin types and compartment setups.
Provides error handling for invalid inputs or data inconsistencies.
Outputs results in an CSV format.

Assigns skus to bins based on the resultant bin count from initial calculations
emulates picking a bin from a stack - returns the depth of the bin when it is picked then replaces it on top
monitors # units in the system and triggers a restock to the initial quantity when restock level is reached
restock level is based as a user input % from the initial values

## File Descriptions
bincountcalc.py

This file contains the core logic for bin count calculations, including:

qty_per_compartment function: A vectorizable function that computes the maximum number of items that can fit in a bin based on dimensions, weight, and utilization.
BinCountCalculator class: Handles the overall process of importing SKU data, validating inputs, performing calculations, and exporting results.
Uses minimal number of compartments needed to fulfill the quantity of SKUs needed to be stored. User defined parameters such as weight limits, utilization, minimum number of items per box, weight limit, and number of compartments are used in calculations.


main.py
This file serves as the front-end interface using Streamlit, allowing users to:

Key Components:
File Upload: Accepts SKU master files in .csv format.
Input Parameters: Collects bin type, utilization percentage, compartments and weight limit.
Delimiters and Units: Allows customization of data separators and unit types.
Output Settings: Defines the output file name and format.
SKU Columns: Maps required columns in the SKU file to user-defined names.
Calculate Button: Initiates the calculations and provides feedback on errors or results.

simulation.py
contains core logic for simulating bin picking based on given order data, including:

_run function: 
_pick function: adds columns to the pick order data such as bin_id, bins_above, stack and bin_priority. updates qty in bin after pick and pops bin to the top of the stack
_get_bins function: finds the first priority bin to pick from for the target sku
_get_depth function: function determines the depth of the sku in the stack at the time it is called
_pop_bins function: pops target bin_id to the top of the stack
_reassign_priorities: re-assigns the priorities of the sku locations (called if prio 1 bin is fully picked)
_update_qty function: updates qty of sku in the bin_list
_mark_empty function: updates bin_list by marking the priority 0 bins to empty
_check_refill function: checks if there are enough items ready to restock a bin (if sku qty is 0 in system or if there are enough skus to fill all compartments)
_trigger_restock function: restocks the bin to the original value
_get_last_priority function: gets the lowest priority # for a sku - used to add new bins to the lowest priority
_new_bin_qty function: returns qty to restock
_find_empty_bin function
_overwrite_bin
_get_max_qty_per_bin



assign_bins.py



assign_stacks.py


components.py


inbound_data.py


outbound_orders.py




## Test file path
Test files available in system design folder - Anybody from SD can grant access
OneDrive - AUTOSTORE AS\Shared Documents - System Design\System Design & Sales Tools\Bin Count Tool\data

## Known Bugs / Issues
qty can go negative in the system


