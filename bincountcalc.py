#!/usr/bin/env python3

from io import StringIO
from itertools import permutations

import streamlit as st
import numpy as np
import pandas as pd
import time


class BinCountCalculator:
    """Class used for calculating bin counts based on input parameters."""

    def __init__(self, inputs: dict, *, to_folder: bool = True) -> None:
        """Initialize the class with inputs and process the SKU master file.

        :param inputs: Dictionary of inputs from the UI
        :param to_folder: If one should write to folder
        """
        self.inputs = inputs
        self.errors: list[str] = []  # List to store errors
        self.to_folder = to_folder
        

        if validate_inputs(inputs, self.errors, to_folder=to_folder):
            skus = import_sku_file(inputs, self.errors)
            if skus is not None:
                self.skus = skus

    def _write_to_file(self) -> None:
        if self.to_folder:
            # Export to Excel
            output_path = f"{self.inputs['output_folder']}/{self.inputs['output_name']}.xlsx"
            self.skus.to_excel(output_path, sheet_name="SKUs", index=False)
        else:
            output = StringIO()
            self.skus.to_csv(output, index=False)
            output.seek(0)  # Move the pointer to the beginning of the buffer
            self.output = output.getvalue()

   
    def calculate_bin_count(self) -> None:
        """Performs bin count calculations and exports results to Excel."""
                
        # Metric conversion and vol calculation
        standardise_units(self.skus, self.inputs["sku_units"])

        # Map bin height and get compartment dimensions
        bin_height = get_bin_height(self.inputs["bin_type"])
        bindims = get_compartment_dimensions(bin_height, self.inputs["bin_weight_limit"])

        # Vectorize the quantity calculation function
        vqty_per_compartment = np.vectorize(qty_per_compartment, excluded=["bin_dims", "max_weight", "bin_utilization"])

        
        
        # Calculate quantities for each compartment
        for compartment, dims in bindims.iterrows():
            


            col_label = "Qty Per Bin" if compartment == 1 else f"Qty Per 1/{compartment} Bin"
            self.skus[col_label] = vqty_per_compartment(
                length=self.skus["Length (mm)"],
                width=self.skus["Width (mm)"],
                height=self.skus["Height (mm)"],
                weight=self.skus["Weight (kg)"],
                bin_dims=dims[["Length", "Width", "Height"]].values,
                max_weight=dims["Weight"],
                bin_utilization=self.inputs["bin_utilization"],
            )

        # Determine final compartment size and bin count
        max_compartments = self.inputs["max_compartments"]

        eight, four, half = 8, 4, 2
        conditions = [
            (max_compartments == eight)
            & (self.skus["Qty Per 1/8 Bin"] >= self.skus["Min Qty Per Bin"])
            & (self.skus["Qty Per 1/8 Bin"] >= self.skus["Qty Stored"]),
            (max_compartments >= four)
            & (self.skus["Qty Per 1/4 Bin"] >= self.skus["Min Qty Per Bin"])
            & (self.skus["Qty Per 1/4 Bin"] >= self.skus["Qty Stored"]),
            (max_compartments >= half)
            & (self.skus["Qty Per 1/2 Bin"] >= self.skus["Min Qty Per Bin"])
            & (self.skus["Qty Per 1/2 Bin"] >= self.skus["Qty Stored"]),
            self.skus["Qty Per Bin"] >= self.skus["Min Qty Per Bin"],
        ]
        compartment_sizes = [0.125, 0.25, 0.5, 1]  # Note 1 means one or more
        self.skus["Final Compartment Size"] = np.select(conditions, compartment_sizes, default=0)

        # Note: leads to overestimation because entire bins when more than 1 is required
        self.skus["Bin Count"] = np.where(
            self.skus["Final Compartment Size"] == 1,
            np.ceil(self.skus["Qty Stored"] / self.skus["Qty Per Bin"]),
            self.skus["Final Compartment Size"],
        )
       
        # Add the 'Capped Bin Count' column
        self.skus["Capped Bin Count"] = self.skus["Bin Count"].apply(lambda x: min(x, self.inputs['max_bins_per_sku']))

        
        # Add Fit/No Fit column
        no_dim = (self.skus[["Length (mm)", "Width (mm)", "Height (mm)", "Weight (kg)"]] <= 0).all(axis=1)
        no_fit = (self.skus["Qty Per Bin"] < self.skus["Min Qty Per Bin"]) | (self.skus["Qty Per Bin"] <= 0)
        self.skus["Fit|No Fit"] = np.select([no_dim, no_fit], ["No Dims", "No Fit"], default="Fit")
     
        #Sorts skus by Bin Count 
        self.skus = self.skus.sort_values(by='Bin Count', ascending= False)
        
        self._write_to_file()

        
        return self.skus

         
    
    def calculate_fill_metrics(self) -> None:
        """Calculates volume and weight fill for each compartment.

        Must always be called after calculate_bin_count.Used for analysis.
        """
        bin_height = get_bin_height(self.inputs["bin_type"])
        compartment_dimensions = get_compartment_dimensions(bin_height, self.inputs["bin_weight_limit"])

        compartment_dimensions["Compartment Volume"] = (
            compartment_dimensions["Length"] * compartment_dimensions["Width"] * compartment_dimensions["Height"]
        )

        # Compute volume and weight fill percentages for all compartments
        for compartment_id in compartment_dimensions.index:
            qty_col = "Qty Per Bin" if compartment_id == 1 else f"Qty Per 1/{compartment_id} Bin"
            volume_fill_col = "Volume Fill Bin" if compartment_id == 1 else f"Volume Fill 1/{compartment_id} Bin"
            weight_fill_col = "Weight Fill Bin" if compartment_id == 1 else f"Weight Fill 1/{compartment_id} Bin"

            compartment_volume = compartment_dimensions.at[compartment_id, "Compartment Volume"]
            max_weight = compartment_dimensions.at[compartment_id, "Weight"]

            # Compute volume and weight fill percentages
            self.skus[volume_fill_col] = (self.skus[qty_col] * self.skus["Cubic Vol (mm^3)"]) / compartment_volume
            self.skus[weight_fill_col] = (self.skus[qty_col] * self.skus["Weight (kg)"]) / max_weight

        size_to_index_map = {0.125: 8, 0.25: 4, 0.5: 2}
        self.skus["Compartment Index"] = self.skus["Final Compartment Size"].map(size_to_index_map)

        # Create a mapping for compartment volumes and weights
        volume_lookup = compartment_dimensions["Compartment Volume"].to_dict()
        weight_lookup = compartment_dimensions["Weight"].to_dict()

        # Map the values to the SKU dataframe
        self.skus["Compartment Volume"] = self.skus["Compartment Index"].map(volume_lookup)
        self.skus["Compartment Weight"] = self.skus["Compartment Index"].map(weight_lookup)

        # Calculate actual volume fill percentages
        self.skus["Volume Fill"] = np.where(
            self.skus["Final Compartment Size"] < 1,
            (self.skus["Qty Stored"] * self.skus["Cubic Vol (mm^3)"]) / self.skus["Compartment Volume"],
            self.skus["Volume Fill Bin"],
        )

        # Calculate actual weight fill percentages
        self.skus["Weight Fill"] = np.where(
            self.skus["Final Compartment Size"] < 1,
            (self.skus["Qty Stored"] * self.skus["Weight (kg)"]) / self.skus["Compartment Weight"],
            self.skus["Weight Fill Bin"],
        )

        # Remove temporary columns to keep the data clean
        self.skus.drop(
            columns=["Compartment Volume", "Compartment Weight", "Compartment Index"],
            inplace=True,
        )

        self._write_to_file()


def qty_per_compartment(
    length: float,
    width: float,
    height: float,
    weight: float,
    bin_dims: list[float],
    max_weight: float,
    bin_utilization: float,
) -> int:
    """Calculates the maximum quantity of SKUs that can fit in a compartment, vectorizeable."""
    max_qty = 0
    if all(dim > 0 for dim in [length, width, height]):
        # How many SKUs can be stacked in compartment - underestimate
        for orientation in permutations([length, width, height]):
            qty_stacked = (
                np.floor(bin_dims[0] / orientation[0])
                * np.floor(bin_dims[1] / orientation[1])
                * np.floor(bin_dims[2] / orientation[2])
            )
            max_qty = max(max_qty, qty_stacked)

        # Limit based on weight of SKUs
        if weight > 0:
            qty_limit_weight = np.floor(max_weight / weight)
            max_qty = min(max_qty, qty_limit_weight)

        # Reduce SKU count on volume
        vol_limit = bin_dims[0] * bin_dims[1] * bin_dims[2] * (bin_utilization / 100)
        qty_limit_vol = np.floor(vol_limit / (length * width * height))
        max_qty = min(max_qty, qty_limit_vol)

    # If missing dimentional data use only weight
    elif weight > 0:
        weight_limit = max_weight * (bin_utilization / 100)  # conservative meassure
        max_qty = np.floor(weight_limit / weight)

    return max_qty


def get_bin_height(bin_type: int) -> int:
    """Maps bin type to height."""
    bin_heights = {220: 202, 330: 312, 425: 404}
    return bin_heights[bin_type]


def validate_inputs(inputs: dict, errors: list[str], *, to_folder: bool) -> bool:
    """Validates initial inputs for required files and folders."""
    if inputs.get("sku_file") == "No file selected":
        errors.append("Error: Please select a SKU master .csv file.")
    if not inputs.get("output_name"):
        errors.append("Error: Output file name cannot be blank.")
    if to_folder and inputs.get("output_folder") == "No folder selected":
        errors.append("Error: Please select a folder for the output file.")
    return not bool(len(errors))


def import_sku_file(inputs: dict, errors: list[str]) -> pd.DataFrame | None:
    """Imports and processes the SKU master file, with a fallback for encoding issues."""
    try:
        # Attempt to read the file with the provided parameters
        skus = pd.read_csv(
            inputs["sku_file"],
            delimiter=inputs["sku_delimiter"],
            decimal=inputs["sku_decimal"],
            thousands=inputs.get("sku_thousands") or None,
            dtype={inputs["sku_cols"]["SKU"]: str},
        )
    except UnicodeDecodeError:
        # Fallback to 'mac_roman' encoding, some problem with mac to windows csv
        skus = pd.read_csv(
            inputs["sku_file"],
            encoding="mac_roman",
            delimiter=inputs["sku_delimiter"],
            decimal=inputs["sku_decimal"],
            thousands=inputs.get("sku_thousands") or None,
            dtype={inputs["sku_cols"]["SKU"]: str},
        )
    except Exception as e:
        errors.append(f"Error: Unable to import SKU file. Details: {e}")
        return None

    # Fill missing values, rename columns, and validate
    skus.fillna(0, inplace=True)
    skus.rename(columns=inputs["sku_cols"], inplace=True)
    validate_sku_columns(skus, inputs["sku_cols"].values(), errors)
    return skus


def validate_sku_columns(skus: pd.DataFrame, required_columns: list[str], errors: list[str]) -> None:
    """Validates and formats required SKU columns in the imported data."""
    missing_columns = [col for col in required_columns if col not in skus.columns]
    if missing_columns:
        errors.extend([f"Error: Missing required column '{col}' in SKU master." for col in missing_columns])
        return

    skus["SKU"] = skus["SKU"].str.upper()

    # Convert other columns to numeric
    numeric_columns = [col for col in required_columns if col != "SKU"]

    for c in numeric_columns:
        try:
            skus[c] = pd.to_numeric(skus[c])
        except ValueError:
            errors.append(f"Error: Column '{c}' contains non-numeric values.")


def standardise_units(skus: pd.DataFrame, sku_units: str) -> None:
    """Converts SKU dimensions and weights to metric units."""
    # Convert units if necessary
    if sku_units == "in / lb":
        skus.rename(
            columns={
                "Length": "Length (in)",
                "Width": "Width (in)",
                "Height": "Height (in)",
                "Weight": "Weight (lb)",
            },
            inplace=True,
        )
        skus["Length (mm)"] = skus["Length (in)"] * 25.4
        skus["Width (mm)"] = skus["Width (in)"] * 25.4
        skus["Height (mm)"] = skus["Height (in)"] * 25.4
        skus["Weight (kg)"] = skus["Weight (lb)"] * 0.453592
    else:
        skus.rename(
            columns={
                "Length": "Length (mm)",
                "Width": "Width (mm)",
                "Height": "Height (mm)",
                "Weight": "Weight (kg)",
            },
            inplace=True,
        )

    skus["Cubic Vol (mm^3)"] = skus["Length (mm)"] * skus["Width (mm)"] * skus["Height (mm)"]


def get_compartment_dimensions(bin_height: float, bin_weight_limit: int) -> pd.DataFrame:
    """Returns a DataFrame of compartment dimensions based on bin type."""
    compartments = [1, 2, 4, 8]
    weights = [bin_weight_limit / size for size in compartments]  # f.eks [30kg, 15kg, 7kg, 3.5kg]
    lengths = [603, 301, 301, 150]
    widths = [403, 403, 201, 201]
    heights = [bin_height] * 4

    return pd.DataFrame(
        {
            "Compartment": compartments,
            "Length": lengths,
            "Width": widths,
            "Height": heights,
            "Weight": weights,
        }
    ).set_index("Compartment")



