import pandas as pd
import numpy as np
import random
import datetime

# Load all CSV files
open_workorders = pd.read_csv('openworkorder.csv')
routing = pd.read_csv('routing.csv')
routing_lines = pd.read_csv('routinglines.csv')
product = pd.read_csv('product.csv')

print("Files loaded successfully")

# Filter out workorders older than 3/22/2025
reference_date = datetime.datetime(2025, 3, 22)
open_workorders['ScheduleDate'] = pd.to_datetime(open_workorders['ScheduleDate'])
open_workorders = open_workorders[open_workorders['ScheduleDate'] >= reference_date]

print(f"Filtered to {len(open_workorders)} workorders after 3/22/2025")

# Create empty dataframe for new_jobs
new_jobs = []

# Join tables to get all required information
for _, wo in open_workorders.iterrows():
    # Get routing for this work order
    route_matches = routing[routing['RouteCode'] == wo['RouteCode']]

    if len(route_matches) == 0:
        print(f"Warning: No routing found for WO {wo['Wono']} with RouteCode {wo['RouteCode']}")
        continue

    # Get product information from routing table
    product_no = route_matches['ProductNo'].iloc[0]
    product_info = product[product['ProductNo'] == product_no]

    if len(product_info) == 0:
        print(f"Warning: No product found for ProductNo {product_no}")
        continue

    # Get routing lines (operations/tasks)
    route_lines = routing_lines[
        (routing_lines['RoutingCode'] == wo['RouteCode']) &
        (routing_lines['Active'] == 1)
        ].sort_values('Sequence')

    if len(route_lines) == 0:
        print(f"Warning: No active routing lines found for RouteCode {wo['RouteCode']}")
        continue

    # Calculate due date in minutes from 3/21/2025
    reference_date_for_due = datetime.datetime(2025, 3, 21)
    due_minutes = int((wo['ScheduleDate'] - reference_date_for_due).total_seconds() / 60)

    # For each task (routing line), create a job record
    for _, rl in route_lines.iterrows():
        # Calculate processing time based on formula
        setup_minutes = product_info['SetUpMinutes'].iloc[0]
        production_minutes = product_info['ProductionMinutes'].iloc[0]
        casting_lot_size = product_info['CostingLotSize'].iloc[0]
        wo_quantity = wo['WoQuantity']

        # Calculate proc time: (wo_quantity / casting_lot_size) * production_minutes
        # Handle division by zero or unusual values
        if casting_lot_size == 0 or production_minutes == 0:
            proc_time = 10  # Default value if division is impossible
        else:
            proc_time = int((wo_quantity / casting_lot_size) * production_minutes)
            proc_time = max(1, proc_time)  # Ensure minimum proc time of 1

        # Determine dwell time (10% of proc time for 20% of records)
        dwell = int(proc_time * 0.1) if random.random() < 0.2 else 0

        # Create job record
        job_record = {
            'JobNumber': wo['Wono'],
            'TaskID': rl['Sequence'],
            'MachineOptions': rl['Workcenter'],
            'ProcTime': proc_time,
            'Slack': 10,  # Constant as specified
            'Setup': setup_minutes,
            'Due': due_minutes,
            'Priority': 5,  # Constant as specified
            'Dwell': dwell,
            'Release': 0,  # Constant as specified
            'JobPreempt': False,
            'TaskPreempt': False,
            'MinSplitJob': 0,
            'MinSplitTask': 0,
            'ReleaseThreshold': 0.25,  # Static value as specified
            'MustDo': '',  # No mustdo as specified
            'CustomerWeight': 5,  # Constant as specified
            'IsRush': False,
            'ToolID': 1,  # Default value as specified
            'StateID': 1,  # Default value as specified
            'ProductNo': product_no,  # From routing table
            'ScheduleDate': wo['ScheduleDate']  # Keep original date for grouping
        }

        new_jobs.append(job_record)

# Convert to DataFrame
new_jobs_df = pd.DataFrame(new_jobs)

# Ensure proper formatting
new_jobs_df['JobPreempt'] = new_jobs_df['JobPreempt'].map({True: 'TRUE', False: 'FALSE'})
new_jobs_df['TaskPreempt'] = new_jobs_df['TaskPreempt'].map({True: 'TRUE', False: 'FALSE'})
new_jobs_df['IsRush'] = new_jobs_df['IsRush'].map({True: 'TRUE', False: 'FALSE'})

# Save original ungrouped data
new_jobs_df_for_save = new_jobs_df.drop('ScheduleDate', axis=1)
new_jobs_df_for_save.to_csv('new_jobst.csv', index=False)
print(f"Created {len(new_jobs_df)} job records")
print("Saved to new_jobst.csv")

# Now create grouped version
print("\nCreating grouped version...")


# Define function to create group key
def create_group_key(row):
    return f"{row['TaskID']}_{row['MachineOptions']}_{row['ProductNo']}"


# Add a group key column
new_jobs_df['GroupKey'] = new_jobs_df.apply(create_group_key, axis=1)

# Sort by ScheduleDate
new_jobs_df = new_jobs_df.sort_values('ScheduleDate')

# Create a new list to store the grouped jobs
grouped_jobs = []
processed_indices = set()

# For each record
for i, row in new_jobs_df.iterrows():
    if i in processed_indices:
        continue

    # Find all matching records by group key
    matches = new_jobs_df[new_jobs_df['GroupKey'] == row['GroupKey']].copy()

    # Filter to only include matches within 3 days
    row_date = pd.to_datetime(row['ScheduleDate'])
    matches = matches[matches['ScheduleDate'].apply(
        lambda x: abs((pd.to_datetime(x) - row_date).total_seconds()) <= 3 * 24 * 60 * 60)]

    if len(matches) <= 1:
        # No grouping needed, just add the original row
        new_row = row.drop(['GroupKey', 'ScheduleDate']).copy()
        grouped_jobs.append(new_row)
    else:
        # Group matches
        match_indices = matches.index.tolist()
        processed_indices.update(match_indices)

        # Create a new job record with summed ProcTime and earliest Due date
        new_job_number = f"{row['JobNumber']}-{len(matches)}"
        new_row = row.drop(['GroupKey', 'ScheduleDate']).copy()
        new_row['JobNumber'] = new_job_number
        new_row['ProcTime'] = matches['ProcTime'].sum()
        new_row['Due'] = matches['Due'].min()

        # Add to grouped jobs
        grouped_jobs.append(new_row)

# Convert grouped jobs to DataFrame
grouped_jobs_df = pd.DataFrame(grouped_jobs)

# Ensure proper formatting
grouped_jobs_df['JobPreempt'] = grouped_jobs_df['JobPreempt'].map({True: 'TRUE', False: 'FALSE'})
grouped_jobs_df['TaskPreempt'] = grouped_jobs_df['TaskPreempt'].map({True: 'TRUE', False: 'FALSE'})
grouped_jobs_df['IsRush'] = grouped_jobs_df['IsRush'].map({True: 'TRUE', False: 'FALSE'})

# Print summary
print(f"Created {len(grouped_jobs_df)} grouped job records")
print("\nSample of grouped jobs:")
print(grouped_jobs_df.head())

# Remove ProductNo column before saving
grouped_jobs_df = grouped_jobs_df.drop('ProductNo', axis=1, errors='ignore')
# Save to CSV
grouped_jobs_df.to_csv('new_jobstg.csv', index=False)
print("Saved to new_jobstg.csv")