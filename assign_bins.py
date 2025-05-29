from bincountcalc import BinCountCalculator # can I delete this line?

import streamlit as st
import pandas as pd
import numpy as np

class Bins:
    """ Class used for calculating bin ids for each sku"""
    bin_contents = []
    single_skus = []; """skus that require a full bin"""
    half_skus = []; """skus that require a half bin"""
    quarter_skus = []; """skus that require a quarter bin"""
    eighth_skus = []; """skus that require a eighth bin"""

    

    def __init__(self):
       #Bins.bin_contents = []
       #Bins.singles = []
       self.assigned_bins = []
       #Bins.half_bins = []
       #Bins.quarter_bins = []
       #Bins.eighth_bins = []
       self.bin_id = 1; """ initializine bin_id as an instance attribute"""
       self.half_bin_contents = []; """tracks skus going into each bin for skus that take half a bin"""
       self.quarter_bin_contents = []; """tracks skus going into each bin for skus that take quarter a bin"""
       self.eighth_bin_contents = []; """tracks skus going into each bin for skus that take eighth a bin"""

    def _run(self, bincount_skus)-> tuple[list, int]:
        """Filters through all skus and assigns them to bins - either multiple full bins or joins skus that need compartments"""
        for i in range (0, len(bincount_skus)): # filters through each sku 
            sku = bincount_skus['SKU'][i]
            capped_bin_count = bincount_skus['Capped Bin Count'][i]
            # Following three lines acts to set the minimum qty stored to the min qty per bin
            qty_stored_given = bincount_skus['Qty Stored'][i]
            min_qty_per_bin = bincount_skus['Min Qty Per Bin'][i]
            qty_stored = max(qty_stored_given, min_qty_per_bin)

            max_qty_per_bin = bincount_skus['Qty Per Bin'][i]
            priority = 1
            
            if capped_bin_count >= 1: # sku requires a full bin
                Bins.single_skus.append((sku, capped_bin_count, qty_stored, max_qty_per_bin))
                self.bin_id = self._add_single(sku, capped_bin_count, qty_stored, max_qty_per_bin)
            elif capped_bin_count == 0.5: # requires a compartment
                Bins.half_skus.append((sku, qty_stored, priority))
            elif capped_bin_count == 0.25: # requires a compartment
                Bins.quarter_skus.append((sku, qty_stored, priority))
            elif capped_bin_count == 0.125: # requires a compartment
                Bins.eighth_skus.append((sku, qty_stored, priority))   
            else: 
                pass

        for i in range (0,len(Bins.half_skus), 2):
            chunk = Bins.half_skus[i:i+2] # ending index is excluded
            self.half_bin_contents = []
            for sku_tuple in chunk:
                self.half_bin_contents.append(sku_tuple)
            self.bin_id = self._add_compartment_bins(self.half_bin_contents, 0.5)
        for i in range (0,len(Bins.quarter_skus), 4):
            chunk = Bins.quarter_skus[i:i+4] # ending index is excluded
            self.quarter_bin_contents = []
            for sku_tuple in chunk:
                self.quarter_bin_contents.append(sku_tuple)
            self.bin_id = self._add_compartment_bins(self.quarter_bin_contents, 0.25)
        for i in range (0,len(Bins.eighth_skus), 8):
            chunk = Bins.eighth_skus[i:i+8] # ending index is excluded
            self.eighth_bin_contents = []
            for sku_tuple in chunk:
                self.eighth_bin_contents.append(sku_tuple)
            self.bin_id = self._add_compartment_bins(self.eighth_bin_contents, 0.125)

        self.assigned_bins = [bin_entry for bin_entry in self.assigned_bins if len(bin_entry) == 3] # Clean up any malformed entries

        max_filled_bins =self.bin_id
        bins_list = self.assigned_bins
        return bins_list, max_filled_bins

    def _add_single(self, sku, capped_bin_count, qty_stored, max_qty_per_bin)-> int:
        """ Fills a bin with a single sku and fills the appropriate # of bins based on the capped bin count"""
        remaining_bin_count = capped_bin_count
        priority: int = 1 #resetting the priority value for the sku
        compartment_size =  1
        while remaining_bin_count > 1:
            if qty_stored > max_qty_per_bin: # remaining qty to store
                storage = max_qty_per_bin
            else:
                storage = qty_stored
            new_bin = (self.bin_id, compartment_size, [(sku, int(storage), priority)])
            self.assigned_bins.append(new_bin)
            remaining_bin_count -= 1
            self.bin_id += 1
            qty_stored -= max_qty_per_bin
            priority += 1
        new_bin = (self.bin_id, compartment_size, [(sku, int(qty_stored), priority)])
        self.assigned_bins.append(new_bin)
        self. bin_id += 1
        return self.bin_id

    def _add_compartment_bins(self, subject_compartment_list, compartment_size)-> int:
        
        priority = 1 # only one location for compartments at beginning - so all priority 1
        compartment_contents = []

        if not subject_compartment_list:
            return self.bin_id

        for i in range(len(subject_compartment_list)):
            sku, qty_stored, priority = subject_compartment_list[i]
            compartment_contents.append([sku, int(qty_stored), priority])

        if compartment_contents:
            self.assigned_bins.append([self.bin_id, compartment_size, compartment_contents])
            self.bin_id += 1

        return self.bin_id  # returns the next bin to be assigned

    def get_sku_bins(self):
        return self.assigned_bins
    

       
       