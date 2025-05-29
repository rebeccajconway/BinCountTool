import pandas as pd
import streamlit as st
import math
from io import StringIO
import numpy as np

class MasterDataSets:
    """Class for creating and managing all datasets used in the warehouse simulation.
    Contains dataframes for SKUs, bins, and stacks that can be accessed and
    manipulated by other classes throughout the program."""

    sku_live_df = pd.DataFrame({
        'sku': pd.Series(dtype = str), # SKU identifier
        'qty_in_system': pd.Series(dtype = int), # Current quantity in the entire system
        'prio_bin': pd.Series(dtype = int),        # Priority bin location
        'full_bin_qty': pd.Series(dtype = int),    # Quantity that can fit in full bin - for full bin skus
        'full_system_qty': pd.Series(dtype = int), # Target quantity for the system
        'restock_qty': pd.Series(dtype = int) ,     # Quantity to restock sku
        'compartment_size': pd.Series(dtype = float) # 1, 0.5, 0.25, 0.125
    })
    
    # Bin contents dataframe (compartment level)
    bin_content_live_df = pd.DataFrame({
        'bin_id': pd.Series(dtype=int),             # Bin identifier
        'compartment_id': pd.Series(dtype = int),   # Compartment identifier within bin
        'compartment_size': pd.Series(dtype = float),# Total # compartments within the bin
        'sku': pd.Series(dtype = str),              # SKU stored in this compartment
        'priority': pd.Series(dtype=int),            # Priority level
        'qty_in_bin': pd.Series(dtype=int)          # Quantity in this specific compartment

    })
    
    # Bin capacity dataframe (bin level)
    bins_capacity_df = pd.DataFrame({
        'bin_id': pd.Series(dtype=int),                 # Bin identifier
        'compartment_size': pd.Series(dtype=float),     # Total compartments in bin
        'num_full_compartments': pd.Series(dtype=float) # Number of compartments currently in use
    })
    
    # Stack tracking dataframe
    stacks_lookup_df = pd.DataFrame({
    'stack_id': pd.Series(dtype=int),
    'bin_id': pd.Series(dtype=int)
    })
    


    @classmethod
    def create_bin_content_df(cls, bins_list):
        """Convert bins_list to a structured DataFrame.
        given: list of tuples in format: (bin_id, compartment_size, compartment_contents) 
            where compartment_contents = [sku, priority, qty_stored]
        returns a dataframe with columns: bin_id, compartment_id, compartment_size, sku, priority, qty_in_bin
        """
        # Create empty lists to store the data
        all_bin_ids = []
        all_compartment_ids = []
        all_compartment_sizes = []  # New list for compartment sizes
        all_skus = []
        all_priorities = []
        all_qty_in_bins = []
        
        #st.write(f"preview bins_list:{bins_list}") # Debug

        for bin_item in bins_list: # Loop through each bin in the bins_list
            bin_id = bin_item[0]
            compartment_size = bin_item[1]
            compartment_contents = bin_item[2]
            
            # Determine number of compartments based on size
            if compartment_size == 1:
                num_compartments = 1
            elif compartment_size == 0.5:
                num_compartments = 2
            elif compartment_size == 0.25:
                num_compartments = 4
            elif compartment_size == 0.125:
                num_compartments = 8
            else:
                raise ValueError(f"Invalid compartment size: {compartment_size}")
            
            # Process each compartment
            for i in range(num_compartments):
                # Check if there's content for this compartment
                if i < len(compartment_contents):
                    content = compartment_contents[i]
                    
                    # Extract data (sku, priority, qty_stored)
                    sku = content[0]
                    qty_stored = content[1]
                    priority = content[2]
                    
                    # Add to our lists
                    all_bin_ids.append(bin_id)
                    all_compartment_ids.append(i+1)  # Start compartment IDs at 1
                    all_compartment_sizes.append(compartment_size)  # Add compartment size
                    all_skus.append(sku)
                    all_priorities.append(priority)
                    all_qty_in_bins.append(qty_stored)
                else:
                    # Handle empty compartments if needed
                    all_bin_ids.append(bin_id)
                    all_compartment_ids.append(i+1)
                    all_compartment_sizes.append(compartment_size)  # Add compartment size
                    all_skus.append(None)
                    all_priorities.append(None)
                    all_qty_in_bins.append(0)
        
        # Create DataFrame from the lists
        cls.bin_content_live_df = pd.DataFrame({
            'bin_id': all_bin_ids,
            'compartment_id': all_compartment_ids,
            'compartment_size': all_compartment_sizes,  # Add to DataFrame
            'sku': all_skus,
            'priority': all_priorities,
            'qty_in_bin': all_qty_in_bins
        })
        
        return cls.bin_content_live_df 
    
    @classmethod
    def create_stack_lookup_df(cls, stack_contents):
        """creates a df to enable quick lookups of stack_id for a given bin_id"""
        
        bin_ids = [] # Create empty lists to hold the data
        stack_ids = [] # Create empty lists to hold the data

        for stack in stack_contents: # Iterate through each stack
            stack_id = stack[0]
            bins = stack[1]
            
            # Iterate through each bin in the stack
            for bin_id in bins:
                bin_ids.append(bin_id)
                stack_ids.append(stack_id)

        # Create the DataFrame
        cls.stacks_lookup_df = pd.DataFrame({
            'bin_id': bin_ids,
            'stack_id': stack_ids
        })

        # Set bin_id as index for quicker lookups
        cls.stacks_lookup_df.set_index('bin_id', inplace=True)

    @classmethod
    def init_priority_bins(cls):
        """Update prio_bin field in sku_live_df with the bin_id of priority 1 bins from bin_content_live_df"""
        
        # Filter bin_content_live_df to only include priority 1 entries with non-null SKUs
        priority_1_bins = cls.bin_content_live_df[
            (cls.bin_content_live_df['priority'] == 1) & 
            (cls.bin_content_live_df['sku'].notnull())
        ]
        
        # Group by SKU and get the first bin_id for each SKU (in case there are multiple priority 1 bins)
        priority_bins_by_sku = priority_1_bins.groupby('sku')['bin_id'].first().reset_index()
        
        # Update the prio_bin field in sku_live_df using the values from priority_bins_by_sku
        for _, row in priority_bins_by_sku.iterrows():
            sku = row['sku']
            bin_id = row['bin_id']
            # Update the prio_bin field for this SKU
            mask = cls.sku_live_df['sku'] == sku
            cls.sku_live_df.loc[mask, 'prio_bin'] = bin_id
            
        return cls.sku_live_df
    
    @classmethod
    def init_bins_capacity_df(cls):
        unique_bin_info = cls.bin_content_live_df[['bin_id', 'compartment_size']].drop_duplicates()
         # Create bins_capacity_df with the unique bin info
        cls.bins_capacity_df = unique_bin_info.copy()
        cls.bins_capacity_df['num_full_compartments'] = 0
        # Now calculate the number of full compartments for each bin_id
        # We need to count non-empty compartments (where sku is not None/NaN)
        bin_counts = cls.bin_content_live_df[cls.bin_content_live_df['sku'].notna()].groupby('bin_id').size()
        
        # Update the num_full_compartments column in bins_capacity_df
        for bin_id, count in bin_counts.items():
            bin_index = cls.bins_capacity_df['bin_id'] == bin_id
            if any(bin_index):
                cls.bins_capacity_df.loc[bin_index, 'num_full_compartments'] = count
                print(f"Updated bin {bin_id} with count {count}")
            else:
                print(f"Warning: Bin {bin_id} not found in bins_capacity_df")

    @classmethod
    def initialize_from_data(cls, bincountoutput, bins_list, inputs, stack_contents):
        """Initialize all dataframes from external data sources"""

        cls.create_bin_content_df(bins_list) #converts bin_list
        st.write(f"bin_content_live_df preview: ")
        st.table(cls.bin_content_live_df.head())

        cls.create_stack_lookup_df(stack_contents)
        st.table(cls.stacks_lookup_df.head())
        bincountoutput_df = pd.read_csv(StringIO(bincountoutput))
    
        needed_columns = ['SKU', 'Fit|No Fit', 'Qty Stored', 'Capped Bin Count', 'Bin Count', 'Final Compartment Size', 'Qty Per Bin', 'Min Qty Per Bin'] # Select necessary columns
        bincountoutput_df = bincountoutput_df[needed_columns]
        
        # Filter only "Fit" rows
        fit_rows = bincountoutput_df[bincountoutput_df['Fit|No Fit'] == "Fit"].copy()
        fit_rows['max_allowed_qty'] = fit_rows['Qty Per Bin'] * inputs['max_bins_per_sku']

        cls.sku_live_df = pd.DataFrame()
        
        # Add each column one by one
        cls.sku_live_df['sku'] = fit_rows['SKU']  
        cls.sku_live_df['prio_bin'] = [None] * len(fit_rows)  # Create a list of None values
        cls.sku_live_df['full_bin_qty'] = fit_rows['Qty Per Bin']
        cls.sku_live_df['full_system_qty'] = (np.maximum(
            fit_rows['Min Qty Per Bin'],
            np.minimum(fit_rows['Qty Stored'], fit_rows['max_allowed_qty'])
        ))
        cls.sku_live_df['qty_in_system'] = cls.sku_live_df['full_system_qty']
        fit_rows['restock_qty_percent'] = (cls.sku_live_df['full_system_qty'] * (inputs['restock_percent'])/100).apply(math.ceil)
        cls.sku_live_df['restock_qty'] = fit_rows['restock_qty_percent']
        cls.sku_live_df['compartment_size'] = fit_rows['Final Compartment Size'] # 1, 0.5, 0.25, 0.125
        
        cls.init_priority_bins()  # Adds priority bin_id to sku_live_df
        st.write(f"sku_live_df preview: ")
        st.table(cls.sku_live_df.head())

        cls.init_bins_capacity_df()
        st.write(f"bins_capacity preview:")
        st.table(cls.bins_capacity_df.head())
    


    
    # SKU methods
    @classmethod
    def get_sku_info(cls, sku):
        """Get all information for a specific SKU"""
        return cls.sku_live_df[cls.sku_live_df['sku'] == sku]
    
    @classmethod
    def update_sku_qty(cls, sku, qty_change):
        """Update quantity for a specific SKU in sku_live_df"""
        mask = cls.sku_live_df['sku'] == sku
        cls.sku_live_df.loc[mask, 'qty_in_system'] += qty_change
    
    # Bin methods
    @classmethod
    def get_bin_compartment_contents(cls, bin_id, target_sku):
        """Get all contents for a specific bin"""     
        return cls.bin_content_live_df[
            (cls.bin_content_live_df['bin_id'] == bin_id) &
            (cls.bin_content_live_df['sku'] == target_sku)
            ]
    
    @classmethod
    def get_bin_capacity(cls, bin_id):
        """Get capacity information for a specific bin"""
        return cls.bins_capacity_df[cls.bins_capacity_df['bin_id'] == bin_id]
    
    @classmethod
    def update_bin_qty(cls, bin_id, compartment_id, qty_change):
        """Update quantity in a specific bin compartment"""
        mask = (cls.bin_content_live_df['bin_id'] == bin_id) & \
               (cls.bin_content_live_df['compartment_id'] == compartment_id)
        cls.bin_content_live_df.loc[mask, 'qty_in_bin'] += qty_change
    
    # Stack methods
    @classmethod
    def get_stack_bins(cls, stack_id):
        """Get all bins in a specific stack"""
        return cls.stacks_live_df[cls.stacks_live_df['stack_id'] == stack_id]
    
    @classmethod
    def add_bin_to_stack(cls, stack_id, bin_id):
        """Add a bin to a stack"""
        new_row = {'stack_id': stack_id, 'bin_id': bin_id}
        cls.stacks_live_df.loc[len(cls.stacks_live_df)] = new_row

    @classmethod
    def get_stack_id(cls, bin_id):
        """Given a bin_id find the corresponding stack_id"""
        try:
            return cls.stacks_lookup_df.loc[bin_id]['stack_id']
        except KeyError:
            print(f"Warning!: Bin {bin_id} not found in stacks_lookup_df")
            return None
    
    @classmethod
    def mark_compartment_empty(cls, bin_id, compartment_id):
        """Mark given bin_id and compartment_id to empty
        set sku & priority to blank and qty to 0"""
        index = cls.bin_content_live_df.index[ # det index of particular entry of interest
            (cls.bin_content_live_df['bin_id'] == bin_id) & 
            (cls.bin_content_live_df['compartment_id'] == compartment_id)
        ]
        if len(index) == 0: return False
        
        cls.bin_content_live_df.at[index[0], 'sku'] = ''  # or None if preferred
        cls.bin_content_live_df.at[index[0], 'priority'] = ''  # or None if preferred  
        cls.bin_content_live_df.at[index[0], 'qty_in_bin'] = 0  # Set to 0, not None

        return True
    



