#from main import bins_list, max_filled_bins


import streamlit as st
import numpy as np
import pandas as pd
import math
import random

from assign_bins import Bins


class Start_Stacks:
    def __init__(self, bins_list: list):
        self.stacks = []
        self.bins_list = bins_list
        self.stack_assignment = []

    def _run(self, max_filled_bins, bins_list)-> list[int, tuple]:
        """adds empty bins to the system then assigns bins to stacks"""

        bins_list_w_empties, bin_id = self._add_empty_bins(max_filled_bins, bins_list) # add empty bins to the system
        adj_avg_stack_height = (st.session_state.inputs['stack_height']-1)+(1-st.session_state.inputs['system_holes']/100) # determine bins per stack - some have less due to holes
        number_of_stacks = math.ceil(bin_id / adj_avg_stack_height)
        base_stack_contents : list= self._assign_stacks(bins_list_w_empties, number_of_stacks) #assign bins to each stack
        return base_stack_contents # return list of tuples - stack id, bin in each stack

    def _assign_stacks(self, bins_list_w_empties, number_of_stacks) -> tuple[int, list[str, int, int]]:
    
        for i in range(number_of_stacks): # Creating stack ids
            stack_id = i 
            self.stack_assignment.append((stack_id, []))

        # Create a randomized list of bin indices
        bin_indices = list(range(len(bins_list_w_empties)))
        random.shuffle(bin_indices)

        # Assign bins to stacks using the randomized indices
        for i, bin_index in enumerate(bin_indices):
            subject_bin = bins_list_w_empties[bin_index][0] # Extract the bin_id from the nested structure
            stack_index = i % number_of_stacks
            self.stack_assignment[stack_index][1].append(subject_bin)  # Append only the bin_id
            
        #for i in range(len(bins_list_w_empties)): # Filling stacks with bin_ids
        #    subject_bin = bins_list_w_empties[i][0] # Extract the bin_id from the nested structure
        #    stack_index = i % number_of_stacks
        #    self.stack_assignment[stack_index][1].append(subject_bin)  # Append only the bin_id
        st.write(self.stack_assignment) # Debugging 
        return self.stack_assignment
        
    #def _add_empty_bins(self, max_filled_bins, bins_list)->tuple[int, list[str, int, int]]:
    #    empty_bins = st.session_state.inputs["empty_bins"]
    #    empty_bin_count: int = math.ceil((empty_bins/100) * max_filled_bins)
    #    
    #    bin_id = max([bin[0] for bin in bins_list]) if bins_list else 0
    #    compartment_size = 0
    #    for i in range(1,empty_bin_count):
    #        bin_id += 1
    #        # new bin contents: (bin_id, [(sku, qty, priority)])
    #        self.bins_list.append((bin_id,compartment_size, []))
    #    return self.bins_list, bin_id

    def _add_empty_bins(self, max_filled_bins, bins_list) -> tuple[list, int]:
        empty_bins_percentage = st.session_state.inputs["empty_bins"]
        total_empty_bins = math.ceil((empty_bins_percentage/100) * max_filled_bins)
        
        # Get the highest bin_id currently in use
        bin_id = max([bin[0] for bin in bins_list]) if bins_list else 0
        
        # Count SKUs by compartment size
        sku_counts = {
            1: len(Bins.single_skus),     # Full bins (compartment size = 1)
            0.5: len(Bins.half_skus),     # Half bins (compartment size = 0.5)
            0.25: len(Bins.quarter_skus), # Quarter bins (compartment size = 0.25)
            0.125: len(Bins.eighth_skus)  # Eighth bins (compartment size = 0.125)
        }
        
        # Convert SKU counts to bin counts
        bin_counts = {
            1: sku_counts[1],           # Each single SKU uses a full bin
            0.5: sku_counts[0.5] / 2,   # Two half SKUs per bin
            0.25: sku_counts[0.25] / 4, # Four quarter SKUs per bin
            0.125: sku_counts[0.125] / 8 # Eight eighth SKUs per bin
        }
        
        # Calculate total number of bins
        total_bins = sum(bin_counts.values())
        
        # Calculate empty bins for each compartment size based on current distribution
        empty_bins_per_size = {}
        bins_allocated = 0
        
        for size, count in bin_counts.items():
            percentage = count / total_bins if total_bins > 0 else 0
            size_bin_count = math.floor(percentage * total_empty_bins)
            empty_bins_per_size[size] = size_bin_count
            bins_allocated += size_bin_count
        
        # Allocate any remaining bins to the most common compartment size
        if bins_allocated < total_empty_bins:
            remaining = total_empty_bins - bins_allocated
            most_common_size = max(bin_counts, key=bin_counts.get)
            empty_bins_per_size[most_common_size] += remaining
        
        # Create the empty bins with appropriate compartment sizes
        for size, count in empty_bins_per_size.items():
            for _ in range(math.ceil(count)):
                bin_id += 1
                # new bin contents: (bin_id, compartment_size, [])
                self.bins_list.append((bin_id, size, []))
        
        return self.bins_list, bin_id

            
