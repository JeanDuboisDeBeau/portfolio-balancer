#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Portfolio Balancer with GUI

This script helps to rebalance your portfolio according to a target allocation.
Author: Matthieu DUFLOT
License: MIT
"""

import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
from pulp import (
    LpProblem, LpVariable, LpMinimize, lpSum,
    LpBinary, LpInteger, LpContinuous, PULP_CBC_CMD
)
import os

def portfolio_balancer(portfolio_file, total_amount, max_transactions):
    # Load data from a CSV file
    portfolio_df = pd.read_csv(portfolio_file)

    # Convert target allocation percentages to proportions (between 0 and 1)
    portfolio_df['Target Allocation'] = portfolio_df['Target Allocation'] / 100

    # Check that the sum of target allocations equals 1 (100%)
    if not abs(portfolio_df['Target Allocation'].sum() - 1.0) < 1e-6:
        raise ValueError("The sum of the target allocations must equal 100%.")

    # Extract information from the current portfolio
    portfolio_df['Value'] = portfolio_df['Quantity'] * portfolio_df['Price']
    portfolio_value = portfolio_df['Value'].sum()
    portfolio_df['Current Weight'] = portfolio_df['Value'] / portfolio_value

    # Calculate the total target portfolio value
    total_target_value = portfolio_value + total_amount

    # Store old quantities and weights for comparison
    portfolio_df['Old Quantity'] = portfolio_df['Quantity']
    portfolio_df['Old Weight'] = portfolio_df['Current Weight']

    # Calculate deviation before rebalancing
    portfolio_df['Deviation Before (%)'] = abs(portfolio_df['Old Weight'] * 100 - portfolio_df['Target Allocation'] * 100)

    # Initialize the optimization problem
    prob = LpProblem("Portfolio_Rebalancing", LpMinimize)

    # Decision variables: number of shares to purchase for each asset
    vars_purchase = LpVariable.dicts(
        "Purchase",
        portfolio_df['Asset'],
        lowBound=0,
        cat=LpInteger
    )

    # Binary variables to count the number of transactions
    vars_transaction = LpVariable.dicts(
        "Transaction",
        portfolio_df['Asset'],
        cat=LpBinary
    )

    # Variables for positive and negative deviations
    dev_plus = LpVariable.dicts(
        "Deviation_Plus",
        portfolio_df['Asset'],
        lowBound=0,
        cat=LpContinuous
    )

    dev_minus = LpVariable.dicts(
        "Deviation_Minus",
        portfolio_df['Asset'],
        lowBound=0,
        cat=LpContinuous
    )

    # Objective function: minimize the sum of absolute deviations
    prob += lpSum([dev_plus[asset] + dev_minus[asset] for asset in portfolio_df['Asset']])

    # Constraints:

    # 1. Total amount invested must not exceed the available amount
    prob += lpSum([
        vars_purchase[portfolio_df.loc[i, 'Asset']] * portfolio_df.loc[i, 'Price']
        for i in portfolio_df.index
    ]) <= total_amount

    # 2. Limit the number of transactions
    prob += lpSum([vars_transaction[asset] for asset in portfolio_df['Asset']]) <= max_transactions

    # 3. Link purchase variables to transaction binary variables
    M = 1e6  # A large number for constraint relaxation
    for i in portfolio_df.index:
        asset = portfolio_df.loc[i, 'Asset']
        # If we purchase at least one share, the transaction is counted
        prob += vars_purchase[asset] >= vars_transaction[asset]
        # If we do not purchase, the purchase variable is zero
        prob += vars_purchase[asset] <= vars_transaction[asset] * M

    # 4. Calculate deviations from target allocation
    for i in portfolio_df.index:
        asset = portfolio_df.loc[i, 'Asset']
        current_value = portfolio_df.loc[i, 'Value']
        price = portfolio_df.loc[i, 'Price']
        target_weight = portfolio_df.loc[i, 'Target Allocation']

        new_value = current_value + vars_purchase[asset] * price

        # Equation:
        # new_value - total_target_value * target_weight == total_target_value * (dev_plus[asset] - dev_minus[asset])
        prob += new_value - total_target_value * target_weight == total_target_value * (
            dev_plus[asset] - dev_minus[asset])

    # Solve the problem
    prob.solve(PULP_CBC_CMD(msg=False))

    # Check if an optimal solution was found
    if prob.status != 1:
        return "No optimal solution was found. Please check the constraints and data."

    # Calculate total invested amount
    total_invested = sum([
        int(vars_purchase[portfolio_df.loc[i, 'Asset']].varValue) * portfolio_df.loc[i, 'Price']
        for i in portfolio_df.index
    ])

    # Ensure that the total invested does not exceed the total amount
    if total_invested > total_amount + 1e-6:  # Allowing a small numerical tolerance
        return (f"Warning: Total invested amount ({total_invested:.2f} €) exceeds the available funds "
                f"({total_amount:.2f} €). Adjusting the investment amounts to not exceed the available funds.")

    # Prepare the results
    results = ""

    # Purchase orders
    results += "\nOrders to place to minimize deviation from the target allocation:\n"
    if total_invested == 0:
        results += "No purchases are recommended with the given constraints.\n"
    else:
        for i in portfolio_df.index:
            asset = portfolio_df.loc[i, 'Asset']
            purchase_quantity = int(vars_purchase[asset].varValue)
            if purchase_quantity > 0:
                investment_cost = purchase_quantity * portfolio_df.loc[i, 'Price']
                results += f"- Buy {purchase_quantity} shares of {asset} for {investment_cost:.2f} €\n"

    # Total invested amount and proportion invested
    percentage_invested = (total_invested / total_amount) * 100
    results += (f"\nTotal amount invested: {total_invested:.2f} € "
                f"({percentage_invested:.2f}% of the amount to invest)\n")

    # Calculate and display the new allocation
    portfolio_df['New Quantity'] = portfolio_df['Quantity'] + [
        int(vars_purchase[asset].varValue) for asset in portfolio_df['Asset']
    ]
    portfolio_df['New Value'] = portfolio_df['New Quantity'] * portfolio_df['Price']
    new_portfolio_value = portfolio_df['New Value'].sum()
    portfolio_df['New Weight'] = portfolio_df['New Value'] / new_portfolio_value

    # Compare old and new quantities and weights
    portfolio_df['Quantity Changed'] = portfolio_df['New Quantity'] != portfolio_df['Old Quantity']
    portfolio_df['Change Symbol'] = portfolio_df['Quantity Changed'].apply(lambda x: '→' if x else '')

    # Prepare the DataFrame for display by making a copy to avoid warnings
    display_df = portfolio_df[[
        'Asset', 'Old Quantity', 'New Quantity', 'Change Symbol',
        'Old Weight', 'New Weight', 'Target Allocation'
    ]].copy()

    # Convert weights to percentages
    display_df['Old Weight (%)'] = display_df['Old Weight'] * 100
    display_df['New Weight (%)'] = display_df['New Weight'] * 100
    display_df['Target Allocation (%)'] = portfolio_df['Target Allocation'] * 100

    # Calculate deviation from target allocation after rebalancing
    display_df['Deviation After (%)'] = abs(display_df['New Weight (%)'] - display_df['Target Allocation (%)'])

    # Calculate allocation indices
    allocation_index_before = 1 - portfolio_df['Deviation Before (%)'].sum() / 200
    allocation_index_after = 1 - display_df['Deviation After (%)'].sum() / 200

    # Reorder columns for better presentation
    display_df = display_df[[
        'Asset', 'Old Quantity', 'New Quantity', 'Change Symbol',
        'Old Weight (%)', 'New Weight (%)', 'Target Allocation (%)', 'Deviation After (%)'
    ]]

    # Rename columns for better readability
    display_df.columns = [
        'Asset', 'Old Qty', 'New Qty', 'Change',
        'Old Weight (%)', 'New Weight (%)', 'Target Allocation (%)', 'Deviation After (%)'
    ]

    # Convert the DataFrame to a string
    results += "\nComparison of old and new positions:\n"
    results += display_df.to_string(index=False)
    results += (f"\n\nPrevious Allocation Index: {allocation_index_before:.4f}")
    results += (f"\nNew Allocation Index: {allocation_index_after:.4f}")
    results += "\n(An allocation index closer to 1 indicates a better match with the target allocation)"

    return results

# GUI Application
def run_gui():
    root = tk.Tk()
    root.title("Portfolio Balancer")

    # Desired window size
    desired_width = 1200
    desired_height = 800

    # Get screen size
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    if desired_width <= screen_width and desired_height <= screen_height:
        # Center the window
        x = (screen_width - desired_width) // 2
        y = (screen_height - desired_height) // 2
        root.geometry(f"{desired_width}x{desired_height}+{x}+{y}")
    else:
        # Make the window full screen if it doesn't fit
        root.geometry(f"{screen_width}x{screen_height}+0+0")

    # Define functions before they are used
    # Portfolio file selection function
    def select_file():
        file_path = filedialog.askopenfilename(
            title="Select Portfolio CSV File",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        portfolio_entry.delete(0, tk.END)
        portfolio_entry.insert(0, file_path)

    # Run the optimization
    def run_optimization():
        portfolio_file = portfolio_entry.get()
        total_amount = amount_entry.get()
        max_transactions = transactions_entry.get()

        if not os.path.isfile(portfolio_file):
            messagebox.showerror("Error", "Please select a valid portfolio CSV file.")
            return

        try:
            total_amount = float(total_amount)
            max_transactions = int(max_transactions)
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values for amount and transactions.")
            return

        try:
            results = portfolio_balancer(portfolio_file, total_amount, max_transactions)
            results_text.config(state=tk.NORMAL)  # Allow editing to update the text
            results_text.delete(1.0, tk.END)
            results_text.insert(tk.END, results)
            results_text.config(state=tk.DISABLED)  # Disable editing again
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # Create the main frames
    upper_frame = tk.Frame(root)
    upper_frame.pack(fill=tk.X, padx=10, pady=10)

    left_frame = tk.Frame(upper_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.Y)

    right_frame = tk.Frame(upper_frame)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    # Left Frame - Input Fields and Buttons

    # Portfolio file input
    portfolio_label = tk.Label(left_frame, text="Portfolio CSV File:")
    portfolio_label.pack(pady=5, anchor='w')
    portfolio_frame = tk.Frame(left_frame)
    portfolio_frame.pack()
    portfolio_entry = tk.Entry(portfolio_frame, width=50)
    portfolio_entry.pack(side=tk.LEFT)
    portfolio_button = tk.Button(portfolio_frame, text="Browse", command=select_file)
    portfolio_button.pack(side=tk.LEFT, padx=5)

    # Total amount input
    amount_label = tk.Label(left_frame, text="Total Amount to Invest (€):")
    amount_label.pack(pady=5, anchor='w')
    amount_entry = tk.Entry(left_frame, width=20)
    amount_entry.pack()

    # Max transactions input
    transactions_label = tk.Label(left_frame, text="Maximum Number of Transactions:")
    transactions_label.pack(pady=5, anchor='w')
    transactions_entry = tk.Entry(left_frame, width=20)
    transactions_entry.pack()

    # Run button
    run_button = tk.Button(left_frame, text="Run Optimization", command=run_optimization)
    run_button.pack(pady=10)

    # Right Frame - Instructions
    instructions_label = tk.Label(right_frame, text="Instructions:", font=('Arial', 12, 'bold'))
    instructions_label.pack(anchor='nw')
    instructions_text = tk.Text(right_frame, wrap=tk.WORD, width=60, height=18)
    instructions_text.pack(pady=5, fill=tk.BOTH, expand=True)

    instructions = (
        "Please prepare your portfolio CSV file with the following columns:\n\n"
        "1. Asset: The name or ticker of the asset.\n"
        "2. Quantity: The number of shares currently held.\n"
        "3. Price: The current price per share.\n"
        "4. Target Allocation: Desired percentage alloc. for the asset (should sum to 100%).\n\n"
        "Example CSV format:\n"
        "Asset,Quantity,Price,Target Allocation\n"
        "Asset A,10,100,50\n"
        "Asset B,5,200,30\n"
        "Asset C,8,150,20\n\n"
        "Instructions:\n"
        "- Ensure that the sum of 'Target Allocation' percentages equals 100%.\n"
        "- Fill in the 'Total Amount to Invest' with the amount you wish to allocate.\n"
        "- Specify the 'Maximum Number of Transactions' you're willing to make.\n"
        "- Click 'Run Optimization' to get the recommended purchases."
    )
    instructions_text.insert(tk.END, instructions)
    instructions_text.config(state=tk.DISABLED, bg='lightgray')

    # Results display
    results_label = tk.Label(root, text="Results:")
    results_label.pack()
    results_text = tk.Text(root, wrap=tk.WORD, width=140, height=25)
    results_text.pack(pady=5)
    results_text.config(state=tk.DISABLED)

    root.mainloop()

if __name__ == "__main__":
    run_gui()
