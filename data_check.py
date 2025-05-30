import pandas as pd
import streamlit as st
from datasets import MasterDataSets

class DataConsistencyChecker:
    """Class to validate data consistency across all DataFrames in the warehouse simulation"""
    
    @classmethod
    def validate_all(cls, context="", raise_on_error=False):
        """
        Run all consistency checks and return results
        
        Args:
            context: String describing when this check is running (e.g., "after pick operation")
            raise_on_error: If True, raises exception on first error found
            
        Returns:
            dict: Results of all checks with detailed error information
        """
        results = {
            'context': context,
            'all_passed': True,
            'errors': [],
            'warnings': [],
            'checks_run': []
        }
        
        # Run all individual checks
        checks = [
            cls._check_quantity_consistency,
            cls._check_priority_consistency,
            cls._check_bin_capacity_consistency,
            cls._check_empty_compartment_consistency,
            cls._check_stack_lookup_consistency,
            cls._check_data_types,
            cls._check_orphaned_records
        ]
        
        for check in checks:
            try:
                check_result = check()
                results['checks_run'].append(check_result['check_name'])
                
                if not check_result['passed']:
                    results['all_passed'] = False
                    results['errors'].extend(check_result['errors'])
                    
                results['warnings'].extend(check_result.get('warnings', []))
                
                if raise_on_error and not check_result['passed']:
                    raise ValueError(f"Data consistency check failed: {check_result['errors'][0]}")
                    
            except Exception as e:
                results['all_passed'] = False
                error_msg = f"Error running {check.__name__}: {str(e)}"
                results['errors'].append(error_msg)
                
                if raise_on_error:
                    raise
        
        # Log results
        cls._log_results(results)
        return results
    
    @classmethod
    def _check_quantity_consistency(cls):
        """Verify that sum of bin quantities equals sku system quantities"""
        result = {'check_name': 'Quantity Consistency', 'passed': True, 'errors': [], 'warnings': []}
        
        try:
            # Get all SKUs from sku_live_df
            for _, sku_row in MasterDataSets.sku_live_df.iterrows():
                sku = sku_row['sku']
                system_qty = sku_row['qty_in_system']
                
                # Sum quantities from all bins for this SKU
                bin_qty_sum = MasterDataSets.bin_content_live_df[
                    MasterDataSets.bin_content_live_df['sku'] == sku
                ]['qty_in_bin'].sum()
                
                if system_qty != bin_qty_sum:
                    result['passed'] = False
                    result['errors'].append(
                        f"SKU {sku}: System qty ({system_qty}) != Bin total ({bin_qty_sum})"
                    )
                    
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Exception in quantity check: {str(e)}")
            
        return result
    
    @classmethod
    def _check_priority_consistency(cls):
        """Verify priority bins are correctly assigned and no gaps exist"""
        result = {'check_name': 'Priority Consistency', 'passed': True, 'errors': [], 'warnings': []}
        
        try:
            for _, sku_row in MasterDataSets.sku_live_df.iterrows():
                sku = sku_row['sku']
                prio_bin = sku_row['prio_bin']
                
                # Get all bins for this SKU
                sku_bins = MasterDataSets.bin_content_live_df[
                    (MasterDataSets.bin_content_live_df['sku'] == sku) &
                    (MasterDataSets.bin_content_live_df['qty_in_bin'] > 0)
                ]
                
                if sku_bins.empty:
                    if pd.notna(prio_bin):
                        result['errors'].append(f"SKU {sku}: Has prio_bin {prio_bin} but no bins with qty > 0")
                        result['passed'] = False
                    continue
                
                # Check if priority 1 bin exists
                prio_1_bins = sku_bins[sku_bins['priority'] == 1]
                if prio_1_bins.empty:
                    result['passed'] = False
                    result['errors'].append(f"SKU {sku}: No priority 1 bin found")
                elif len(prio_1_bins) > 1:
                    result['passed'] = False
                    result['errors'].append(f"SKU {sku}: Multiple priority 1 bins found")
                else:
                    # Check if prio_bin matches actual priority 1 bin
                    actual_prio_bin = prio_1_bins.iloc[0]['bin_id']
                    if prio_bin != actual_prio_bin:
                        result['passed'] = False
                        result['errors'].append(
                            f"SKU {sku}: prio_bin ({prio_bin}) != actual priority 1 bin ({actual_prio_bin})"
                        )
                
                # Check for priority gaps and negative priorities
                priorities = sorted(sku_bins['priority'].dropna().unique())
                if priorities:
                    if min(priorities) < 1:
                        result['passed'] = False
                        result['errors'].append(f"SKU {sku}: Has negative or zero priority: {min(priorities)}")
                    
                    # Check for gaps in priority sequence
                    expected_priorities = list(range(1, len(priorities) + 1))
                    if priorities != expected_priorities:
                        result['warnings'].append(
                            f"SKU {sku}: Priority gaps detected. Expected {expected_priorities}, got {priorities}"
                        )
                        
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Exception in priority check: {str(e)}")
            
        return result
    
    @classmethod
    def _check_bin_capacity_consistency(cls):
        """Verify bins_capacity_df matches actual bin usage"""
        result = {'check_name': 'Bin Capacity Consistency', 'passed': True, 'errors': [], 'warnings': []}
        
        try:
            for _, capacity_row in MasterDataSets.bins_capacity_df.iterrows():
                bin_id = capacity_row['bin_id']
                reported_full_compartments = capacity_row['num_full_compartments']
                
                # Count actual full compartments
                actual_full_compartments = len(MasterDataSets.bin_content_live_df[
                    (MasterDataSets.bin_content_live_df['bin_id'] == bin_id) &
                    (MasterDataSets.bin_content_live_df['sku'].notna()) &
                    (MasterDataSets.bin_content_live_df['sku'] != '') &
                    (MasterDataSets.bin_content_live_df['qty_in_bin'] > 0)
                ])
                
                if reported_full_compartments != actual_full_compartments:
                    result['passed'] = False
                    result['errors'].append(
                        f"Bin {bin_id}: Reported full compartments ({reported_full_compartments}) != "
                        f"Actual full compartments ({actual_full_compartments})"
                    )
                    
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Exception in bin capacity check: {str(e)}")
            
        return result
    
    @classmethod
    def _check_empty_compartment_consistency(cls):
        """Verify empty compartments are properly marked"""
        result = {'check_name': 'Empty Compartment Consistency', 'passed': True, 'errors': [], 'warnings': []}
        
        try:
            # Find compartments that should be empty (qty = 0)
            zero_qty_compartments = MasterDataSets.bin_content_live_df[
                MasterDataSets.bin_content_live_df['qty_in_bin'] == 0
            ]
            
            for _, comp in zero_qty_compartments.iterrows():
                sku = comp['sku']
                priority = comp['priority']
                
                # Check if SKU and priority are properly cleared
                if pd.notna(sku) and sku != '':
                    result['warnings'].append(
                        f"Bin {comp['bin_id']} Compartment {comp['compartment_id']}: "
                        f"Has qty=0 but SKU still set to '{sku}'"
                    )
                
                if pd.notna(priority) and priority != '':
                    result['warnings'].append(
                        f"Bin {comp['bin_id']} Compartment {comp['compartment_id']}: "
                        f"Has qty=0 but priority still set to '{priority}'"
                    )
                    
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Exception in empty compartment check: {str(e)}")
            
        return result
    
    @classmethod
    def _check_stack_lookup_consistency(cls):
        """Verify stack lookup table matches actual bin assignments"""
        result = {'check_name': 'Stack Lookup Consistency', 'passed': True, 'errors': [], 'warnings': []}
        
        try:
            # Get all bin_ids from bin_content_live_df
            all_bins = set(MasterDataSets.bin_content_live_df['bin_id'].unique())
            
            # Get all bin_ids from stack lookup
            lookup_bins = set(MasterDataSets.stacks_lookup_df.index.unique())
            
            # Check for bins missing from lookup
            missing_from_lookup = all_bins - lookup_bins
            if missing_from_lookup:
                result['passed'] = False
                result['errors'].append(f"Bins missing from stack lookup: {missing_from_lookup}")
            
            # Check for orphaned entries in lookup
            orphaned_in_lookup = lookup_bins - all_bins
            if orphaned_in_lookup:
                result['warnings'].append(f"Orphaned bins in stack lookup: {orphaned_in_lookup}")
                
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Exception in stack lookup check: {str(e)}")
            
        return result
    
    @classmethod
    def _check_data_types(cls):
        """Verify data types are correct in all DataFrames"""
        result = {'check_name': 'Data Type Consistency', 'passed': True, 'errors': [], 'warnings': []}
        
        try:
            # Check sku_live_df
            qty_negatives = MasterDataSets.sku_live_df[MasterDataSets.sku_live_df['qty_in_system'] < 0]
            if not qty_negatives.empty:
                result['passed'] = False
                result['errors'].append(f"Negative quantities in system: {qty_negatives['sku'].tolist()}")
            
            # Check bin_content_live_df
            bin_qty_negatives = MasterDataSets.bin_content_live_df[MasterDataSets.bin_content_live_df['qty_in_bin'] < 0]
            if not bin_qty_negatives.empty:
                result['passed'] = False
                result['errors'].append(f"Negative bin quantities found in bins: {bin_qty_negatives['bin_id'].tolist()}")
            
            # Check for invalid compartment sizes
            valid_sizes = {1.0, 0.5, 0.25, 0.125}
            invalid_sizes = MasterDataSets.bin_content_live_df[
                ~MasterDataSets.bin_content_live_df['compartment_size'].isin(valid_sizes)
            ]
            if not invalid_sizes.empty:
                result['passed'] = False
                result['errors'].append(f"Invalid compartment sizes found: {invalid_sizes['compartment_size'].unique()}")
                
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Exception in data type check: {str(e)}")
            
        return result
    
    @classmethod
    def _check_orphaned_records(cls):
        """Check for orphaned records between DataFrames"""
        result = {'check_name': 'Orphaned Records', 'passed': True, 'errors': [], 'warnings': []}
        
        try:
            # SKUs in bin_content_live_df but not in sku_live_df
            bin_skus = set(MasterDataSets.bin_content_live_df['sku'].dropna().unique())
            bin_skus.discard('')  # Remove empty strings
            
            system_skus = set(MasterDataSets.sku_live_df['sku'].unique())
            
            orphaned_skus = bin_skus - system_skus
            if orphaned_skus:
                result['passed'] = False
                result['errors'].append(f"SKUs in bins but not in system: {orphaned_skus}")
                
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Exception in orphaned records check: {str(e)}")
            
        return result
    
    @classmethod
    def _log_results(cls, results):
        """Log the results appropriately"""
        if results['all_passed']:
            print(f"✅ Data consistency check PASSED ({results['context']})")
            if results['warnings']:
                print(f"⚠️  {len(results['warnings'])} warnings found")
        else:
            print(f"❌ Data consistency check FAILED ({results['context']})")
            print(f"Found {len(results['errors'])} errors")
            
        # Log to Streamlit if available
        try:
            if results['all_passed']:
                if results['warnings']:
                    st.warning(f"Data consistency check passed with {len(results['warnings'])} warnings")
                else:
                    st.success("Data consistency check passed")
            else:
                st.error(f"Data consistency check failed with {len(results['errors'])} errors")
                with st.expander("View Errors"):
                    for error in results['errors']:
                        st.text(error)
        except:
            pass  # Streamlit not available
    
    @classmethod
    def quick_check(cls, context=""):
        """Run a quick subset of checks for frequent validation"""
        result = cls._check_quantity_consistency()
        prio_result = cls._check_priority_consistency()
        
        all_passed = result['passed'] and prio_result['passed']
        
        if not all_passed:
            print(f"❌ Quick consistency check FAILED ({context})")
            for error in result['errors'] + prio_result['errors']:
                print(f"  - {error}")
        
        return all_passed
    
    @classmethod
    def minimal_check(cls, context=""):
        """Ultra-fast check for high-frequency validation (every 1000 lines)"""
        try:
            # Just check a few critical items that are fast to compute
            errors = []
            
            # 1. Quick negative quantity check
            neg_system_qty = (MasterDataSets.sku_live_df['qty_in_system'] < 0).any()
            if neg_system_qty:
                errors.append("Negative system quantities detected")
            
            neg_bin_qty = (MasterDataSets.bin_content_live_df['qty_in_bin'] < 0).any()
            if neg_bin_qty:
                errors.append("Negative bin quantities detected")
            
            # 2. Quick check that we have some data (catch major corruption)
            if len(MasterDataSets.sku_live_df) == 0:
                errors.append("SKU dataframe is empty")
            
            if len(MasterDataSets.bin_content_live_df) == 0:
                errors.append("Bin content dataframe is empty")
            
            # 3. Quick check for priority 1 bins existence (sample a few SKUs)
            sample_skus = MasterDataSets.sku_live_df.head(5)['sku']  # Just check first 5 SKUs
            for sku in sample_skus:
                prio_1_exists = ((MasterDataSets.bin_content_live_df['sku'] == sku) & 
                               (MasterDataSets.bin_content_live_df['priority'] == 1)).any()
                sku_has_qty = MasterDataSets.sku_live_df[MasterDataSets.sku_live_df['sku'] == sku]['qty_in_system'].iloc[0] > 0
                
                if sku_has_qty and not prio_1_exists:
                    errors.append(f"SKU {sku} missing priority 1 bin")
                    break  # Just flag first occurrence
            
            if errors:
                print(f"❌ Minimal consistency check FAILED ({context}): {'; '.join(errors)}")
                return False
            else:
                return True
                
        except Exception as e:
            print(f"❌ Minimal consistency check ERROR ({context}): {str(e)}")
            return False
    
    @classmethod
    def adaptive_check(cls, iteration, context=""):
        """
        Adaptive checking strategy:
        - Every 1000: minimal_check (very fast)
        - Every 10000: quick_check (medium speed)  
        - Every 50000: full validation (comprehensive)
        """
        if iteration % 50000 == 0:
            return cls.validate_all(f"{context} - full check at {iteration}")['all_passed']
        elif iteration % 10000 == 0:
            return cls.quick_check(f"{context} - quick check at {iteration}")
        elif iteration % 1000 == 0:
            return cls.minimal_check(f"{context} - minimal check at {iteration}")
        else:
            return True  # No check needed


# Usage examples and when to run checks:

def add_consistency_checks_to_simulation():
    """
    Example of how to integrate consistency checks into your simulation
    """
    
    # 1. Add to critical points in simulation.py:
    
    # After initialization (add to Sim.__init__ or _run start)
    DataConsistencyChecker.validate_all("simulation initialization")
    
    # After each major operation (add after pick operations)
    # DataConsistencyChecker.quick_check("after pick operation")
    
    # Before and after restock operations
    # DataConsistencyChecker.validate_all("before restock")
    # DataConsistencyChecker.validate_all("after restock") 
    
    # Before and after consolidation
    # DataConsistencyChecker.validate_all("before consolidation")
    # DataConsistencyChecker.validate_all("after consolidation")
    
    # At regular intervals during long simulations
    # if i % 1000 == 0:  # Every 1000 orders
    #     DataConsistencyChecker.quick_check(f"order {i}")


# RECOMMENDED INTEGRATION FOR YOUR SESSION STATE BACKUP:

"""
PERFORMANCE-OPTIMIZED INTEGRATION:

In your simulation.py _run method, replace your current session state backup section:

# Old way (every 1000 lines):
if i % st.session_state['save_interval'] == 0 and i is not 0:

# New way (adaptive checking):
if i % st.session_state['save_interval'] == 0 and i is not 0:
    # Your existing session state backup code here...
    
    # Add adaptive consistency check
    data_ok = DataConsistencyChecker.adaptive_check(i, "session backup")
    if not data_ok:
        st.session_state['data_consistency_error'] = True
        st.session_state['error_at_line'] = i
        # Optionally stop simulation or flag for user attention

PERFORMANCE IMPACT ESTIMATES:
- minimal_check (every 1000): ~0.1-0.5ms per check
- quick_check (every 10000): ~2-10ms per check  
- full validation (every 50000): ~50-200ms per check

For 150K lines, total overhead: ~150ms (negligible)

ALTERNATIVE - Just use minimal_check every 1000:
if i % st.session_state['save_interval'] == 0 and i is not 0:
    # Your session state backup
    data_ok = DataConsistencyChecker.minimal_check(f"line {i}")
    st.session_state['last_data_check'] = data_ok
"""