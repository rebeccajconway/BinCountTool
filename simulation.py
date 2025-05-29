import streamlit as st
import pandas as pd
import logging
import os
from datetime import datetime
import time
import io
import math

from components import setup_logger
from datasets import MasterDataSets


class Sim:
    def __init__(self, bins_list, pick_orders, stack_contents, bincount_output):

        if isinstance(pick_orders, pd.DataFrame):
            self.pick_orders = pick_orders
        else:
            raise ValueError("pick_orders must be a pandas DataFrame")
        # initializing lists and dataframes for remainder of class
        self.stack_contents = stack_contents # includes stack_id and bin_id  
        self.pick_orders['bin_id'] = pd.NA
        self.pick_orders_lines_in_as = []
        self.non_fit_pick_orders =[] # contains orders of skus that are not in the AutoStore - these will be excluded from output pick_orders and bin distribution
        self.excluded_pick_orders = [] # picks where sku was not given in sku data thus it is excluded
        self.insufficient_qty_pick_order = [] # picks where the sku qty in the system was insufficient to complete the pick
        self.bincount_output_df = pd.DataFrame(bincount_output)
        self.bins_per_line = 1
        self.track_insufficient_picks = 0
        #self.bins_list = bins_list

        self.logger = setup_logger()

    def _run(self): # csv data output
        """Filters through outbound orders that fit in the AutoStore and updates the stock in the system after a pick"""
        
        sim_progress_bar = st.progress(0, text = "simulation progress ... ") # Progress Bar to load how it is being simulated
        self.num_rows = len(self.pick_orders)
        self.logger.info(f"Processing {self.num_rows} orders")

        st.button(label="stop and save", key="stop_button")
        
        for i, row in self.pick_orders.iterrows(): # loop through order / outbound data: 
            
            if i % st.session_state['save_interval'] == 0 and i is not 0: # Periodically save data to session_state incase simulation is stopped
                self.pick_orders_lines_in_as = self.pick_orders[self.pick_orders['bin_id'].notna()]
                self.pick_orders_output_csv = self.pick_orders_lines_in_as.to_csv(index = False)
                st.session_state['pick_orders_df'] = self.pick_orders_lines_in_as
                st.session_state['pick_orders_output_csv'] = self.pick_orders_output_csv  
                st.session_state['count_insufficient_picks'] = self.track_insufficient_picks # integer
                count_line_no_fits = len(self.non_fit_pick_orders)
                count_line_fits = len(self.pick_orders_lines_in_as)
                count_lines_excluded = len(self.excluded_pick_orders)
                count_insufficient_qty = len(self.insufficient_qty_pick_order)
                st.session_state['count_line_fits'] = count_line_fits
                st.session_state['count_line_no_fits'] = count_line_no_fits
                st.session_state['count_lines_excluded'] = count_lines_excluded
                st.session_state['count_insufficient_qty'] = count_insufficient_qty
                st.session_state['count_total_input_lines'] = self.num_rows
                print("session state saved")

            check_restock: bool = False

            target_sku: str = row['sku']
            timestamp = row['timestamp']
            qty_needed: int = row['qty']

            order_start_time = time.time()
            self.logger.debug(f"Processing order {i+1}/{self.num_rows}: SKU={target_sku}, Qty={qty_needed}")
            sim_progress_bar.progress(((i+1)/self.num_rows), text=f"simulation progress ({i+1}/{self.num_rows})... ") # Progress Bar loading

            fit_status = self.check_sku_fit_status(target_sku)

            if fit_status == "Fit" or fit_status == "fit": # makes sure requested sku is one that is in the AutoStore system:   
                
                # 1. Do we have sufficient skus in system to fulfil the order?
                sku_info = MasterDataSets.get_sku_info(target_sku)
                full_system_qty = sku_info['full_system_qty'].values[0] # if not sku_info.empty else None
                prio_bin = sku_info['prio_bin'].values[0]
                 
                bin_info = MasterDataSets.get_bin_compartment_contents(prio_bin, target_sku)
                if prio_bin is None:
                    st.table(MasterDataSets.bin_content_live_df)
                qty_in_bin = bin_info['qty_in_bin'].values[0]
                compartment_id = bin_info['compartment_id'].values[0]
                self.logger.info(f"sku {target_sku} in bin {prio_bin} qty in bin {qty_in_bin}")

                # Insufficient qty in system
                if qty_needed > full_system_qty:
                    check_restock = False
                    self.logger.warning(f"sku {target_sku} qty requested: {qty_needed} qty in system: {full_system_qty}")
                    self.insufficient_qty_pick_order.append(row)        


                # 2. Do have sufficient qty to pick - Can I pick from one bin or do I need more?
                elif qty_needed <= qty_in_bin:
                    check_restock = True
                    # can be picked from single bin
                    self.logger.info(f"{qty_needed} units of sku {target_sku} can be picked entirely from bin {prio_bin} with pre-pick qty of {qty_in_bin}")
                    # 2a. Reduce qty in bin
                    MasterDataSets.update_bin_qty(prio_bin, compartment_id, -qty_needed) # want to deduct the qty in the
                    # 2b. Update qty in system
                    MasterDataSets.update_sku_qty(target_sku, -qty_needed) # update sku_live_df
                    # 2c look up stack bin is in
                    target_stack_id = MasterDataSets.get_stack_id(prio_bin)
                    # 2d. record depth of bin in stacks and pop to top
                    bins_above = self._pick(prio_bin, target_sku, target_stack_id)
                    # 2e log to excel - unnecessary
                    self.log_csv(prio_bin, bins_above, target_stack_id, i, full_system_qty)
                    if qty_needed < qty_in_bin:
                        self.logger.debug(f"sku {target_sku} successfully picked and has units remaining in prio bin")

                    # if qty_needed = qty_in_bin, need to mark the bin as empty
                    elif qty_needed == qty_in_bin:
                        self.logger.info(f" sku {target_sku} picked all items in compartment {compartment_id} of bin {prio_bin}. Now it will be marked empty.")
                        bin_info = MasterDataSets.get_bin_compartment_contents(prio_bin, target_sku) 
                        if bin_info['qty_in_bin'].values[0] == 0:
                            self.logger.debug(f"confirmed - qty in bin is {bin_info['qty_in_bin'].values[0]}")
                            update_success = MasterDataSets.mark_compartment_empty(prio_bin, compartment_id) # marks empty in bin_content_live_df
                            
                            if update_success:
                                self.logger.info(f"success marking bin {prio_bin} compartment {compartment_id} as empty")
                                # update sku live df - new prio 1 bin and update other bin priorities in system
                                sku_info = MasterDataSets.get_sku_info(target_sku)
                                full_system_qty = sku_info['full_system_qty'].values[0] # if not sku_info.empty else None
                                if full_system_qty > 0:
                                    # can't reassign priorities if there is no priority 2 bin!
                                    self._reassign_priorities(target_sku) 
                                    self._update_sku_live_prio_bin(target_sku)
                                    self.update_bin_capacity_df(restock = False, empty= True, bin_id=prio_bin) # updates qty in bins_capacity_df

                            else:
                                self.logger.warning(f"Issue marking bin {prio_bin} compartment id: {compartment_id} as empty")
                            
                elif qty_needed > qty_in_bin:
                    # need more than one bin to fulfil this order, but have enough units in the system
                    check_restock = True
                    qty_remaining = qty_needed
                    
                    # 2b. Update qty in system
                    MasterDataSets.update_sku_qty(target_sku, qty_needed) # update sku_live_df
                    
                    while qty_remaining > 0:
                        bin_info = MasterDataSets.get_bin_compartment_contents(prio_bin, target_sku)
                        # self.logger.info(f"{qty_remaining} units requested of sku {target_sku}. {qty_in_bin} can be picked from bin {prio_bin}. After picking bin empty, {(qty_remaining - qty_in_bin)} units still needed")
                        
                        # 2c look up stack bin is in
                        target_stack_id = MasterDataSets.get_stack_id(prio_bin)
                        # 2d. record depth of bin in stacks and pop to top
                        bins_above = self._pick(prio_bin, target_sku, target_stack_id)
                        self.log_csv(prio_bin, bins_above, target_stack_id, i, full_system_qty)

                        # Do I need to empty my existing bin?
                        # 2a. Reduce qty in bin
                        if qty_remaining >= qty_in_bin:
                            qty_picked = qty_in_bin
                        if qty_remaining < qty_in_bin:
                            qty_picked = qty_remaining
                        
                        MasterDataSets.update_bin_qty(prio_bin, compartment_id, qty_picked)
                        qty_remaining -= qty_picked
                        
                        bin_info = MasterDataSets.get_bin_compartment_contents(prio_bin, target_sku) 
                        if bin_info['qty_in_bin'].values[0] == 0: # Mark bin as empty if it is fully used
                            self.logger.info(f" sku {target_sku} picked all items in compartment {compartment_id} of bin {prio_bin}. Now it will be marked empty.")
                            self.logger.debug(f"confirmed - qty in bin is {bin_info['qty_in_bin'].values[0]}")
                            update_success = MasterDataSets.mark_compartment_empty(prio_bin, compartment_id) # marks empty in bin_content_live_df
                            
                            if update_success:
                                self.logger.info(f"success marking bin {prio_bin} compartment {compartment_id} as empty")

                                sku_info = MasterDataSets.get_sku_info(target_sku)
                                full_system_qty = sku_info['full_system_qty'].values[0] # if not sku_info.empty else None
                                if full_system_qty > 0:
                                    # update sku live df - new prio 1 bin and update other bin priorities in system
                                    self._reassign_priorities(target_sku) 
                                    self._update_sku_live_prio_bin(target_sku)
                                    self.update_bin_capacity_df(restock = False, empty= True, bin_id=prio_bin)  # updates qty in bins_capacity_df
                            else:
                                self.logger.warning(f"Issue marking bin {prio_bin} compartment id: {compartment_id} as empty")
                if check_restock is True:
                    # check restock
                    post_pick_sku_info = MasterDataSets.get_sku_info(target_sku)
                    self._check_refill(target_sku)
                                        
            elif fit_status == "No Fit": 
                self.logger.info(f"SKU {target_sku} was in given data, but does not fit in the AS")
                self.pick_orders.at[i, 'bin_id'] = pd.NA
                self.non_fit_pick_orders.append(row)
            elif fit_status == "SKU not found":
                self.logger.info(f"SKU {target_sku} was not in given sku data")
                self.excluded_pick_orders.append(row)
            elif fit_status == "No Dims":
                self.logger.info(f"SKU {target_sku} was given in sku data, but missing dimensions")
                self.excluded_pick_orders.append(row)
            else:
                self.logger.warning(f"Issue with assigning fit status to sku {target_sku} fit status: {fit_status}")
                
        # outside of for loop iterating through lines
        self.pick_orders = self.pick_orders[self.pick_orders['bin_id'].notna()]
        pick_orders_df = self.pick_orders
        pick_orders_output_csv = self.pick_orders.to_csv(index = False)
        st.session_state['count_insufficient_picks'] = self.track_insufficient_picks # integer

        count_line_no_fits = len(self.non_fit_pick_orders)
        count_line_fits = len(pick_orders_df)
        count_lines_excluded = len(self.excluded_pick_orders)
        count_insufficient_qty = len(self.insufficient_qty_pick_order)
        st.session_state['count_line_fits'] = count_line_fits
        st.session_state['count_line_no_fits'] = count_line_no_fits
        st.session_state['count_lines_excluded'] = count_lines_excluded
        st.session_state['count_insufficient_qty'] = count_insufficient_qty
        st.session_state['count_total_input_lines'] = self.num_rows
        
        for handler in self.logger.handlers:
            handler.flush()
        sim_progress_bar.empty()
        return pick_orders_output_csv, pick_orders_df
       
    def log_csv(self, bin_id, bins_above, stack, i, full_system_qty):
        self.pick_orders.at[i, 'bin_id'] = bin_id # Debug Command
        self.pick_orders.at[i, 'bins_above'] = bins_above
        self.pick_orders.at[i, 'stack'] = stack # Debug Command
        self.pick_orders.at[i, 'bins_per_line'] = self.bins_per_line
        self.pick_orders.at[i, 'qty in system before pick'] = full_system_qty          

    def _pick(self, bin_id, sku, target_stack_id):
        """gets depth of chosen bin and brings it to the top of the stack, updates the pick_orders qty remaining in syst"""
        bins_above = self._get_depth(bin_id, target_stack_id)
        self._pop_bin(bin_id, target_stack_id) # pop bin to top of stack after it is picked
        self.logger.info(f"sku {sku} had {bins_above} bins above in the stack. It will now be popped to the top of the stack")
        return bins_above
    
    def update_bin_capacity_df(self, restock: bool, empty:bool, bin_id):
        """Updates # of available compartments in given bin. Either increments (restock = True)
        or decrements (empty = True)"""
        if restock is True:
            bin_index = MasterDataSets.bins_capacity_df['bin_id'] == bin_id
            if any(bin_index):
                MasterDataSets.bins_capacity_df.loc[bin_index, 'num_full_compartments'] += 1
            pass

        if empty is True:
            bin_index = MasterDataSets.bins_capacity_df['bin_id'] == bin_id
            if any(bin_index):
                MasterDataSets.bins_capacity_df.loc[bin_index, 'num_full_compartments'] -= 1

    def _get_depth(self, bin_id, target_stack_id)-> tuple[int, int]: 
        """function pulls in the stack_contents and determines the index (depth) of the bin in the stack
         returns bins_above"""
        for stack in self.stack_contents:
            stack_id, bins = stack
            if stack_id == target_stack_id:
                if bin_id in bins:
                    bins_above = bins.index(bin_id)
                    return bins_above
                self.logger.error(f"Bin {bin_id} not found in stack {target_stack_id}")
                return None
        self.logger.error(f"Stack {target_stack_id} not found in stack.contents")

    
    def _pop_bin(self, bin_id, target_stack_id)-> None:
        """function to pop the bin_id picked to the top of the stack
        updates self.bins"""
        for stack in self.stack_contents:
            stack_id, self.bins = stack
            if stack_id == target_stack_id:
                if bin_id in self.bins:
                    bin_index = self.bins.index(bin_id)
                    self.bins.pop(bin_index) # Remove the bin from its current position
                    self.bins.insert(0, bin_id) # Insert the bin at the top of the list

    def _reassign_priorities(self, target_sku)-> None:
        """Updates the priorities in bin_content_live_df - decrementing all current priorities by 1
        Finds new priority 1 bin and assigns that to the sku_live_df""" 

        target_mask = MasterDataSets.bin_content_live_df['sku'] == target_sku

        if not target_mask.any(): # If no bins contain the target SKU, return original dataframes
            self.logger.error(f"No bins found containing {target_sku}")
            return
        # Decrement priorities for all bins containing the target SKU
        MasterDataSets.bin_content_live_df.loc[target_mask, 'priority'] = MasterDataSets.bin_content_live_df.loc[target_mask, 'priority'] - 1
        
    def _update_sku_live_prio_bin(self, target_sku):    
        # Find the new priority 1 bin (was previously priority 2)
        new_prio_1_mask = (MasterDataSets.bin_content_live_df['sku'] == target_sku) & (MasterDataSets.bin_content_live_df['priority'] == 1)
        
        # If a new priority 1 bin exists, update sku_live_df
        if new_prio_1_mask.any():
            new_prio_1_bin = MasterDataSets.bin_content_live_df.loc[new_prio_1_mask, 'bin_id'].values[0]
            MasterDataSets.sku_live_df.loc[MasterDataSets.sku_live_df['sku'] == target_sku, 'prio_bin'] = new_prio_1_bin
        else:
            # If no priority 1 bin exists after update, clear the prio_bin field
            MasterDataSets.sku_live_df.loc[MasterDataSets.sku_live_df['sku'] == target_sku, 'prio_bin'] = None
            self.logger.error(f"No priority 1 bin for sku {target_sku}")

    def _check_refill(self, target_sku)-> None:
        """check if restock level is reached for target sku. 
        If so, trigger a restock."""
        # Get sku data
        post_pick_sku_info = MasterDataSets.get_sku_info(target_sku)
        restock_qty = post_pick_sku_info['restock_qty'].values[0] # qty that triggers a restock
        qty_in_system = post_pick_sku_info['qty_in_system'].values[0]

        if restock_qty < qty_in_system: # No Restock
            pass

        elif restock_qty >= qty_in_system: # Needs Restock
            self.logger.info(f"sku {target_sku} is ready to be restocked with {qty_in_system} units in the system and a restock level of {restock_qty}")
  
            #Qty to Restock
            full_bin_qty = post_pick_sku_info['full_bin_qty'].values[0]
            full_system_qty = post_pick_sku_info['full_system_qty'].values[0]
            qty_to_restock = full_system_qty - qty_in_system

            compartment_size = post_pick_sku_info['compartment_size'].values[0] # compartment size needed
            
            while qty_to_restock > 0:
                # Find empty compartment in bin with appropriate compartment size
                target_bin_id = self._find_available_bin(compartment_size)

                if target_bin_id is None:
                    self.logger.info(f"No available bins for compartment size {compartment_size}, attempting consolidation")
                    compartments_freed = self.consolidation(compartment_size)

                    if compartments_freed > 0:
                        # Try to find available bin again after consolidation
                        target_bin_id = self._find_available_bin(compartment_size)

                    if target_bin_id is None:
                        self.logger.error(f"Still no available bins after consolidation")
                        # Handle this case - maybe skip restock or log error
                        return

                target_compartment_id = self._find_available_compartments(target_bin_id)
                
                if qty_to_restock <= full_bin_qty: # Needs a single storage location
                    compartment_restock_qty = qty_to_restock   
                elif qty_to_restock > full_bin_qty: # Will require > 1 location
                    compartment_restock_qty = full_bin_qty

                priority = self._get_last_priority(target_sku) + 1 # Will return 0 for _get_last_priority if no bins found
                
                restock_success = self.restock_compartment(target_bin_id, target_compartment_id, target_sku, compartment_restock_qty, priority)
                qty_to_restock = qty_to_restock - compartment_restock_qty
                self.logger.info(f"{target_sku} restocked to bin {target_bin_id} compartment {target_compartment_id} with qty {compartment_restock_qty} ")


    def _get_last_priority(self, sku) -> int:
        """
        Find the maximum priority value for a given SKU in bin_content_live_df.
        returns the maximum priority value for the SKU, or 0 if the SKU doesn't exist in any bin
        """
        # Filter for rows with the given SKU
        sku_rows = MasterDataSets.bin_content_live_df[MasterDataSets.bin_content_live_df['sku'] == sku]
        if sku_rows.empty:
            return 0  # Return 0 if SKU doesn't exist, so first priority will be 1
        max_priority = sku_rows['priority'].max() # Find the maximum priority value
        return max_priority

            
    def _find_available_bin(self, sku_compartment_size)-> int:
        
        compartment_size_to_total = {1.0: 1, 0.5: 2, 0.25: 4, 0.125: 8}

        available_bins = MasterDataSets.bins_capacity_df[
            (MasterDataSets.bins_capacity_df['compartment_size'] == sku_compartment_size) &
            ((MasterDataSets.bins_capacity_df['num_full_compartments'] < MasterDataSets.bins_capacity_df['compartment_size'].map(compartment_size_to_total)))
        ]
        num_not_full_bins: int = len(available_bins)
        
        if not available_bins.empty:
            self.logger.debug(f" {num_not_full_bins} bins were found to not be full with compartment size {sku_compartment_size} (total compartments: {compartment_size_to_total[sku_compartment_size]}), bin id: {available_bins.iloc[0]['bin_id']}")
            return available_bins.iloc[0]['bin_id']
        else:
            self.logger.error(f"No empty compartments found for compartment size: {sku_compartment_size}")
            return None
        

    def _find_available_compartments(self, bin_id):
        bin_entries = MasterDataSets.bin_content_live_df[MasterDataSets.bin_content_live_df['bin_id'] == int(bin_id)]
        
        if bin_entries.empty:
            self.logger.warning(f"bin entries returned empty while searching for available compartments")
            return None
        
        available_compartments = bin_entries[   # Find entries where sku, priority are None or a blank string and qty is 0
            (bin_entries['sku'].isna() | (bin_entries['sku'] == '')) & 
            (bin_entries['priority'].isna() | (bin_entries['priority'] == '')) & 
            (bin_entries['qty_in_bin'] == 0)
        ]
        
        # Return the compartment_id of the first available compartment
        if not available_compartments.empty:
            self.logger.debug(f"available compartment found! compartment: {available_compartments.iloc[0]['compartment_id']}")
            return available_compartments.iloc[0]['compartment_id']
        else:
            self.logger.warning(f"bin entries returned empty while searching for available compartments")
            return None


    def restock_compartment(self, bin_id, compartment_id, sku, qty, priority):
        """Restocks given bin and compartment id with the given sku, qty, and priority.
        Returns True if successful and False if unsuccessful."""  
        # Verify that the bin and compartment exist
        bin_comp_mask = (MasterDataSets.bin_content_live_df['bin_id'] == bin_id) & (MasterDataSets.bin_content_live_df['compartment_id'] == compartment_id)
        if not any(bin_comp_mask):
            print(f"Error: Bin {bin_id}, Compartment {compartment_id} not found.")
            return False

        # Update bin_content_live_df - set the SKU, priority, and quantity
        MasterDataSets.bin_content_live_df.loc[bin_comp_mask, 'sku'] = sku
        MasterDataSets.bin_content_live_df.loc[bin_comp_mask, 'priority'] = priority
        MasterDataSets.bin_content_live_df.loc[bin_comp_mask, 'qty_in_bin'] = qty
        
        # Update sku_live_df - increase qty_in_system and the priotiy 1 bin
        sku_mask = MasterDataSets.sku_live_df['sku'] == sku
        if any(sku_mask):
            MasterDataSets.sku_live_df.loc[sku_mask, 'qty_in_system'] += qty            
            prio1_mask = (MasterDataSets.bin_content_live_df['sku'] == sku) & (MasterDataSets.bin_content_live_df['priority'] == 1) # Find the current priority 1 bin for this SKU
            if any(prio1_mask):
                current_prio1_bin = MasterDataSets.bin_content_live_df.loc[prio1_mask, 'bin_id'].iloc[0] # Get the bin_id of the priority 1 bin
                MasterDataSets.sku_live_df.loc[sku_mask, 'prio_bin'] = current_prio1_bin # Update the prio_bin value in sku_live_df
            else:
                self.logger.warning(f"Warning: No priority 1 bin found for SKU {sku}. prio_bin not updated.")
        else:
            self.logger.warning(f"Warning: SKU {sku} not found in sku_live_df. Cannot update quantity.")
        
        # Update bins_capacity_df - increment num_full_compartments
        bin_mask = MasterDataSets.bins_capacity_df['bin_id'] == bin_id
        if any(bin_mask):
            MasterDataSets.bins_capacity_df.loc[bin_mask, 'num_full_compartments'] += 1
        else:
            self.logger.error(f"Warning: Bin {bin_id} not found in bins_capacity_df. Cannot update count.")
        return True


    def check_sku_fit_status(self, sku):
        """
        Check if a SKU is in the bincount_output dataframe and return its Fit status.
        returns: 'Fit', 'No Fit', or 'SKU not found'
        """
        if sku in self.bincount_output_df['SKU'].values: # Check if SKU exists in the dataframe
            fit_status = self.bincount_output_df.loc[self.bincount_output_df['SKU'] == sku, 'Fit|No Fit'].iloc[0] # Get the corresponding 'Fit|No Fit' value
            return fit_status
        else:
            return "SKU not found"
        
    def consolidation(self, compartment_size):
        """Consolidate bins by moving skus from multiple partially-filled bins into fewer bins. 
        returns # compartments freed through consolidation"""

        self.logger.info(f"Starting consolidation for compartment size {compartment_size}")

        self.debug_consolidation_data(compartment_size)

        compartments_freed = 0

        # Step 1: Find SKUs that exist in muleiple bins with the target compartment size
        consolidation_candidates = self._find_consolidation_candidates(compartment_size)

        if not consolidation_candidates:
            self.logger.info(f"No consolidation candidates found for compartment size {compartment_size}")
            return 0
        
        # Step 2: Process each SKU that can be consolidated
        for sku_data in consolidation_candidates:
            sku = sku_data['sku']
            bins_with_sku = sku_data['bins']
            total_qty = sku_data['total_qty']

            self.logger.info(f"Attempting to consolidate sku {sku} (total qty: {total_qty}) from {len(bins_with_sku)} bins")

            #Step 3: Determine optimal bin arrangement
            sku_info = MasterDataSets.get_sku_info(sku)
            if sku_info.empty:
                continue

            full_bin_qty = sku_info['full_bin_qty'].values[0]
            optimal_bins_needed = math.ceil(total_qty / full_bin_qty)
            current_bins_used = len(bins_with_sku)

            if optimal_bins_needed >= current_bins_used:
                # No consolidation benefit
                continue

            # Step 4: Perform Consolidation
            bins_freed = self._consolidate_sku(sku, bins_with_sku, total_qty, full_bin_qty, optimal_bins_needed)
            compartments_freed += bins_freed

            self.logger.info(f"SKU {sku}: Consolidated from {current_bins_used} to {optimal_bins_needed} bins, freed {bins_freed} compartments")

        self.logger.info(f"Consolidation complete. Total compartments freed: {compartments_freed}")
        return compartments_freed
        
    
    def _find_consolidation_candidates(self, compartment_size):
        """ Find SKUs that are spread across multiple bins and could benefit from consolidation.
        returns a lisst of dictionaries containing SKU consolidation data"""

        # Get all non-empty bins with the specified compartment size
        occupied_bins = MasterDataSets.bin_content_live_df[
            (MasterDataSets.bin_content_live_df['compartment_size'] == compartment_size) &
            (MasterDataSets.bin_content_live_df['sku'].notna()) & 
            (MasterDataSets.bin_content_live_df ['sku'] != '') &
            (MasterDataSets.bin_content_live_df['qty_in_bin'] > 0)
        ]
    
        if occupied_bins.empty:
            return []
        
        # Group by SKU to find those in multiple bins
        sku_groups = occupied_bins.groupby('sku').agg({
            'bin_id': 'count',
            'qty_in_bin': 'sum'
        }).reset_index()

        # Only consider SKUs in multiple bins
        multi_bin_skus = sku_groups[sku_groups['bin_id'] > 1]

        candidates = []
        for _, row in multi_bin_skus.iterrows():
            sku = row['sku']
            total_qty = row['qty_in_bin']

            # Get detailed bin information for this SKU
            sku_bins = occupied_bins[occupied_bins['sku'] == sku][
                ['bin_id', 'compartment_id', 'qty_in_bin', 'priority']
            ].to_dict('records')

            candidates.append({
                'sku': sku,
                'bins': sku_bins,
                'total_qty': total_qty,
                'bin_count': len(sku_bins)
            })

        candidates.sort(key=lambda x: x['bin_count'], reverse=True) # Sort by potential benefit (more bins used = higher consolidation potential

        return candidates
    

    def _consolidate_sku(self, sku, bins_with_sku, total_qty, full_bin_qty, optimal_bins_needed):
        """Consolidate a specific SKU from multiple bins into fewer bins. 
        returns number of compartments freed"""
        
        bins_with_sku.sort(key=lambda x: x['priority']) # Sort bins by priority to maintain priority order

        # Step 1: Empty all current bins of this SKU
        for bin_data in bins_with_sku:
            bin_id = bin_data['bin_id']
            compartment_id = bin_data['compartment_id']

            # Mark compartment as empty
            MasterDataSets.mark_compartment_empty(bin_id, compartment_id)
            # Update bin capacity
            self.update_bin_capacity_df(restock = False, empty = True, bin_id = bin_id)

        # Step 2: Redistribute the SKU into optimal number of bins
        qty_remaining = total_qty
        bins_used = 0
        priority = 1

        while qty_remaining > 0 and bins_used < optimal_bins_needed:
            # Find an available bin with the right compartment size
            sku_info = MasterDataSets.get_sku_info(sku)
            compartment_size = sku_info['compartment_size'].values[0]

            target_bin_id = self._find_available_bin(compartment_size)
            if target_bin_id is None:
                self.logger.warning(f"Could not find available bin for sku {sku} comsolidation")
                break

            target_compartment_id = self._find_available_compartments(target_bin_id)
            if target_compartment_id is None:
                self.logger.warning(f"Could not find available compartment in bin {target_bin_id}")
                break
            
            # Determine qty to place in this bin
            qty_to_place = min(qty_remaining, full_bin_qty)

            # Restock the compartment
            success = self.restock_compartment(target_bin_id, target_compartment_id, sku, qty_to_place, priority)

            if success:
                qty_remaining -= qty_to_place
                bins_used += 1
                priority += 1
                self.logger.debug(f"Placed {qty_to_place} units of {sku} in bin {target_bin_id}, compartment {target_compartment_id}")
                self._update_sku_live_prio_bin(sku)
            else:
                self.logger.error(f"Failed to restock compartment during consolidation")
                break

        # Calculate compartments freed
        original_bins = len(bins_with_sku)
        compartments_freed = original_bins - bins_used

        return max(0, compartments_freed)
    

    def debug_consolidation_data(self, compartment_size):
        """Debug function to check consolidation data"""
        df = MasterDataSets.bin_content_live_df
        
        print(f"\n=== DEBUG: Compartment size {compartment_size} ===")
        print(f"Total rows: {len(df)}")
        
        size_match = df[df['compartment_size'] == compartment_size]
        print(f"Rows with compartment size {compartment_size}: {len(size_match)}")
        
        has_sku = size_match[size_match['sku'].notna() & (size_match['sku'] != '')]
        print(f"With valid SKU: {len(has_sku)}")
        
        has_qty = has_sku[has_sku['qty_in_bin'] > 0]
        print(f"With qty > 0: {len(has_qty)}")
        
        if len(has_qty) > 0:
            sku_counts = has_qty.groupby('sku').size()
            multi_bin_skus = sku_counts[sku_counts > 1]
            print(f"SKUs in multiple bins: {len(multi_bin_skus)}")
            if len(multi_bin_skus) > 0:
                print("Multi-bin SKUs:", multi_bin_skus.to_dict())