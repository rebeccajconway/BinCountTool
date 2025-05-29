import streamlit as st
import pandas as pd
import logging
import os
from datetime import datetime
import time
import io

from components import setup_logger


class Sim:
    def __init__(self, bins_list, pick_orders, stack_contents, bincount_output, restock_data):

        if isinstance(pick_orders, pd.DataFrame):
            self.pick_orders = pick_orders
        else:
            raise ValueError("pick_orders must be a pandas DataFrame")
        
        # initializing lists and dataframes for remainder of class
        self.stack_contents = stack_contents # includes stack_id and bin_id  
        self.bins_list = bins_list # contains bin_id, sku, qty and priority
        self.pick_orders['bin_id'] = pd.NA
        self.pick_orders_lines_in_as = []
        self.non_fit_pick_orders =[] # contains orders of skus that are not in the AutoStore - these will be excluded from output pick_orders and bin distribution
        self.excluded_pick_orders = [] # picks where sku was not given in sku data thus it is excluded
        self.bincount_output_df = pd.DataFrame(bincount_output)
        self.restock_data = restock_data
        self.restock_halfbin = []
        self.restock_quarterbin = []
        self.restock_eighthbin = []
        self.bins_per_line = 1
        self.track_insufficient_picks = 0
         

        self.logger = setup_logger()

    def _run(self): # csv data output
        """Filters through outbound orders that fit in the AutoStore and updates the stock in the system after a pick"""
        
        self.logger.info("Application Started")
        
        if self.bins_list is None: # Ensure bins_list is initialized
            self.logger.error("bins_list is not initialized")
            raise ValueError("bins_list is not initialized.")
        st.write(self.bins_list)
        
        sim_progress_bar = st.progress(0, text = "simulation progress ... ") # Progress Bar to load how it is being simulated
        self.num_rows = len(self.pick_orders)
        self.logger.info(f"Processing {self.num_rows} orders")

        st.button(label="stop and save", key="stop_button")

        self.debug_bins_list()

        # loop through order / outbound data: 
        for i, row in self.pick_orders.iterrows():
            
            if i % st.session_state['save_interval'] == 0 and i is not 0: # Periodically save data to session_state incase simulation is stopped
                self.pick_orders_lines_in_as = self.pick_orders[self.pick_orders['bin_id'].notna()]
                #pick_orders_df = self.pick_orders_lines_in_as
                self.pick_orders_output_csv = self.pick_orders_lines_in_as.to_csv(index = False)
                st.session_state['pick_orders_df'] = self.pick_orders_lines_in_as
                st.session_state['pick_orders_output_csv'] = self.pick_orders_output_csv
                

                st.session_state['count_insufficient_picks'] = self.track_insufficient_picks # integer
                count_line_no_fits = len(self.non_fit_pick_orders)
                count_line_fits = len(self.pick_orders_lines_in_as)
                count_lines_excluded = len(self.excluded_pick_orders)
                st.session_state['count_line_fits'] = count_line_fits
                st.session_state['count_line_no_fits'] = count_line_no_fits
                st.session_state['count_lines_excluded'] = count_lines_excluded
                st.session_state['count_total_input_lines'] = self.num_rows
                print("session state saved")

                    
            if st.session_state['stop_run'] is True:
                self.logger.info(f"Simulation Stopping...")
                self.backup_ss
                st.rerun()

            #else:
            target_sku: str = row['sku']
            timestamp = row['timestamp']
            qty_needed: int = row['qty']

            order_start_time = time.time()
            self.logger.debug(f"Processing order {i+1}/{self.num_rows}: SKU={target_sku}, Qty={qty_needed}")
            
            sim_progress_bar.progress(((i+1)/self.num_rows), text=f"simulation progress ({i+1}/{self.num_rows})... ") # Progress Bar loading

            fit_status = self.check_sku_fit_status(target_sku)

            

            if fit_status == "Fit": # makes sure requested sku is one that is in the AutoStore system:   
                
                bin_id, bin_qty, priority = self._get_bins(target_sku) # Calls Bin_id with Priority 1
                
                #update stock count for restocking purposes
                result = self.restock_data.loc[self.restock_data['sku'] == target_sku, ['qty_in_system', 'full_qty', 'restock_qty','capped_bin_count', 'force_restock_qty']]
                if result.empty:
                    self.logger.error(f"restock data not present for sku {target_sku}")
                    st.warning("simulation _run program: restock_data is empty")
                
                else: # if not result.empty:
                    self.update_system_stock(result, target_sku, qty_needed)
                    
                    if self.sufficient_qty is False:
                        self.track_insufficient_picks += 1
                    if self.sufficient_qty is True:
                        
                        # moved to update_system_stock
                        #restock_qty = result['restock_qty'].values[0]
                        #full_qty = result['full_qty'].values[0]
                        #qty_in_system = result['qty_in_system'].values[0]
                        #capped_bin_count = result['capped_bin_count'].values[0]
                        #self.qty_in_system_pre_pick = qty_in_system
                        #qty_in_system = qty_in_system - qty_needed
                        #self.qty_in_system_post_pick = qty_in_system
                        #print(f"{sku} qty in system after pick: {qty_in_system} with a restock level {restock_qty}")
                        #self.restock_data.loc[self.restock_data['sku'] == sku, 'qty_in_system'] = qty_in_system
                        #if qty_in_system <= restock_qty:
                        #   print(f"sku {sku} needs restock")
                        #    self._check_refill(sku)

                    
                        self.bins_per_line = 1 # re-initialize for each order line analyzed
                        self.logger.debug(f"for sku {target_sku} qty needed: {qty_needed} and qty in bin {bin_id} is {bin_qty} ")

                        if qty_needed < bin_qty: # if the qty requested can be fulfilled with the priority 1 bin
                            self.logger.info(f"sku {target_sku} qty needed {qty_needed} can be fulfilled with current bin {bin_id}")
                            qty_picked_from_bin = qty_needed
                            self._pick(bin_id, target_sku, qty_picked_from_bin, priority, i)
                            self.bins_per_line = 1
                            

                        elif qty_needed == bin_qty: # empty the bin and move up the priorities for next time it is picked
                            qty_picked_from_bin = qty_needed
                            self._pick(bin_id, target_sku, qty_picked_from_bin, priority, i)
                            self.bins_per_line = 1
                            self._reassign_priorities(target_sku) # bump up the priorities for each sku
                            self._mark_empty(bin_id, target_sku) # mark bin / compartment as empty
                            self.logger.info(f"sku {target_sku} qty needed {qty_needed} can be fulfilled with current bin {bin_id} which is now empty")
                            
                                
                        elif qty_needed > bin_qty: # start by empting existing bin, pick the next one then decide if it needs to be emptied or not
                            self.logger.info(f"analyzing sku {target_sku} which needs {qty_needed} units from bin {bin_id} which has a qty of {bin_qty}")
                            qty_needed = qty_needed - bin_qty # takes remainder of objects from old bin then determines how many are still needed
                            self._reassign_priorities(target_sku) # bump up the priorities for each sku
                            self._mark_empty(bin_id, target_sku) # mark bin / compartment as empty
                            bin_id, bin_qty, priority = self._get_bins(target_sku) # Calls Bin_id with Priority 1
                            while qty_needed > 0 and bin_id is not None:
                                bin_id, bin_qty, priority = self._get_bins(target_sku) # Calls Bin_id with Priority 1
                                self.bins_per_line += 1
                                self.logger.info(f"analyzing sku {target_sku} which needs {qty_needed} units from bin {bin_id} which has a qty of {bin_qty}")
                                if qty_needed < bin_qty:
                                    qty_picked_from_bin = qty_needed
                                    self._pick(bin_id, target_sku, qty_picked_from_bin, priority, i)
                                    # bin_qty = bin_qty - qty_needed
                                    qty_needed = 0
                                elif qty_needed >= bin_qty:
                                    qty_picked_from_bin = bin_qty
                                    self._pick(bin_id, target_sku, qty_picked_from_bin, priority, i)
                                    qty_needed = qty_needed - bin_qty # takes remainder of objects from old bin then determines how many are still needed
                                    self._reassign_priorities(target_sku) # bump up the priorities for each sku
                                    self._mark_empty(bin_id, target_sku) # mark bin / compartment as empty
                            if qty_needed > 0 and bin_id is None:
                                self.logger.warning(f"sku {target_sku} was unable to be fully picked as {qty_needed} still are requested, but there are no more bins with this sku.")
    
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
        st.session_state['count_line_fits'] = count_line_fits
        st.session_state['count_line_no_fits'] = count_line_no_fits
        st.session_state['count_lines_excluded'] = count_lines_excluded
        st.session_state['count_total_input_lines'] = self.num_rows
        
        for handler in self.logger.handlers:
            handler.flush()
        sim_progress_bar.empty()
        return pick_orders_output_csv, pick_orders_df
       
        
                     

    def _pick(self, bin_id, sku, qty_picked_from_bin, priority, i):
        """gets depth of chosen bin and brings it to the top of the stack, updates the pick_orders qty remaining in syst"""
        bins_above, stack = self._get_depth(bin_id)
        self.logger.info(f"sku {sku} had {bins_above} bins above in the stack. It will now be popped to the top")
        
        self.pick_orders.at[i, 'bin_id'] = bin_id # Debug Command
        self.pick_orders.at[i, 'bins_above'] = bins_above
        self.pick_orders.at[i, 'stack'] = stack # Debug Command
        self.pick_orders.at[i, 'bins_per_line'] = self.bins_per_line

        new_qty = self._update_qty(bin_id, sku, qty_picked_from_bin) # update the qty of units stored after picking the order
        self.logger.info(f"sku {sku} picked, bin {bin_id} has a remaining qty of {new_qty} post pick")

        self.pick_orders.at[i, 'qty remaining in prio 1 bin'] = new_qty # qty in bin after line picked
        self.pick_orders.at[i, 'qty in system before pick'] = self.qty_in_system_pre_pick
        self.pick_orders.at[i, 'system qty remaining'] = self.qty_in_system_post_pick
        self._pop_bin(bin_id) # pop bin to top of stack after it is picked
        

    def _get_bins(self, target_sku) :
        # finds the best bin with target sku and priority 1
        # returns bin_id, priority and qty in the bin        
        self.logger.debug(f"Looking for SKU: {target_sku}")
        
        # Debug the first few bins to see what they look like
        if len(self.bins_list) > 0:
            self.logger.debug(f"First bin structure: {self.bins_list[0]}")
            
        prio_bin_id = None
        prio_qty = None
        prio_priority = None

        for bin_entry in self.bins_list:
            # Skip malformed entries
            if len(bin_entry) != 3:
                self.logger.warning(f"Skipping malformed bin entry: {bin_entry}")
                continue
                
            bin_id, compartment_size, sku_tuples = bin_entry
            
            # Add additional debugging
            self.logger.debug(f"Checking bin {bin_id}, compartment size {compartment_size}")
            self.logger.debug(f"SKU tuples: {sku_tuples}")
            
            # Handle case where sku_tuples might be empty
            if not sku_tuples:
                self.logger.debug(f"Empty SKU tuples in bin {bin_id}")
                continue
            
            for sku_data in sku_tuples:
                # Check if sku_data has the expected format
                if not isinstance(sku_data, (list, tuple)) or len(sku_data) < 3:
                    self.logger.warning(f"Malformed SKU data in bin {bin_id}: {sku_data}")
                    continue
                    
                sku, qty, priority = sku_data
                
                # Debug each SKU check
                self.logger.debug(f"Checking SKU {sku} (target: {target_sku}), priority {priority}")
                
                if sku == target_sku and priority == 1: 
                    prio_bin_id = bin_id
                    prio_qty = qty
                    prio_priority = priority
                    self.logger.debug(f"MATCH! SKU {target_sku} found in bin {prio_bin_id}, qty {prio_qty}, priority {prio_priority}")
                    return prio_bin_id, prio_qty, prio_priority
        
        # If we get here, no match was found
        self.logger.warning(f"No bin with priority 1 found for SKU {target_sku}.")
        
        # As a fallback, look for the SKU with any priority
        for bin_entry in self.bins_list:
            if len(bin_entry) != 3:
                continue
                
            bin_id, compartment_size, sku_tuples = bin_entry
            
            if not sku_tuples:
                continue
            
            for sku_data in sku_tuples:
                if not isinstance(sku_data, (list, tuple)) or len(sku_data) < 3:
                    continue
                    
                sku, qty, priority = sku_data
                
                if sku == target_sku:  # Any priority
                    self.logger.debug(f"Found SKU {target_sku} with non-priority 1 in bin {bin_id}, priority {priority}")
                    return bin_id, qty, priority
        
        self.logger.warning(f"No bin found for SKU {target_sku} with any priority.")
        return None, None, None
        
        #for bin_id, compartment_size, sku_tuple in self.bins_list:
        #    for sku, qty, priority in sku_tuple:
        #        if sku == target_sku and priority == 1: 
        #            prio_bin_id = bin_id
        #            prio_qty = qty
        #            prio_priority = priority
        #            self.logger.debug(f"sku {sku} target bin found: bin {prio_bin_id}, qty {prio_qty} and priority {prio_priority}")
        #            return prio_bin_id, prio_qty, prio_priority
        #self.logger.warning(f"No bin found for sku {sku}.")
        #return None, None, None

    def _get_depth(self, bin_id)-> tuple[int, int]: 
        """function pulls in the stack_contents and determines the index (depth) of the bin in the stack
         returns bins_above and stack_id"""
        for stack in self.stack_contents:
            stack_id, bins = stack
            if bin_id in bins:
                bins_above = bins.index(bin_id)
                return bins_above, stack_id
        return None, None # Return None if bin_id is not found
    
    def _pop_bin(self, bin_id)-> None:
        """function to pop the bin_id picked to the top of the stack
        updates self.bins"""
        for stack in self.stack_contents:
            stack_id, self.bins = stack
            if bin_id in self.bins:
                bin_index = self.bins.index(bin_id)
                self.bins.pop(bin_index) # Remove the bin from its current position
                self.bins.insert(0, bin_id) # Insert the bin at the top of the list

    def _reassign_priorities(self, target_sku)-> None:
        """re-assign the priorities of sku locations
        updates self.bins_list with new priorities""" 
        updated_bins_list = [] #self.bins_list
        for bin_id, compartment_size, skus in self.bins_list:
            updated_skus = []
            for sku, qty, priority in skus:
                if sku == target_sku:
                    if priority != 1: # priority 1 would be empty, so move all others up by 1
                        new_priority = priority - 1  
                        updated_skus.append((sku, qty, new_priority))
                    elif priority == 1:                                       
                        sku = ""
                        qty = ""
                        new_priority= 0 # priority 0 means it needs to be written to blank
                        updated_skus.append((sku, qty, new_priority))
                else:
                    updated_skus.append((sku, qty, priority)) 
            updated_bins_list.append((bin_id, compartment_size, updated_skus))
        self.bins_list = updated_bins_list
        return
                        
    def _update_qty(self, target_bin_id, target_sku, qty_picked_from_bin)-> int:
        """updates the qty of a sku in the given bin by subtracting the qty needed"""

        updated_bin_list = []
        for bin_id, compartment_size, skus in self.bins_list:
            if bin_id == target_bin_id:
                updated_skus = []
                for sku, qty, priority in skus:
                    if sku == target_sku:
                        new_qty = qty - qty_picked_from_bin
                        updated_skus.append((sku, new_qty, priority))
                    else:
                        updated_skus.append((sku, qty, priority))
                updated_bin_list.append((bin_id, updated_skus))
            else:
                updated_bin_list.append((bin_id, compartment_size, skus))  # Append unchanged bins as they are
        self.bins_list = updated_bin_list
        return new_qty  

    def _mark_empty(self, target_bin_id, target_sku)-> None:
        """updates bin_list with marking the priority 0 bin to empty for sku, qty and priority"""
        updated_bin_list = []
        for bin_id, compartment_size, skus in self.bins_list:
            updated_skus = []
            if bin_id == target_bin_id:
                for sku, qty, priority in skus:
                    if sku == target_sku and priority == 0:
                        updated_skus.append(("","",""))
                    else:
                        updated_skus.append((sku, qty, priority))
                updated_bin_list.append((bin_id, compartment_size, updated_skus))
            else:
                updated_bin_list.append((bin_id, compartment_size, skus))
        self.bins_list = updated_bin_list
        self.logger.info(f"sku {target_sku} picked bin {target_bin_id} to empty.")

    def _check_refill(self, target_sku)-> None:
        """check if there are enough items ready to restock a bin"""
        # potential issue - do we refill the initial value or the difference? If we do the difference, the bincount / size may change, but not worth re-running bincount tool
        # print("Restock Data Columns:", self.restock_data.columns)
        # print("First few rows:\n", self.restock_data.head())

        for index, row in self.restock_data.iterrows():
            sku = row['sku']
            if sku == target_sku:
                bin_count_cap = row['capped_bin_count']
                if bin_count_cap >= 1:
                    self._trigger_restock(sku, bin_count_cap) 

                elif bin_count_cap == 0.5:
                    self.restock_halfbin.append(sku) # add to list to update
                    self.logger.info(f"sku {sku} added to half bin restock list, which has a length of {len(self.restock_halfbin)}") 
                    if len(self.restock_halfbin) == 2: # Changed from >= to == - debug here if issues arise 3/14/25
                       self._trigger_restock(sku, bin_count_cap)
                    elif self.force_restock is True:
                        self._trigger_restock(sku, bin_count_cap)
                        self.logger.info(f"force restock triggered for sku {sku}")
                    elif len(self.restock_halfbin) > 2:
                        st.warning(f"issue with restock. Half Bin Restock: {self.restock_halfbin}")
                elif bin_count_cap == 0.25:
                    self.restock_quarterbin.append(sku)
                    self.logger.info(f"sku {sku} added to quarter bin restock list, which has a length of {len(self.restock_quarterbin)}")
                    if len(self.restock_quarterbin) == 4: # Changed from >= to == - debug here if issues arise 3/14/25
                        self._trigger_restock(sku, bin_count_cap)
                    elif self.force_restock is True:
                        self._trigger_restock(sku, bin_count_cap)
                        self.logger.info(f"force restock triggered for sku {sku}")
                    elif len(self.restock_quarterbin) > 4:
                        st.warning(f"issue with restock. Quarter Bin Restock: {self.restock_quarterbin}")
                elif bin_count_cap == 0.125:
                    self.restock_eighthbin.append(sku)
                    self.logger.info(f"sku {sku} added to eigth bin restock list, which has a length of {len(self.restock_eighthbin)}")
                    if len(self.restock_eighthbin) == 8: # Changed from >= to == - debug here if issues arise 3/14/25
                        self._trigger_restock(sku, bin_count_cap)
                    elif self.force_restock is True:
                        self._trigger_restock(sku, bin_count_cap)
                        self.logger.info(f"force restock triggered for sku {sku}")
                    elif len(self.restock_eighthbin) > 8:
                        st.warning(f"issue with restock. Eigth Bin Restock: {self.restock_eighthbin}")
                else:
                    self.logger.error(f"Error with check refill function for sku {sku}")
                    st.warning(f"_check_refill is returning inappropriate compartment size: {bin_count_cap}")
        
    
        
    def _trigger_restock(self, target_sku, bin_count_cap) -> None:
        if bin_count_cap >= 1:  # For skus that need a full bin
            qty_to_restock, qty_in_system = self._new_bin_qty(target_sku)
            max_qty_per_bin = self._get_max_qty_per_bin(target_sku)
        
            while qty_to_restock > 0:
                # Determine quantity for this bin
                new_bin_id = self._find_empty_bin()
                if new_bin_id is not None:    
                    
                    if qty_to_restock > max_qty_per_bin:
                        new_bin_qty = max_qty_per_bin
                    else:
                        new_bin_qty = qty_to_restock
                    
                    # Create new bin contents
                    new_bin_priority = self._get_last_priority(target_sku) + 1
                    new_bin_contents = [(target_sku, new_bin_qty, new_bin_priority)]
                
                    self._overwrite_bin(new_bin_id, new_bin_contents)
                    self._pop_bin(new_bin_id)
                    self.logger.info(f"new bin filled - bin: {new_bin_id} sku: {target_sku} qty: {new_bin_qty}")
            
                    # Update qty to restock
                    qty_to_restock -= new_bin_qty
                
                    # Update restock_data
                    mask = self.restock_data['sku'] == target_sku
                    if any(mask):
                        current_qty = self.restock_data.loc[mask, 'qty_in_system'].values[0]
                        new_qty_system = current_qty + new_bin_qty
                        self.restock_data.loc[mask, 'qty_in_system'] = new_qty_system
                        
                    if new_qty_system is not None:
                        self.logger.info(f"sku {target_sku} refilled, new qty in system: {new_qty_system}")
                    if new_qty_system is None:
                        self.logger.error(f"sku {sku} appears to be present in the restock data, but not in the mask")
                
        elif bin_count_cap == 0.5:  # For skus that need half bin
            new_bin_contents = []
            total_qty_added = 0
        
            new_bin_id = self._find_empty_bin()
            if new_bin_id is not None:
                for sku in self.restock_halfbin[:2]:  # Take only 2 SKUs to ensure we fill exactly half bins
                    new_bin_priority = self._get_last_priority(sku) + 1
                    new_bin_qty, _ = self._new_bin_qty(sku)
                    new_bin_contents.append((sku, new_bin_qty, new_bin_priority))
                    self.logger.debug(f"new bin is being prepared for {sku} in a 0.5 bin compartment and a qty of {new_bin_qty} and a priority {new_bin_priority}")
            
                self._overwrite_bin(new_bin_id, new_bin_contents)
                self.logger.info(f"empty bin {new_bin_id} now filled with skus {new_bin_contents}")
                self._pop_bin(new_bin_id)
            
                # Clear the restocked SKUs from the list
                self.restock_halfbin = self.restock_halfbin[2:] if len(self.restock_halfbin) > 2 else []

                # Update restock_data for this SKU
                mask = self.restock_data['sku'] == sku
                if any(mask):
                    current_qty = self.restock_data.loc[mask, 'qty_in_system'].values[0]
                    self.restock_data.loc[mask, 'qty_in_system'] = current_qty + new_bin_qty
        
        elif bin_count_cap == 0.25:  # For skus that need quarter bin
            new_bin_contents = []
        
            new_bin_id = self._find_empty_bin()
            if new_bin_id is not None:
                for sku in self.restock_quarterbin[:4]:  # Take only 4 SKUs to ensure we fill exactly quarter bins
                    new_bin_priority = self._get_last_priority(sku) + 1
                    new_bin_qty, _ = self._new_bin_qty(sku)
                    new_bin_contents.append((sku, new_bin_qty, new_bin_priority))
            
                
                # Find empty bin and add contents
            
                self._overwrite_bin(new_bin_id, new_bin_contents)
                self._pop_bin(new_bin_id)
                self.logger.info(f"empty bin {new_bin_id} now filled with skus {new_bin_contents}")
            
                # Clear the restocked SKUs from the list
                self.restock_quarterbin = self.restock_quarterbin[4:] if len(self.restock_quarterbin) > 4 else []

                # Update restock_data for this SKU
                mask = self.restock_data['sku'] == sku
                if any(mask):
                    current_qty = self.restock_data.loc[mask, 'qty_in_system'].values[0]
                    self.restock_data.loc[mask, 'qty_in_system'] = current_qty + new_bin_qty
            
        elif bin_count_cap == 0.125:  # For skus that need eighth bin
            new_bin_contents = []
        
            new_bin_id = self._find_empty_bin()
            if new_bin_id is not None:
                for sku in self.restock_eighthbin[:8]:  # Take only 8 SKUs to ensure we fill exactly eighth bins
                    new_bin_priority = self._get_last_priority(sku) + 1
                    new_bin_qty, _ = self._new_bin_qty(sku)
                    new_bin_contents.append((sku, new_bin_qty, new_bin_priority))  
            
                self._overwrite_bin(new_bin_id, new_bin_contents)
                self._pop_bin(new_bin_id)
                self.logger.info(f"empty bin {new_bin_id} now filled with skus {new_bin_contents}")
            
                # Clear the restocked SKUs from the list
                self.restock_eighthbin = self.restock_eighthbin[8:] if len(self.restock_eighthbin) > 8 else []

                # Update restock_data for this SKU
                mask = self.restock_data['sku'] == sku
                if any(mask):
                    current_qty = self.restock_data.loc[mask, 'qty_in_system'].values[0]
                    self.restock_data.loc[mask, 'qty_in_system'] = current_qty + new_bin_qty
        
        else:
            st.warning(f"_trigger restock issue for sku {target_sku} and compartment size: {bin_count_cap}")



    def _get_last_priority(self, target_sku) -> int:
        # Find lowest priority (highest #) bin for a given sku
        # returns the last priority value
        current_priority = 0
        for bin_id, compartment_size, skus in self.bins_list:
            for sku, qty, priority in skus:
                if sku == target_sku:
                    if priority > current_priority:
                        current_priority = priority
        return current_priority
    
    def _new_bin_qty(self, target_sku) -> int: 
        for index, row in self.restock_data.iterrows():
            sku = row['sku']
            qty_in_system = row['qty_in_system']
            full_qty = row['full_qty']
            if sku == target_sku:
                qty_to_restock = full_qty - qty_in_system
                return qty_to_restock, qty_in_system

            
    def _find_empty_bin(self)-> int:
        
        for bin_id, compartment_size, skus in self.bins_list:
            if all(pd.isna(sku) for sku, qty, priority in skus):
                self.logger.debug(f"empty bin found: {bin_id}")
                return bin_id
        # If no empty bin is found, return None
        st.session_state['allowable_empties_counter'] += 1
        self.logger.error(f"No empty bin found, instance {st.session_state['allowable_empties_counter']} of allowable {st.session_state['skip_empty_bin_allowance']}")
        st.warning(f"No more empty bins in the system instance {st.session_state['allowable_empties_counter']}")
        if st.session_state['allowable_empties_counter'] >= st.session_state['skip_empty_bin_allowance']:
            st.session_state['stop_run'] = True
            st.session_state['stop_reason'] = f"allowable # skips reached: {st.session_state['allowable_empties_counter']} / {st.session_state['skip_empty_bin_allowance']}"
        return None
    
        
    def _overwrite_bin(self, target_bin_id, bin_contents)-> None:
        updated_bins_list = []
        for bin_id, compartment_size, skus in self.bins_list:
            if bin_id == target_bin_id:
                updated_bins_list.append((target_bin_id, compartment_size, bin_contents))
            else:
                updated_bins_list.append((bin_id, compartment_size, skus))
        self.bins_list = updated_bins_list

    def _get_max_qty_per_bin(self, target_sku)-> int:
        for i, row in self.bincount_output_df.iterrows():
            sku = row['SKU']
            max_qty_per_bin = row['Qty Per Bin']
            if sku == target_sku:
                return max_qty_per_bin
            
    def update_system_stock(self, result, sku, qty_needed):
        restock_qty = result['restock_qty'].values[0]
        full_qty = result['full_qty'].values[0]
        qty_in_system = result['qty_in_system'].values[0]
        capped_bin_count = result['capped_bin_count'].values[0]
        force_restock_qty = result['force_restock_qty'].values[0]
        self.qty_in_system_pre_pick = qty_in_system
        next_empty_bin  = self._find_empty_bin()
        if next_empty_bin is None:
            self.logger.warning(f"out of empty bins, sku {sku} will not be restocked at this time.")
        elif next_empty_bin is not None:
            if qty_needed <= qty_in_system:
                self.sufficient_qty = True
                qty_in_system = qty_in_system - qty_needed
                self.qty_in_system_post_pick = qty_in_system
                self.logger.info(f"checking restock - sku {sku} qty in system after pick: {qty_in_system} with a restock level {restock_qty}")
                self.restock_data.loc[self.restock_data['sku'] == sku, 'qty_in_system'] = qty_in_system
                if qty_in_system <= force_restock_qty:
                    self.force_restock = True
                    self._check_refill(sku)
                elif qty_in_system <= restock_qty:
                    print(f"sku {sku} needs restock")
                    self.force_restock = False
                    self._check_refill(sku)
            elif qty_needed > qty_in_system:
                self.sufficient_qty = False
                self.logger.warning(f"sku {sku} requires {qty_needed} units, but only {qty_in_system} are in the AS. This line will be excluded.")
        else:
            self.logger.warning(f"something isn't right in the update system stock")

    def check_sku_fit_status(self, sku):
        """
        Check if a SKU is in the bincount_output dataframe and return its Fit status.
            
            Args:
                sku (str): The SKU to check
                bincount_output_df (pandas.DataFrame): DataFrame with 'sku' and 'Fit|No Fit' columns
                
            Returns:
                str: 'Fit', 'No Fit', or 'SKU not found'
        """
        # Check if SKU exists in the dataframe
        if sku in self.bincount_output_df['SKU'].values:
            # Get the corresponding 'Fit|No Fit' value
            fit_status = self.bincount_output_df.loc[self.bincount_output_df['SKU'] == sku, 'Fit|No Fit'].iloc[0]
            return fit_status
        else:
            return "SKU not found"
        
    def backup_ss(self):

        
        self.pick_orders_filtered = self.pick_orders[self.pick_orders['bin_id'].notna()]
        pick_orders_df = pd.DataFrame(self.pick_orders_filtered)
        pick_orders_output_csv = self.pick_orders_filtered.to_csv(index = False)
        st.session_state['pick_orders_df'] = pick_orders_df
        st.session_state['pick_orders_output_csv'] = pick_orders_output_csv


        st.session_state['insufficient_picks'] = self.track_insufficient_picks
        line_no_fits = len(self.non_fit_pick_orders)
        line_fits = len(pick_orders_df)
        lines_excluded = len(self.excluded_pick_orders)
        st.session_state['line_fits'] = line_fits
        st.session_state['line_no_fits'] = line_no_fits
        st.session_state['lines_excluded'] = lines_excluded
        st.session_state['total_input_lines'] = self.num_rows
        print("session state saved through backup_ss function")

    def debug_bins_list(self):
        for i, bin_entry in enumerate(self.bins_list):
            if len(bin_entry) != 3:
                print(f"Bin entry at index {i} has {len(bin_entry)} elements instead of 3: {bin_entry}")
