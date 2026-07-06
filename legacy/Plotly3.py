import pandas as pd
import plotly.graph_objects as go
import os
import sys


def load_gantt_data(filename='gantt_data.csv'):
    """
    Load and preprocess gantt data from CSV.
    """
    try:
        print(f"Loading gantt data from {filename}...")
        gantt_df = pd.read_csv(filename)
        print(f"Gantt DataFrame loaded: {gantt_df.shape} rows x columns")
        print(f"Column names: {gantt_df.columns.tolist()}")

        # Check if required columns exist
        required_columns = ['Machine', 'Task', 'Start', 'End', 'Duration', 'Phase']
        missing_columns = [col for col in required_columns if col not in gantt_df.columns]

        if missing_columns:
            print(f"WARNING: Missing required columns in gantt data: {missing_columns}")
            print("Attempting to fix column names...")

            # Try to rename columns based on common patterns
            if 'Machine' not in gantt_df.columns and 'machine' in gantt_df.columns:
                gantt_df = gantt_df.rename(columns={'machine': 'Machine'})

            if 'Task' not in gantt_df.columns and 'task' in gantt_df.columns:
                gantt_df = gantt_df.rename(columns={'task': 'Task'})

            if 'Start' not in gantt_df.columns and 'start' in gantt_df.columns:
                gantt_df = gantt_df.rename(columns={'start': 'Start'})

            if 'End' not in gantt_df.columns and 'end' in gantt_df.columns:
                gantt_df = gantt_df.rename(columns={'end': 'End'})

            if 'Duration' not in gantt_df.columns and 'duration' in gantt_df.columns:
                gantt_df = gantt_df.rename(columns={'duration': 'Duration'})

            if 'Phase' not in gantt_df.columns and 'phase' in gantt_df.columns:
                gantt_df = gantt_df.rename(columns={'phase': 'Phase'})

            # Check again after fixes
            missing_columns = [col for col in required_columns if col not in gantt_df.columns]
            if missing_columns:
                print(f"ERROR: Still missing required columns: {missing_columns}")
                print("Cannot proceed without these columns.")
                sys.exit(1)
            else:
                print("Column names fixed successfully.")

        # Print the first few rows to check the data structure
        print("First 5 rows (after column fixing):")
        print(gantt_df.head())

        # Ensure Machine is integer (if it's not already)
        try:
            gantt_df['Machine'] = gantt_df['Machine'].astype(int)
        except Exception as e:
            print(f"WARNING: Could not convert Machine column to integer: {e}")
            print("Machine values:", gantt_df['Machine'].tolist()[:10])

        # Calculate End from Start+Duration if End is missing
        if 'End' not in gantt_df.columns and 'Start' in gantt_df.columns and 'Duration' in gantt_df.columns:
            gantt_df['End'] = gantt_df['Start'] + gantt_df['Duration']
            print("Created End column from Start + Duration.")

        # Calculate Duration from End-Start if Duration is missing
        if 'Duration' not in gantt_df.columns and 'Start' in gantt_df.columns and 'End' in gantt_df.columns:
            gantt_df['Duration'] = gantt_df['End'] - gantt_df['Start']
            print("Created Duration column from End - Start.")

        return gantt_df
    except Exception as e:
        print(f"ERROR loading gantt data: {e}")
        sys.exit(1)


def load_capacity_data(filename='machine_capacity.csv'):
    """
    Load and preprocess machine capacity data from CSV.
    """
    try:
        print(f"Loading capacity data from {filename}...")
        capacity_df = pd.read_csv(filename)
        print(f"Capacity DataFrame loaded: {capacity_df.shape} rows x columns")
        print(f"Column names: {capacity_df.columns.tolist()}")

        # Check if required columns exist
        required_columns = ['Machine', 'StartTime', 'EndTime']
        missing_columns = [col for col in required_columns if col not in capacity_df.columns]

        if missing_columns:
            print(f"WARNING: Missing required columns in capacity data: {missing_columns}")
            print("Attempting to fix column names...")

            # Try to rename columns based on common patterns
            if 'Machine' not in capacity_df.columns and 'machine' in capacity_df.columns:
                capacity_df = capacity_df.rename(columns={'machine': 'Machine'})

            if 'StartTime' not in capacity_df.columns:
                if 'Start' in capacity_df.columns:
                    capacity_df = capacity_df.rename(columns={'Start': 'StartTime'})
                elif 'start' in capacity_df.columns:
                    capacity_df = capacity_df.rename(columns={'start': 'StartTime'})
                elif 'start_time' in capacity_df.columns:
                    capacity_df = capacity_df.rename(columns={'start_time': 'StartTime'})

            if 'EndTime' not in capacity_df.columns:
                if 'End' in capacity_df.columns:
                    capacity_df = capacity_df.rename(columns={'End': 'EndTime'})
                elif 'end' in capacity_df.columns:
                    capacity_df = capacity_df.rename(columns={'end': 'EndTime'})
                elif 'end_time' in capacity_df.columns:
                    capacity_df = capacity_df.rename(columns={'end_time': 'EndTime'})

            # Check again after fixes
            missing_columns = [col for col in required_columns if col not in capacity_df.columns]
            if missing_columns:
                print(f"ERROR: Still missing required columns: {missing_columns}")
                print("Cannot proceed without these columns.")
                sys.exit(1)
            else:
                print("Column names fixed successfully.")

        # Print the first few rows to check the data structure
        print("First 5 rows (after column fixing):")
        print(capacity_df.head())

        return capacity_df
    except Exception as e:
        print(f"ERROR loading capacity data: {e}")
        sys.exit(1)


def create_machine_mappings():
    """
    Create mappings between machine names and indices.
    """
    # Define machine mapping (consistent with optimizer)
    machine_map = {
        "CNC-1": 0, "Lathe-2": 1, "Miller-3": 2, "Drill-4": 3, "Grinder-5": 4,
        "Saw-6": 5, "Press-7": 6, "Lathe-8": 7, "Mill-9": 8, "Polish-10": 9
    }

    # Map numeric indices to names with index for clarity
    machine_names = {
        0: "CNC-1(0)", 1: "Lathe-2(1)", 2: "Miller-3(2)", 3: "Drill-4(3)", 4: "Grinder-5(4)",
        5: "Saw-6(5)", 6: "Press-7(6)", 7: "Lathe-8(7)", 8: "Mill-9(8)", 9: "Polish-10(9)"
    }

    return machine_map, machine_names


def map_machine_names(gantt_df, machine_names):
    """
    Apply machine name mapping to the DataFrame.
    """
    try:
        print("Mapping machine names...")
        # Save original machine values
        original_machines = gantt_df['Machine'].unique()
        print(f"Original machine values: {original_machines}")

        # Convert to integers if they're not already
        if not gantt_df['Machine'].dtype == 'int64':
            try:
                gantt_df['Machine'] = gantt_df['Machine'].astype(int)
                print("Converted Machine column to integers.")
            except Exception as e:
                print(f"WARNING: Could not convert Machine to integers: {e}")
                print("Will attempt to map as-is.")

        # Apply mapping
        gantt_df['Machine'] = gantt_df['Machine'].map(lambda x: machine_names.get(x, f"Unknown({x})"))
        print(f"Machine mapping complete. New values: {gantt_df['Machine'].unique()}")
        print(f"Sample after mapping: \n{gantt_df.head()}")

        return gantt_df
    except Exception as e:
        print(f"ERROR mapping machine names: {e}")
        # Return original DataFrame if mapping fails
        return gantt_df


def calculate_downtime(capacity_df, machine_map, machine_names):
    """
    Calculate downtime windows from capacity data.
    """
    print("Calculating downtime windows...")
    downtime_data = []

    try:
        # First, ensure capacity_df has the right column types
        if not pd.api.types.is_numeric_dtype(capacity_df['StartTime']):
            capacity_df['StartTime'] = pd.to_numeric(capacity_df['StartTime'], errors='coerce')
            print("Converted StartTime to numeric.")

        if not pd.api.types.is_numeric_dtype(capacity_df['EndTime']):
            capacity_df['EndTime'] = pd.to_numeric(capacity_df['EndTime'], errors='coerce')
            print("Converted EndTime to numeric.")

        # Process each machine
        for machine in capacity_df['Machine'].unique():
            try:
                print(f"Processing machine: {machine}")

                # Skip if machine not in map
                if machine not in machine_map:
                    print(f"  Warning: Machine '{machine}' not found in machine map. Skipping.")
                    continue

                # Get capacity slots for this machine
                machine_slots = capacity_df[capacity_df['Machine'] == machine].sort_values('StartTime')

                if machine_slots.empty:
                    print(f"  Warning: No capacity data for machine '{machine}'. Skipping.")
                    continue

                # Calculate downtime gaps
                prev_end = 0
                for _, row in machine_slots.iterrows():
                    if row['StartTime'] > prev_end:
                        downtime_data.append({
                            'Machine': machine_names[machine_map[machine]],  # Use mapped name with index
                            'Start': prev_end,
                            'End': row['StartTime'],
                            'Duration': row['StartTime'] - prev_end,
                            'Phase': 'Downtime'
                        })
                    prev_end = row['EndTime']
            except Exception as e:
                print(f"  Error processing machine {machine}: {e}")
                continue
    except Exception as e:
        print(f"ERROR calculating downtime: {e}")

    # Create DataFrame from downtime data
    downtime_df = pd.DataFrame(downtime_data)

    # Ensure we have the required columns
    if len(downtime_data) == 0:
        print("WARNING: No downtime periods found!")
        # Create an empty DataFrame with required columns
        downtime_df = pd.DataFrame(columns=['Machine', 'Start', 'End', 'Duration', 'Phase'])

    print(f"Downtime DataFrame created: {downtime_df.shape} rows x columns")
    print(f"First 5 rows of downtime data: \n{downtime_df.head()}")

    return downtime_df


def check_overlaps_downtime(row, downtime_df):
    """
    Check if a task overlaps with any downtime period.
    Safe implementation that handles missing columns or empty DataFrames.
    """
    try:
        # If downtime_df is empty, nothing can overlap
        if downtime_df.empty:
            return False

        # Ensure we have all required columns in both DataFrames
        required_cols = {'Machine', 'Start', 'End'}
        row_cols = set(row.index)
        dt_cols = set(downtime_df.columns)

        if not required_cols.issubset(row_cols) or not required_cols.issubset(dt_cols):
            print(f"WARNING: Missing required columns for overlap check: row={row_cols}, downtime={dt_cols}")
            return False

        # Filter downtime periods for this machine
        machine_downtime = downtime_df[downtime_df['Machine'] == row['Machine']]

        # Check for overlap with each downtime period
        for _, dt in machine_downtime.iterrows():
            # Overlap occurs when start of one is before end of other, and end of one is after start of other
            if row['Start'] < dt['End'] and row['End'] > dt['Start']:
                return True

        return False
    except Exception as e:
        print(f"ERROR checking downtime overlap: {e}")
        return False


def create_gantt_figure(gantt_df, downtime_df, machine_names, solution_name="Default"):
    """
    Create the Plotly Gantt chart figure with robust error handling.
    """
    print(f"Creating Gantt chart figure for {solution_name}...")

    # Create figure
    fig = go.Figure()

    try:
        # Define all machines in order for y-axis
        all_machines = sorted(machine_names.values(), key=lambda x: int(x.split('(')[1].strip(')')))
        machine_to_y = {machine: idx for idx, machine in enumerate(all_machines)}

        # Print debug info about machine mapping
        print(f"Machine mapping created for {len(all_machines)} machines:")
        for machine, y_pos in list(machine_to_y.items())[:5]:  # Show first 5 for brevity
            print(f"  {machine} -> position {y_pos}")
        if len(machine_to_y) > 5:
            print(f"  ... and {len(machine_to_y) - 5} more")

        # Verify gantt_df has required columns
        required_cols = {'Machine', 'Task', 'Start', 'End', 'Duration', 'Phase'}
        if not required_cols.issubset(set(gantt_df.columns)):
            print(f"ERROR: gantt_df is missing columns. Has: {gantt_df.columns.tolist()}")
            print("Creating a minimal chart instead.")

            # Add a placeholder trace
            fig.add_trace(go.Scatter(
                x=[0, 100],
                y=[0, 0],
                mode='lines',
                name='Error: Missing Data',
                line=dict(color='red', dash='dash')
            ))

            # Add text annotation explaining the error
            fig.add_annotation(
                x=50, y=0,
                text="ERROR: Data columns missing. Check console for details.",
                showarrow=True,
                arrowhead=1
            )

            # Return minimal figure
            return fig, {}

        # Process each phase
        phases_processed = 0
        for phase, color in [('Setup', 'yellow'), ('Proc', 'green'), ('Dwell', 'lightgray')]:
            try:
                # Filter tasks for this phase
                phase_df = gantt_df[gantt_df['Phase'] == phase]

                if phase_df.empty:
                    print(f"No tasks with phase '{phase}' found in data.")
                    continue

                print(f"Processing {len(phase_df)} tasks with phase '{phase}'")
                phases_processed += 1

                # Handle special case for Setup phase (check downtime overlap)
                if phase == 'Setup':
                    try:
                        # Safely check for overlaps
                        overlap_results = []
                        for _, row in phase_df.iterrows():
                            try:
                                overlap_results.append(check_overlaps_downtime(row, downtime_df))
                            except Exception as e:
                                print(f"Error checking overlap for row: {e}")
                                overlap_results.append(False)

                        # Create boolean mask from results
                        overlap_mask = pd.Series(overlap_results, index=phase_df.index)

                        # Split into normal and overlapping setups
                        normal_df = phase_df[~overlap_mask]
                        overlap_df = phase_df[overlap_mask]

                        print(f"  - Normal setup tasks: {len(normal_df)}")
                        print(f"  - Setup tasks overlapping downtime: {len(overlap_df)}")

                        # Add normal setup tasks
                        if not normal_df.empty:
                            # Ensure all machines in normal_df are in the machine_to_y mapping
                            valid_machine_mask = normal_df['Machine'].isin(machine_to_y.keys())
                            if not all(valid_machine_mask):
                                print(f"WARNING: Some machines in normal_df are not in machine_to_y mapping")
                                print(f"Invalid machines: {normal_df.loc[~valid_machine_mask, 'Machine'].unique()}")
                                # Filter to only include valid machines
                                normal_df = normal_df[valid_machine_mask]

                            fig.add_trace(go.Bar(
                                x=normal_df['Duration'],
                                y=normal_df['Machine'].map(machine_to_y),
                                base=normal_df['Start'],
                                orientation='h',
                                name=phase,
                                marker_color=color,
                                hovertemplate=(
                                    "Phase=%{customdata[0]}<br>"
                                    "Start=%{base}<br>"
                                    "End=%{x}<br>"
                                    "Machine=%{customdata[1]}<br>"
                                    "Task=%{customdata[2]}<br>"
                                    "Duration=%{customdata[3]}<extra></extra>"
                                ),
                                customdata=normal_df[['Phase', 'Machine', 'Task', 'Duration']].values
                            ))

                        # Add overlapping setup tasks
                        if not overlap_df.empty:
                            # Ensure all machines in overlap_df are in the machine_to_y mapping
                            valid_machine_mask = overlap_df['Machine'].isin(machine_to_y.keys())
                            if not all(valid_machine_mask):
                                print(f"WARNING: Some machines in overlap_df are not in machine_to_y mapping")
                                # Filter to only include valid machines
                                overlap_df = overlap_df[valid_machine_mask]

                            fig.add_trace(go.Bar(
                                x=overlap_df['Duration'],
                                y=overlap_df['Machine'].map(machine_to_y),
                                base=overlap_df['Start'],
                                orientation='h',
                                name='Setup (Overlaps Downtime)',
                                marker_color=color,
                                marker_line_color='red',
                                marker_line_width=2,
                                hovertemplate=(
                                    "Phase=%{customdata[0]}<br>"
                                    "Start=%{base}<br>"
                                    "End=%{x}<br>"
                                    "Machine=%{customdata[1]}<br>"
                                    "Task=%{customdata[2]}<br>"
                                    "Duration=%{customdata[3]}<br>"
                                    "<b>WARNING: Overlaps Downtime</b><extra></extra>"
                                ),
                                customdata=overlap_df[['Phase', 'Machine', 'Task', 'Duration']].values
                            ))
                    except Exception as e:
                        print(f"ERROR processing Setup phase: {e}")
                        # Skip overlap check and add all Setup tasks as normal
                        print("Adding all Setup tasks without overlap check.")

                        # Filter by valid machines
                        valid_machine_mask = phase_df['Machine'].isin(machine_to_y.keys())
                        if not all(valid_machine_mask):
                            print(f"WARNING: Some machines in phase_df are not in machine_to_y mapping")
                            phase_df = phase_df[valid_machine_mask]

                        fig.add_trace(go.Bar(
                            x=phase_df['Duration'],
                            y=phase_df['Machine'].map(machine_to_y),
                            base=phase_df['Start'],
                            orientation='h',
                            name=phase,
                            marker_color=color,
                            hovertemplate=(
                                "Phase=%{customdata[0]}<br>"
                                "Start=%{base}<br>"
                                "End=%{x}<br>"
                                "Machine=%{customdata[1]}<br>"
                                "Task=%{customdata[2]}<br>"
                                "Duration=%{customdata[3]}<extra></extra>"
                            ),
                            customdata=phase_df[['Phase', 'Machine', 'Task', 'Duration']].values
                        ))
                elif phase == 'Dwell':
                    # Semi-transparent Dwell bars
                    # Filter by valid machines
                    valid_machine_mask = phase_df['Machine'].isin(machine_to_y.keys())
                    if not all(valid_machine_mask):
                        print(f"WARNING: Some machines in Dwell phase_df are not in machine_to_y mapping")
                        phase_df = phase_df[valid_machine_mask]

                    fig.add_trace(go.Bar(
                        x=phase_df['Duration'],
                        y=phase_df['Machine'].map(machine_to_y),
                        base=phase_df['Start'],
                        orientation='h',
                        name=phase,
                        marker_color=color,
                        opacity=0.5,  # Set transparency
                        hovertemplate=(
                            "Phase=%{customdata[0]}<br>"
                            "Start=%{base}<br>"
                            "End=%{x}<br>"
                            "Machine=%{customdata[1]}<br>"
                            "Task=%{customdata[2]}<br>"
                            "Duration=%{customdata[3]}<extra></extra>"
                        ),
                        customdata=phase_df[['Phase', 'Machine', 'Task', 'Duration']].values
                    ))
                else:
                    # Filter by valid machines
                    valid_machine_mask = phase_df['Machine'].isin(machine_to_y.keys())
                    if not all(valid_machine_mask):
                        print(f"WARNING: Some machines in {phase} phase_df are not in machine_to_y mapping")
                        phase_df = phase_df[valid_machine_mask]

                    fig.add_trace(go.Bar(
                        x=phase_df['Duration'],
                        y=phase_df['Machine'].map(machine_to_y),
                        base=phase_df['Start'],
                        orientation='h',
                        name=phase,
                        marker_color=color,
                        hovertemplate=(
                            "Phase=%{customdata[0]}<br>"
                            "Start=%{base}<br>"
                            "End=%{x}<br>"
                            "Machine=%{customdata[1]}<br>"
                            "Task=%{customdata[2]}<br>"
                            "Duration=%{customdata[3]}<extra></extra>"
                        ),
                        customdata=phase_df[['Phase', 'Machine', 'Task', 'Duration']].values
                    ))
            except Exception as e:
                print(f"ERROR processing phase '{phase}': {e}")
                continue

        print(f"Added traces for {phases_processed} phases")

        # Add downtime shapes if we have downtime data
        if not downtime_df.empty:
            # Filter to only include valid machines
            valid_machine_mask = downtime_df['Machine'].isin(machine_to_y.keys())
            if not all(valid_machine_mask):
                print(f"WARNING: Some machines in downtime_df are not in machine_to_y mapping")
                downtime_df = downtime_df[valid_machine_mask]

            print(f"Adding {len(downtime_df)} downtime periods as shapes")
            for _, row in downtime_df.iterrows():
                try:
                    y_pos = machine_to_y[row['Machine']]
                    fig.add_shape(
                        type="rect",
                        x0=row['Start'], x1=row['End'],
                        y0=y_pos - 0.45, y1=y_pos + 0.45,
                        fillcolor="gray",
                        opacity=0.7,
                        layer="below",
                        line_width=0
                    )
                except Exception as e:
                    print(f"ERROR adding downtime shape: {e}")
                    continue
        else:
            print("No downtime periods to add.")

        # Add dummy trace for legend
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='markers',
            marker=dict(color="gray", opacity=0.7),
            name="Downtime",
            showlegend=True
        ))

        # Calculate makespan for x-axis range
        makespan = 0
        if not gantt_df.empty:
            try:
                task_ends = gantt_df['Start'] + gantt_df['Duration']
                makespan = task_ends.max()
            except Exception as e:
                print(f"ERROR calculating makespan: {e}")
                makespan = 350  # Default

        makespan = max(350, int(makespan * 1.1))  # Add 10% margin

        print(f"Calculated makespan: {makespan}")

        # Update layout
        fig.update_layout(
            title=f"Scheduling Gantt Chart - {solution_name}",
            xaxis_title="Time (seconds)",
            yaxis_title="Machine",
            yaxis=dict(
                ticktext=all_machines,
                tickvals=list(range(len(all_machines))),
                autorange="reversed"  # Ensures top-to-bottom order matches machine indices
            ),
            barmode='overlay',  # Ensures bars overlap correctly
            legend_title_text='Phase',
            xaxis_range=[0, makespan],
            bargap=0.2,
            height=600,  # Adjust height for better visibility
            template="plotly_white",  # Use a cleaner template
            margin=dict(l=50, r=50, t=50, b=50)  # Add some margin
        )

        # Calculate metrics
        metrics = {
            'makespan': makespan,
            'total_setup_time': int(gantt_df[gantt_df['Phase'] == 'Setup']['Duration'].sum()),
            'total_proc_time': int(gantt_df[gantt_df['Phase'] == 'Proc']['Duration'].sum()),
            'total_dwell_time': int(gantt_df[gantt_df['Phase'] == 'Dwell']['Duration'].sum()),
            'setup_downtime_overlap': 0  # Calculate this properly if needed
        }

        print(f"Figure created with {len(fig.data)} traces")
        return fig, metrics

    except Exception as e:
        print(f"ERROR creating Gantt figure: {e}")
        # Create a minimal figure with error message
        fig.add_trace(go.Scatter(
            x=[0, 100],
            y=[0, 0],
            mode='lines+text',
            name='Error',
            text=['Error creating chart'],
            textposition='top center',
            line=dict(color='red')
        ))

        # Add annotation explaining the error
        fig.add_annotation(
            x=50, y=0,
            text=f"Error creating chart: {str(e)}",
            showarrow=False,
            font=dict(size=14, color='red')
        )

        # Return minimal figure with empty metrics
        return fig, {'makespan': 0, 'total_setup_time': 0, 'total_proc_time': 0, 'total_dwell_time': 0,
                     'setup_downtime_overlap': 0}


def write_html_with_utf8(filename, content):
    """
    Write HTML content to file with UTF-8 encoding to avoid character encoding issues.
    """
    try:
        print(f"Writing HTML to file {filename} (length: {len(content)})")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"HTML file successfully written to {filename}")

        # Verify file exists and has content
        file_size = os.path.getsize(filename)
        print(f"File size: {file_size} bytes")
        if file_size < 100:
            print("WARNING: File is suspiciously small, may be empty or corrupted")
    except Exception as e:
        print(f"ERROR writing HTML file: {e}")

        # Try with a simple HTML content as fallback
        try:
            print("Attempting to write a minimal HTML file as fallback...")
            minimal_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Error in Gantt Chart</title>
</head>
<body>
    <h1>Error Creating Gantt Chart</h1>
    <p>There was an error generating the Gantt chart. Please check the console output for details.</p>
</body>
</html>"""
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(minimal_html)
            print(f"Minimal HTML file written to {filename}")
        except Exception as e2:
            print(f"ERROR writing minimal HTML file: {e2}")


def create_test_figure():
    """
    Create a simple test figure to verify Plotly is working correctly.
    """
    print("Creating test figure...")
    test_fig = go.Figure()

    # Add a simple scatter plot
    test_fig.add_trace(go.Scatter(
        x=[0, 1, 2, 3, 4, 5],
        y=[0, 1, 0, 2, 1, 0],
        mode='lines+markers',
        name='Test Line'
    ))

    # Update layout
    test_fig.update_layout(
        title="Test Figure",
        xaxis_title="X Axis",
        yaxis_title="Y Axis",
        template="plotly_white"
    )

    return test_fig


def main():
    """
    Main function to run the Gantt chart generation.
    """
    print("-" * 50)
    print("Starting Gantt chart generation...")
    print("-" * 50)

    try:
        # Load data
        gantt_df = load_gantt_data()
        capacity_df = load_capacity_data()

        # Create machine mappings
        machine_map, machine_names = create_machine_mappings()

        # Map machine names
        gantt_df = map_machine_names(gantt_df, machine_names)

        # Calculate downtime
        downtime_df = calculate_downtime(capacity_df, machine_map, machine_names)

        # Create the main figure
        solution_name = "Solution 1 (Current)"
        fig, metrics = create_gantt_figure(gantt_df, downtime_df, machine_names, solution_name)

        # Generate HTML for main figure
        print("Generating HTML for main figure...")
        try:
            main_html = fig.to_html(include_plotlyjs=True, full_html=True)
            print(f"HTML generated successfully, length: {len(main_html)}")
        except Exception as e:
            print(f"ERROR generating HTML: {e}")
            print("Trying with minimal configuration...")
            try:
                main_html = fig.to_html(include_plotlyjs=True, full_html=True, config={'displayModeBar': False})
            except Exception as e2:
                print(f"ERROR generating HTML with minimal config: {e2}")
                main_html = "<html><body><h1>Error generating Gantt chart</h1></body></html>"

        # Save main figure
        main_output = "gantt_chart_with_downtime.html"
        write_html_with_utf8(main_output, main_html)

        # Create a test figure as a fallback
        test_fig = create_test_figure()
        try:
            test_html = test_fig.to_html(include_plotlyjs=True, full_html=True)
            test_output = "test_figure.html"
            write_html_with_utf8(test_output, test_html)
            print(f"Test figure saved to {test_output}")
        except Exception as e:
            print(f"ERROR creating test figure: {e}")

        print("-" * 50)
        print("Gantt chart generation complete!")
        print("-" * 50)
    except Exception as e:
        print(f"ERROR in main function: {e}")
        print("Gantt chart generation failed!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        # Create a minimal error HTML file
        error_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Critical Error</title>
</head>
<body>
    <h1>Critical Error in Gantt Chart Generation</h1>
    <p>Error message: {str(e)}</p>
    <p>Please check the console output for details.</p>
</body>
</html>"""
        try:
            with open("gantt_error.html", 'w', encoding='utf-8') as f:
                f.write(error_html)
            print("Error HTML file created at gantt_error.html")
        except:
            print("Could not create error HTML file")