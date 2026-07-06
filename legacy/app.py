import pandas as pd
import plotly.graph_objects as go
import os
import dash
from dash import dcc, html, Input, Output, State, ctx, no_update
import numpy as np
import math  # For math.ceil


# Helper function to format time
def format_time_as_days_hours_minutes(minutes):
    if pd.isna(minutes):
        return "N/A"
    minutes = int(minutes)
    days = minutes // (24 * 60)
    remaining_minutes = minutes % (24 * 60)
    hours = remaining_minutes // 60
    mins = remaining_minutes % 60
    return f"Day {days}, {hours:02d}:{mins:02d}"


# Function to enhance Gantt data with State IDs from new_jobs.csv
def enhance_gantt_data_with_states(gantt_df):
    try:
        if not os.path.exists('new_jobs.csv'):
            gantt_df['StateID'] = -1
            # print("Warning: new_jobs.csv not found. StateID enhancement skipped.")
            return gantt_df

        new_jobs_df = pd.read_csv('new_jobs.csv')
        required_cols = ['JobNumber', 'TaskID', 'StateID']
        if not all(col in new_jobs_df.columns for col in required_cols):
            gantt_df['StateID'] = -1
            # print(f"Warning: new_jobs.csv missing one or more required columns ({', '.join(required_cols)}). StateID enhancement skipped.")
            return gantt_df

        task_to_state = {}
        for _, row in new_jobs_df.iterrows():
            task_key = f"{row['JobNumber']} T{row['TaskID']}"
            task_to_state[task_key] = int(row['StateID'])

        gantt_df['StateID'] = gantt_df.apply(
            lambda row: task_to_state.get(row['Task'], -1) if row['Phase'] != 'Downtime' else -1,
            axis=1
        )
        # print("Gantt data enhanced with StateIDs from new_jobs.csv.")
    except Exception as e:
        print(f"Error enhancing gantt data with states: {e}")
        gantt_df['StateID'] = -1
    return gantt_df


# Function to add setup transition annotations to the figure
# Expects machine_to_y_map_str_keys (string keys for machine_id)
def add_setup_transition_info_to_fig(fig, gantt_df, machine_to_y_map_str_keys, all_machine_indices_sorted_int,
                                     machine_display_names_map_str_keys):
    if 'StateID' not in gantt_df.columns or 'Setup' not in gantt_df['Phase'].values:
        return fig

    try:
        if not os.path.exists('setup_transitions.csv'): return fig
        setup_transitions_df = pd.read_csv('setup_transitions.csv')
        required_cols = ['FromStateID', 'ToStateID', 'SetupTime', 'SetupScrap']
        if not all(col in setup_transitions_df.columns for col in required_cols): return fig
    except Exception as e:
        print(f"Error loading setup_transitions.csv for annotations: {e}")
        return fig

    setup_phases = gantt_df[gantt_df['Phase'] == 'Setup'].copy()

    for machine_idx_int in all_machine_indices_sorted_int:  # machine_idx_int is an integer
        machine_setups = setup_phases[setup_phases['Machine'] == machine_idx_int].copy()
        if len(machine_setups) < 2: continue
        machine_setups = machine_setups.sort_values('Start')
        rows = machine_setups.to_dict('records')
        for i in range(1, len(rows)):
            prev_task, curr_task = rows[i - 1], rows[i]
            prev_state, curr_state = prev_task.get('StateID', -1), curr_task.get('StateID', -1)

            if prev_state < 0 or curr_state < 0: continue
            transition = setup_transitions_df[
                (setup_transitions_df['FromStateID'] == prev_state) &
                (setup_transitions_df['ToStateID'] == curr_state)
                ]
            if transition.empty: continue

            setup_time, setup_scrap = transition.iloc[0]['SetupTime'], transition.iloc[0]['SetupScrap']
            if pd.isna(setup_time) or setup_time == 0: continue

            x_from, x_to = prev_task['Start'] + prev_task['Duration'], curr_task['Start']
            if pd.isna(x_from) or pd.isna(x_to) or x_to <= x_from or abs(x_to - x_from) < 5: continue

            # Use string key for machine_to_y_map_str_keys
            y_pos = machine_to_y_map_str_keys.get(str(machine_idx_int))
            if y_pos is None: continue

            fig.add_annotation(
                x=(x_from + x_to) / 2, y=y_pos,
                text=f"S{prev_state}→S{curr_state}<br>{setup_time}m, {setup_scrap} scrap",
                showarrow=True, arrowhead=1, arrowsize=0.8, arrowwidth=1, arrowcolor='rgba(100,0,0,0.7)',
                font=dict(size=7, color='darkred'), align='center',
                bordercolor='darkred', borderwidth=0.5, borderpad=2,
                bgcolor='rgba(255, 220, 220, 0.7)', opacity=0.9
            )
    return fig


# Main data loading and preparation function
def load_and_prepare_data():
    if not os.path.exists('gantt_data.csv'):
        print("FATAL: gantt_data.csv not found.")
        return pd.DataFrame().to_dict('records'), pd.DataFrame().to_dict('records'), [], {}, {}

    try:
        gantt_df = pd.read_csv('gantt_data.csv')
        gantt_df['uid'] = gantt_df.index.astype(str)
        gantt_df['Machine'] = pd.to_numeric(gantt_df['Machine'], errors='coerce').fillna(-1).astype(int)
        gantt_df['Start'] = pd.to_numeric(gantt_df['Start'], errors='coerce').fillna(0)
        gantt_df['Duration'] = pd.to_numeric(gantt_df['Duration'], errors='coerce').fillna(0)
        gantt_df['Task'] = gantt_df['Task'].astype(str)  # Ensure Task is string for mapping
        gantt_df = gantt_df[gantt_df['Machine'] != -1]
        if gantt_df.empty:
            print("Warning: Gantt data is empty after initial processing or filtering invalid machines.")
            return pd.DataFrame().to_dict('records'), pd.DataFrame().to_dict('records'), [], {}, {}

        gantt_df = enhance_gantt_data_with_states(gantt_df)

        if 'MachineName' not in gantt_df.columns:
            # print("MachineName column not found in gantt_data.csv. Attempting to map from new_jobs.csv or using fallback.")
            try:
                if not os.path.exists('new_jobs.csv'): raise FileNotFoundError(
                    "new_jobs.csv not found for machine name mapping.")
                new_jobs_df = pd.read_csv('new_jobs.csv')
                required_cols_nj = ['JobNumber', 'TaskID', 'MachineOptions']
                if not all(col in new_jobs_df.columns for col in required_cols_nj):
                    raise ValueError(
                        f"new_jobs.csv missing required columns for machine name mapping: {', '.join(required_cols_nj)}")

                task_machine_map = {}
                for _, row in new_jobs_df.iterrows():
                    job_num, task_id_val = str(row['JobNumber']), int(row['TaskID'])
                    machine_options = str(row['MachineOptions'])
                    machine_name = machine_options.split('/')[-1] if '/' in machine_options else machine_options
                    task_machine_map[f"{job_num} T{task_id_val}"] = machine_name

                gantt_df['MachineName'] = gantt_df['Task'].map(task_machine_map)
            except (FileNotFoundError, ValueError) as e_nj_map:
                # print(f"Warning: Could not get machine names from new_jobs.csv: {e_nj_map}. Using generic names if needed.")
                pass  # If MachineName exists, it will be used, otherwise generic below
            except Exception as e_nj_map_other:
                print(f"Unexpected error mapping machine names from new_jobs.csv: {e_nj_map_other}.")
                pass

        # Create MachineFormatted (ensure MachineName exists, even if as fallback)
        if 'MachineName' not in gantt_df.columns:  # If still no MachineName (e.g. new_jobs failed or gantt_data had none)
            gantt_df['MachineName'] = gantt_df['Machine'].apply(lambda x: f"M-{x}")  # Fallback
        gantt_df['MachineName'] = gantt_df['MachineName'].fillna(
            gantt_df['Machine'].apply(lambda x: f"M-{x}"))  # Fill NaNs if any
        gantt_df['MachineFormatted'] = gantt_df.apply(lambda r: f"{r['MachineName']}({r['Machine']})", axis=1)

        all_machine_ids_sorted_int = sorted(gantt_df['Machine'].unique()) if not gantt_df.empty else []

        # --- CREATE JSON SERIALIZABLE MAPS ---
        machine_display_names_map_str_keys = {}
        if not gantt_df.empty:
            for idx_int in all_machine_ids_sorted_int:
                rows_for_machine = gantt_df[gantt_df['Machine'] == idx_int]
                # Use MachineFormatted which should always exist now
                machine_display_names_map_str_keys[str(idx_int)] = rows_for_machine['MachineFormatted'].iloc[
                    0] if not rows_for_machine.empty else f"M-{idx_int}({idx_int})"

        machine_to_y_mapping_str_keys = {str(idx_int): i for i, idx_int in enumerate(all_machine_ids_sorted_int)}
        # --- END JSON SERIALIZABLE MAPS ---

        downtime_data_list = []
        try:
            if not os.path.exists('machine_capacity.csv'): raise FileNotFoundError(
                "machine_capacity.csv not found for downtime.")
            capacity_df = pd.read_csv('machine_capacity.csv')
            required_cols_cap = ['StartTime', 'EndTime']
            if not all(col in capacity_df.columns for col in required_cols_cap):
                raise ValueError(f"machine_capacity.csv missing required columns: {', '.join(required_cols_cap)}.")

            if 'Machine' in capacity_df.columns and pd.api.types.is_numeric_dtype(capacity_df['Machine']):
                capacity_df['MachineIdx'] = capacity_df['Machine'].astype(int)
            elif 'MachineName' in capacity_df.columns and 'MachineName' in gantt_df.columns:
                # Create a map from MachineName in gantt_df to its integer Machine ID
                gantt_machine_name_to_id_map = \
                gantt_df.drop_duplicates(subset=['MachineName']).set_index('MachineName')['Machine'].to_dict()
                if gantt_machine_name_to_id_map:
                    capacity_df['MachineIdx'] = capacity_df['MachineName'].map(gantt_machine_name_to_id_map).fillna(
                        -1).astype(int)
                    capacity_df = capacity_df[capacity_df['MachineIdx'] != -1]
                else:
                    capacity_df['MachineIdx'] = -1
            else:
                capacity_df['MachineIdx'] = -1

            capacity_df['StartTime'] = pd.to_numeric(capacity_df['StartTime'], errors='coerce')
            capacity_df['EndTime'] = pd.to_numeric(capacity_df['EndTime'], errors='coerce')
            capacity_df.dropna(subset=['MachineIdx', 'StartTime', 'EndTime'], inplace=True)

            if 'MachineIdx' in capacity_df.columns and not capacity_df.empty:
                for machine_idx_val_int in all_machine_ids_sorted_int:
                    machine_slots = capacity_df[capacity_df['MachineIdx'] == machine_idx_val_int].sort_values(
                        'StartTime')
                    prev_end = 0
                    for _, row in machine_slots.iterrows():
                        if row['StartTime'] > prev_end:
                            downtime_data_list.append({
                                'Machine': machine_idx_val_int, 'Start': prev_end, 'End': row['StartTime'],
                                'Duration': row['StartTime'] - prev_end, 'Phase': 'Downtime'
                            })
                        prev_end = row['EndTime']
        except FileNotFoundError:
            pass
        except ValueError as ve_cap:
            print(f"Warning processing machine_capacity.csv: {ve_cap}")
        except Exception as e_cap:
            print(f"Unexpected error processing machine_capacity.csv: {e_cap}")

        downtime_df = pd.DataFrame(downtime_data_list)
        return gantt_df.to_dict('records'), downtime_df.to_dict(
            'records'), all_machine_ids_sorted_int, machine_display_names_map_str_keys, machine_to_y_mapping_str_keys

    except Exception as e_main:
        print(f"FATAL error in load_and_prepare_data: {e_main}")
        return pd.DataFrame().to_dict('records'), pd.DataFrame().to_dict('records'), [], {}, {}


# Core plotting function - expects string-keyed maps
# Core plotting function - expects string-keyed maps
def create_gantt_figure(gantt_data_dict, downtime_data_dict, all_machine_ids_sorted_int,
                        machine_display_names_map_str_keys, machine_to_y_map_str_keys, selected_task_uid=None):
    fig = go.Figure()

    # --- Define DataFrames from input dicts FIRST ---
    gantt_df = pd.DataFrame(gantt_data_dict)
    downtime_df = pd.DataFrame(downtime_data_dict)
    # --- END DataFrame definitions ---

    if not gantt_data_dict or not all_machine_ids_sorted_int or not machine_display_names_map_str_keys or not machine_to_y_map_str_keys:
        fig.update_layout(title="No data or machine configuration to display.", xaxis_visible=False,
                          yaxis_visible=False)
        return fig

    # Now it's safe to check if gantt_df is empty
    if gantt_df.empty:
        fig.update_layout(title="Gantt data is empty.", xaxis_visible=False, yaxis_visible=False)
        return fig

    # --- Define base colors for phases ---
    phase_base_colors_rgb = {
        'Setup': '255,165,0',  # Orange: rgb(255,165,0)
        'Proc': '65,105,225',  # Royal Blue: rgb(65,105,225)
        'Dwell': '112,128,144'  # Slate Grey: rgb(112,128,144)
    }

    for phase, color_map_entry_rgb_string in phase_base_colors_rgb.items():
        phase_df = gantt_df[gantt_df['Phase'] == phase]
        if phase_df.empty: continue

        customdata_list = []
        y_values_for_bars = []
        marker_colors_rgba = []  # To store RGBA colors for each bar

        for _, row in phase_df.iterrows():
            machine_id_int = row['Machine']
            y_val = machine_to_y_map_str_keys.get(str(machine_id_int))
            if y_val is None: continue

            y_values_for_bars.append(y_val)
            customdata_list.append([
                str(row['uid']), row['Phase'], row.get('MachineFormatted', f"M-{machine_id_int}({machine_id_int})"),
                row['Task'], row['Duration'],
                format_time_as_days_hours_minutes(row['Start']),
                format_time_as_days_hours_minutes(row['Start'] + row['Duration']),
                row.get('StateID', -1)
            ])

            # --- Determine opacity and construct RGBA color ---
            current_opacity = 1.0
            if str(row['uid']) == str(selected_task_uid):
                current_opacity = 0.6  # Lower opacity for selected (or keep 1.0 and rely on border)
            elif phase == 'Dwell':
                current_opacity = 0.7

            marker_colors_rgba.append(f'rgba({color_map_entry_rgb_string},{current_opacity})')
            # --- End RGBA color construction ---

        valid_phase_df = phase_df[phase_df['Machine'].apply(lambda m_id: str(m_id) in machine_to_y_map_str_keys)]
        if valid_phase_df.empty: continue

        # opacities list is removed
        marker_line_colors = ['magenta' if str(row['uid']) == str(selected_task_uid) else 'black' for _, row in
                              valid_phase_df.iterrows()]
        marker_line_widths = [2.5 if str(row['uid']) == str(selected_task_uid) else 0.5 for _, row in
                              valid_phase_df.iterrows()]

        fig.add_trace(go.Bar(
            x=valid_phase_df['Duration'],
            y=y_values_for_bars,
            base=valid_phase_df['Start'], orientation='h', name=phase,
            marker_color=marker_colors_rgba,  # CHANGED: Use list of RGBA colors
            # opacity=opacities, # REMOVED: Opacity is now part of marker_color
            marker_line_color=marker_line_colors,
            marker_line_width=marker_line_widths,
            customdata=customdata_list,
            hovertemplate=(
                "<b>%{customdata[3]}</b> (%{customdata[1]})<br>"
                "UID: %{customdata[0]} | Machine: %{customdata[2]}<br>"
                "Start: %{customdata[5]} | End: %{customdata[6]}<br>"
                "Duration: %{customdata[4]} min | State: %{customdata[7]}<extra></extra>"
            )
        ))

    # ... (rest of the function for downtime, setup transitions, layout) ...
    return fig


# --- Dash App Definition ---
app = dash.Dash(__name__)
app.title = "Interactive Gantt Chart"

app.layout = html.Div([
    dcc.Store(id='gantt-data-store'),
    dcc.Store(id='downtime-data-store'),
    dcc.Store(id='machine-config-store'),
    dcc.Store(id='selected-task-store', data={'uid': None, 'duration': None, 'task_name': None}),

    html.H2("Interactive Gantt Chart", style={'textAlign': 'center', 'fontFamily': 'Arial'}),
    html.Div(id='message-area',
             style={'padding': '10px', 'border': '1px solid lightgrey', 'marginBottom': '10px', 'minHeight': '40px',
                    'background': '#f9f9f9', 'textAlign': 'center', 'fontFamily': 'Arial'}),

    dcc.Graph(id='gantt-chart-graph', config={'displayModeBar': True, 'scrollZoom': True}),

    html.Div([
        html.Button('Reset Task Selection', id='reset-selection-button', n_clicks=0,
                    style={'marginTop': '10px', 'fontFamily': 'Arial'}),
        html.Button('Reload Initial Data', id='reload-data-button', n_clicks=0,
                    style={'marginTop': '10px', 'marginLeft': '10px', 'fontFamily': 'Arial'})
    ], style={'textAlign': 'center', 'paddingBottom': '20px'})
])


# Callback to load/reload all data
@app.callback(
    [Output('gantt-data-store', 'data'),
     Output('downtime-data-store', 'data'),
     Output('machine-config-store', 'data'),
     Output('message-area', 'children', allow_duplicate=True),
     Output('selected-task-store', 'data', allow_duplicate=True)],
    [Input('reload-data-button', 'n_clicks')],
    prevent_initial_call='initial_duplicate'
)
def load_initial_data_callback(n_clicks_reload):
    # load_and_prepare_data returns string-keyed maps for JSON store
    gantt_data, downtime_data, all_ids_int, display_map_str_keys, to_y_map_str_keys = load_and_prepare_data()

    machine_config = {
        'all_machine_ids_sorted_int': all_ids_int,  # List of integers
        'machine_display_names_map_str_keys': display_map_str_keys,  # Dict with string keys
        'machine_to_y_map_str_keys': to_y_map_str_keys  # Dict with string keys
    }

    current_message = ""
    # Distinguish initial load from button click
    if ctx.triggered_id == 'reload-data-button' and n_clicks_reload is not None and n_clicks_reload > 0:
        current_message = "Data reloaded. Click a task bar to select it. Click again on the chart to place it."
    else:  # Initial load
        current_message = "Data loaded. Click a task bar to select it. Click again on the chart to place it."

    if not gantt_data:
        current_message += " Warning: No Gantt data loaded. Check gantt_data.csv and console for errors."
    elif not all_ids_int:
        current_message += " Warning: No machine IDs found. Gantt data might be empty or invalid."

    return gantt_data, downtime_data, machine_config, current_message, {'uid': None, 'duration': None,
                                                                        'task_name': None}


# Callback to update the Gantt chart figure when data changes
@app.callback(
    Output('gantt-chart-graph', 'figure'),
    [Input('gantt-data-store', 'data'),
     Input('downtime-data-store', 'data'),
     Input('machine-config-store', 'data'),
     Input('selected-task-store', 'data')]
)
def update_gantt_chart_callback(gantt_data_dict, downtime_data_dict, machine_config_from_store, selected_task_info):
    if not gantt_data_dict or not machine_config_from_store or not machine_config_from_store.get(
            'all_machine_ids_sorted_int'):
        fig = go.Figure()
        fig.update_layout(title="No data loaded or machine configuration missing.", xaxis_visible=False,
                          yaxis_visible=False)
        return fig

    selected_uid_val = selected_task_info.get('uid') if selected_task_info else None
    return create_gantt_figure(
        gantt_data_dict, downtime_data_dict,
        machine_config_from_store['all_machine_ids_sorted_int'],
        machine_config_from_store['machine_display_names_map_str_keys'],
        machine_config_from_store['machine_to_y_map_str_keys'],
        selected_uid_val  # Pass positionally
    )


# Callback to handle click interactions for selecting and moving tasks
@app.callback(
    [Output('selected-task-store', 'data', allow_duplicate=True),
     Output('gantt-data-store', 'data', allow_duplicate=True),
     Output('message-area', 'children', allow_duplicate=True)],
    [Input('gantt-chart-graph', 'clickData'),
     Input('reset-selection-button', 'n_clicks')],
    [State('selected-task-store', 'data'),
     State('gantt-data-store', 'data'),
     State('machine-config-store', 'data')],
    prevent_initial_call=True
)
def handle_task_interaction_callback(clickData, n_clicks_reset, selected_task_info, gantt_data_records,
                                     machine_config_from_store):
    triggered_id = ctx.triggered_id

    if triggered_id == 'reset-selection-button':
        return {'uid': None, 'duration': None, 'task_name': None}, no_update, "Task selection reset."

    if not clickData or not gantt_data_records or not machine_config_from_store or not machine_config_from_store.get(
            'all_machine_ids_sorted_int'):
        return no_update, no_update, "Interaction not possible: data or configuration missing."

    gantt_df = pd.DataFrame(gantt_data_records)
    all_machine_ids_sorted_int = machine_config_from_store['all_machine_ids_sorted_int']
    machine_to_y_map_str_keys = machine_config_from_store.get('machine_to_y_map_str_keys', {})
    machine_display_names_map_str_keys = machine_config_from_store.get('machine_display_names_map_str_keys', {})

    # Create reverse mapping from y-axis index (int) to machine ID (int)
    # Keys of machine_to_y_map_str_keys are strings ('0', '1', ...), values are ints (0, 1, ...)
    y_to_machine_id_map_int_keys = {
        y_idx_val: int(machine_id_str)
        for machine_id_str, y_idx_val in machine_to_y_map_str_keys.items()
    }

    clicked_point = clickData['points'][0]

    current_selected_uid = selected_task_info.get('uid')
    current_selected_duration = selected_task_info.get('duration')
    current_selected_task_name = selected_task_info.get('task_name')

    if current_selected_uid is None:  # --- SELECTION PHASE ---
        if 'customdata' in clicked_point and len(clicked_point['customdata']) >= 5:
            uid_selected = str(clicked_point['customdata'][0])
            task_name_sel = clicked_point['customdata'][3]
            duration_sel = clicked_point['customdata'][4]
            try:
                duration_sel = float(duration_sel)
                if pd.isna(duration_sel): raise ValueError("Duration is NaN")
            except (ValueError, TypeError):
                return no_update, no_update, f"Error: Task '{task_name_sel}' has invalid duration '{duration_sel}'. Cannot select."
            return {'uid': uid_selected, 'duration': duration_sel,
                    'task_name': task_name_sel}, no_update, f"Task '{task_name_sel}' (UID: {uid_selected}) selected. Click new position on chart to move."
        else:
            return no_update, no_update, "Clicked on empty space or non-task element. Click on a task bar to select it."
    else:  # --- PLACEMENT PHASE ---
        uid_to_move = str(current_selected_uid)
        duration_to_move = current_selected_duration
        task_name_moving = current_selected_task_name

        clicked_y_val = clicked_point.get('y')
        target_start_time = clicked_point.get('x')

        if clicked_y_val is None or target_start_time is None:
            return {'uid': None, 'duration': None,
                    'task_name': None}, no_update, "Error: Invalid click location for placement. Movement cancelled."

        y_idx = int(
            np.clip(round(clicked_y_val), 0, len(all_machine_ids_sorted_int) - 1)) if all_machine_ids_sorted_int else -1
        target_machine_id_int = y_to_machine_id_map_int_keys.get(y_idx)  # Get integer machine ID

        if target_machine_id_int is None:
            return {'uid': None, 'duration': None,
                    'task_name': None}, no_update, "Error: Could not determine target machine from click. Movement cancelled."
        if target_start_time < 0: target_start_time = 0
        if duration_to_move is None or not isinstance(duration_to_move, (int, float)) or pd.isna(duration_to_move):
            return {'uid': None, 'duration': None,
                    'task_name': None}, no_update, f"Error: Duration for task UID {uid_to_move} is invalid. Movement cancelled."

        task_indices = gantt_df[gantt_df['uid'] == uid_to_move].index
        if not task_indices.empty:
            idx_to_update = task_indices[0]

            gantt_df.loc[idx_to_update, 'Start'] = target_start_time
            # End is typically Start + Duration, not stored directly unless it's fixed
            # gantt_df.loc[idx_to_update, 'End'] = target_start_time + duration_to_move
            gantt_df.loc[idx_to_update, 'Machine'] = target_machine_id_int  # Store integer machine ID

            target_machine_fmt_name = machine_display_names_map_str_keys.get(str(target_machine_id_int),
                                                                             f"M-{target_machine_id_int}({target_machine_id_int})")
            gantt_df.loc[idx_to_update, 'MachineFormatted'] = target_machine_fmt_name

            message = f"Task '{task_name_moving}' (UID: {uid_to_move}) moved to {target_machine_fmt_name} starting at {format_time_as_days_hours_minutes(target_start_time)}."
        else:
            message = f"Error: Task UID {uid_to_move} not found in current data. Movement cancelled."

        return {'uid': None, 'duration': None, 'task_name': None}, gantt_df.to_dict('records'), message


if __name__ == '__main__':
    dummy_files_content = {
        'new_jobs.csv': "JobNumber,TaskID,StateID,MachineOptions\nJOB1,0,10,F00B/D3001\nJOB1,1,12,F00B/D3007\nJOB2,0,15,M-ALT",
        'machine_capacity.csv': "Machine,MachineName,StartTime,EndTime\n6,F00B/D3001,2880,2940\n7,F00B/D3002,5760,5820\n0,,100,200",
        'setup_transitions.csv': "FromStateID,ToStateID,SetupTime,SetupScrap\n10,12,30,1\n12,10,25,0.5\n10,15,40,2"
    }
    for fname, content in dummy_files_content.items():
        if not os.path.exists(fname):
            try:
                with open(fname, 'w') as f:
                    f.write(content)
                # print(f"Created dummy file: {fname}")
            except Exception as e_dummy:
                print(f"Could not create dummy file {fname}: {e_dummy}")

    if not os.path.exists('gantt_data.csv'):
        print("FATAL ERROR: gantt_data.csv is missing. A minimal sample file will be created.")
        minimal_gantt_data = (
            "Machine,MachineName,Task,Start,End,Duration,Phase\n"
            "6,F00B/D3001,SAMPLE_TASK_A T0,0,60,60,Setup\n"  # Task needs to be string
            "6,F00B/D3001,SAMPLE_TASK_A T0,60,120,60,Proc\n"
            "7,F00B/D3002,SAMPLE_TASK_B T0,10,80,70,Setup\n"
            "0,M-0,SAMPLE_TASK_C T0,0,50,50,Proc"
        )
        try:
            with open('gantt_data.csv', 'w') as f:
                f.write(minimal_gantt_data)
            # print("Created minimal gantt_data.csv")
        except Exception as e_gantt_dummy:
            print(f"Could not create minimal gantt_data.csv: {e_gantt_dummy}")

    app.run(debug=True)