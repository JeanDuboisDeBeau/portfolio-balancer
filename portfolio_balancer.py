#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Portfolio Balancer

This script helps to rebalance your portfolio according to a target allocation.
Author: Matthieu DUFLOT
License: MIT
"""

import pandas as pd
from pulp import (
    LpProblem, LpVariable, LpMinimize, lpSum,
    LpBinary, LpInteger, LpContinuous, PULP_CBC_CMD
)

# Load data from a CSV file
# Ensure that the CSV file 'portfolio.csv' contains the following columns:
# 'Asset', 'Quantity', 'Price', 'Target Allocation'
portfolio_df = pd.read_csv('portfolio.csv')

# Convert target allocation percentages to proportions (between 0 and 1)
portfolio_df['Target Allocation'] = portfolio_df['Target Allocation'] / 100

# Check that the sum of target allocations equals 1 (100%)
if not abs(portfolio_df['Target Allocation'].sum() - 1.0) < 1e-6:
    raise ValueError("The sum of the target allocations must equal 100%.")

# Ask the user for the total amount to invest and the maximum number of transactions
total_amount = float(input("Please enter the total amount to invest (€): "))
max_transactions = int(input("Please enter the maximum number of transactions: "))

# Extract information from the current portfolio
portfolio_df['Value'] = portfolio_df['Quantity'] * portfolio_df['Price']
portfolio_value = portfolio_df['Value'].sum()
portfolio_df['Current Weight'] = portfolio_df['Value'] / portfolio_value

# Calculate the total target portfolio value
total_target_value = portfolio_value + total_amount

# Store old quantities and weights for comparison
portfolio_df['Old Quantity'] = portfolio_df['Quantity']
portfolio_df['Old Weight'] = portfolio_df['Current Weight']

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
    print("No optimal solution was found. Please check the constraints and data.")
    exit()

# Calculate total invested amount
total_invested = sum([
    int(vars_purchase[portfolio_df.loc[i, 'Asset']].varValue) * portfolio_df.loc[i, 'Price']
    for i in portfolio_df.index
])

# Ensure that the total invested does not exceed the total amount
if total_invested > total_amount + 1e-6:  # Allowing a small numerical tolerance
    print(f"\nWarning: Total invested amount ({total_invested:.2f} €) exceeds the available funds ({total_amount:.2f} €).")
    print("Adjusting the investment amounts to not exceed the available funds.")
    # This should not happen due to the constraints, but we include a check just in case
    exit()

# Display the purchase orders
print("\nOrders to place to minimize deviation from the target allocation:")
if total_invested == 0:
    print("No purchases are recommended with the given constraints.")
else:
    for i in portfolio_df.index:
        asset = portfolio_df.loc[i, 'Asset']
        purchase_quantity = int(vars_purchase[asset].varValue)
        if purchase_quantity > 0:
            investment_cost = purchase_quantity * portfolio_df.loc[i, 'Price']
            print(f"- Buy {purchase_quantity} shares of {asset} for {investment_cost:.2f} €")

# Display the total invested amount and the proportion invested
percentage_invested = (total_invested / total_amount) * 100
print(f"\nTotal amount invested: {total_invested:.2f} € ({percentage_invested:.2f}% of the amount to invest)")

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
display_df['Target Allocation (%)'] = display_df['Target Allocation'] * 100

# Calculate deviation from target allocation
display_df['Deviation (%)'] = abs(display_df['New Weight (%)'] - display_df['Target Allocation (%)'])

# Calculate the allocation index (1 - sum of absolute deviations / 200)
allocation_index = 1 - display_df['Deviation (%)'].sum() / 200

# Configure number formatting
pd.options.display.float_format = '{:.2f}'.format

# Reorder columns for better presentation
display_df = display_df[[
    'Asset', 'Old Quantity', 'New Quantity', 'Change Symbol',
    'Old Weight (%)', 'New Weight (%)', 'Target Allocation (%)', 'Deviation (%)'
]]

# Rename columns for better readability
display_df.columns = [
    'Asset', 'Old Quantity', 'New Quantity', 'Change',
    'Old Weight (%)', 'New Weight (%)', 'Target Allocation (%)', 'Deviation (%)'
]

# Display the comparison
print("\nComparison of old and new positions:")
print(display_df.to_string(index=False))

# Display the allocation index
print(f"\nAllocation index: {allocation_index:.4f} (1 indicates a perfect match with the target allocation)")
