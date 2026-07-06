import pandas as pd
import plotly.graph_objects as go
import os
import dash
from intdash import dcc, html, Input, Output, State, ctx
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
            return gantt_df

        new_jobs_df = pd.read_csv('new_jobs.csv')
        required_cols = ['JobNumber', 'TaskID', 'StateID']
        if not all(col in new_jobs_df.columns for col in required_cols):
            gantt_df['StateID'] = -1
            return gantt_df

        task_to_state = {}
        for _, row in new_jobs_df.iterrows():
            task_key = f"{row['JobNumber']} T{row['TaskID']}"
            task_to_state[task_key] = int(row['StateID'])

        gantt_df['StateID'] = gantt_df.apply(
            lambda row: task_to_state.get(row['Task'], -1) if row['Phase'] != 'Downtime' else -1,
            axis=1
        )
    except Exception:
        gantt_df['StateID'] = -1
    return gantt_df


# Function to add setup transition annotations to the figure
def add_setup_transition_info_to_fig(fig, gantt_df, machine_to_y, all_machine_indices_sorted,
                                     machine_display_names_map):
    if 'StateID' not in gantt_df.columns or 'Setup' not in gantt_df['Phase'].values:
        return fig

    try:
        if not os.path.exists('setup_transitions.csv'):
            return fig
        setup_transitions_df = pd.read_csv('setup_transitions.csv')
        required_cols = ['FromStateID', 'ToStateID', 'SetupTime', 'SetupScrap']
        if not all(col in setup_transitions_df.columns for col in required_cols):
            return fig
    except Exception:
        return fig

    setup_phases = gantt_df[gantt_df['Phase'] == 'Setup'].copy()
    if 'StateID' not in setup_phases.columns or (not setup_phases.empty and setup_phases['StateID'].min() < 0):
        pass

    for machine_idx in all_machine_indices_sorted:
        machine_setups = setup_phases[setup_phases['Machine'] == machine_idx].copy()
        if len(machine_setups) < 2:
            continue
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
            if setup_time == 0: continue

            x_from, x_to = prev_task['Start'] + prev_task['Duration'], curr_task['Start']
            if x_to <= x_from or abs(x_to - x_from) < 5: continue  # Avoid overlap/tiny gaps

            x_pos, y_pos = (x_from + x_to) / 2, machine_to_y.get(machine_idx)
            if y_pos is None: continue

            fig.add_annotation(
                x=x_pos, y=y_pos,
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
        return pd.DataFrame().to_dict('records'), pd.DataFrame().to_dict('records'), [], {}, {}

    gantt_df = pd.read_csv('gantt_data.csv')
    gantt_df['uid'] = gantt_df.index.astype(str)  # Unique ID for each row/bar
    gantt_df['Machine'] = gantt_df['Machine'].astype(int)

    gantt_df = enhance_gantt_data_with_states(gantt_df)

    # Machine Name Formatting
    if 'MachineName' in gantt_df.columns:
        gantt_df['MachineFormatted'] = gantt_df.apply(
            lambda row: f"{row['MachineName']}({row['Machine']})", axis=1
        )
    else:  # Try to get from new_jobs.csv or fallback
        try:
            if not os.path.exists('new_jobs.csv'): raise FileNotFoundError(
                "new_jobs.csv not found for machine name mapping.")
            new_jobs_df = pd.read_csv('new_jobs.csv')
            required_cols = ['JobNumber', 'TaskID', 'MachineOptions']
            if not all(col in new_jobs_df.columns for col in required_cols):
                raise ValueError(f"new_jobs.csv missing required columns: {', '.join(required_cols)}")

            task_machine_map = {}
            for _, row in new_jobs_df.iterrows():
                job_num, task_id_val = str(row['JobNumber']), int(row['TaskID'])
                machine_options = str(row['MachineOptions'])
                machine_name = machine_options.split('/')[-1] if '/' in machine_options else machine_options
                task_machine_map[f"{job_num} T{task_id_val}"] = machine_name

            gantt_df['MachineName'] = gantt_df['Task'].map(task_machine_map)
            gantt_df['MachineName'] = gantt_df['MachineName'].fillna(gantt_df['Machine'].apply(lambda x: f"M-{x}"))
            gantt_df['MachineFormatted'] = gantt_df.apply(lambda r: f"{r['MachineName']}({r['Machine']})", axis=1)
        except (FileNotFoundError, ValueError) as e:
            gantt_df['MachineName'] = gantt_df['Machine'].apply(lambda x: f"M-{x}")
            gantt_df['MachineFormatted'] = gantt_df['Machine'].apply(lambda x: f"M-{x}({x})")

    all_machine_ids_sorted = sorted(gantt_df['Machine'].unique())
    machine_display_names_map = {}
    if not gantt_df.empty:
        machine_display_names_map = {
            idx: gantt_df[gantt_df['Machine'] == idx]['MachineFormatted'].iloc[0]
            if not gantt_df[gantt_df['Machine'] == idx].empty else f"M-{idx}({idx})"
            for idx in all_machine_ids_sorted
        }
    machine_to_y_mapping = {idx: i for i, idx in enumerate(all_machine_ids_sorted)}

    # Downtime data processing
    downtime_data_list = []
    try:
        if not os.path.exists('machine_capacity.csv'): raise FileNotFoundError(
            "machine_capacity.csv not found for downtime.")
        capacity_df = pd.read_csv('machine_capacity.csv')
        required_cols = ['StartTime', 'EndTime']
        if not all(col in capacity_df.columns for col in required_cols):
            raise ValueError("machine_capacity.csv missing StartTime or EndTime.")

        if 'Machine' in capacity_df.columns and pd.api.types.is_numeric_dtype(capacity_df['Machine']):
            capacity_df['MachineIdx'] = capacity_df['Machine']
        elif 'MachineName' in capacity_df.columns:
            gantt_machine_name_to_id_map = {
                gantt_df[gantt_df['Machine'] == mid]['MachineName'].iloc[0]: mid
                for mid in all_machine_ids_sorted
                if not gantt_df[gantt_df['Machine'] == mid].empty and 'MachineName' in gantt_df.columns
            }
            capacity_df['MachineIdx'] = capacity_df['MachineName'].apply(
                lambda name: gantt_machine_name_to_id_map.get(str(name), -1))
            capacity_df = capacity_df[capacity_df['MachineIdx'] != -1]
        else:
            raise ValueError("machine_capacity.csv needs 'Machine' (ID) or 'MachineName' column.")

        if 'MachineIdx' in capacity_df.columns:
            for machine_idx_val in all_machine_ids_sorted:
                machine_slots = capacity_df[capacity_df['MachineIdx'] == machine_idx_val].sort_values('StartTime')
                prev_end = 0
                for _, row in machine_slots.iterrows():
                    if row['StartTime'] > prev_end:
                        downtime_data_list.append({
                            'Machine': machine_idx_val, 'Start': prev_end, 'End': row['StartTime'],
                            'Duration': row['StartTime'] - prev_end, 'Phase': 'Downtime'
                        })
                    prev_end = row['EndTime']
    except (FileNotFoundError, ValueError) as e:
        pass  # Silently ignore if optional files/configs are problematic
    except Exception:
        pass

    downtime_df = pd.DataFrame(downtime_data_list)
    return gantt_df.to_dict('records'), downtime_df.to_dict(
        'records'), all_machine_ids_sorted, machine_display_names_map, machine_to_y_mapping


# Core plotting function to generate the Gantt chart figure
def create_gantt_figure(gantt_data_dict, downtime_data_dict,
                        all_machine_ids_sorted, machine_display_names_map, machine_to_y_mapping,
                        selected_task_uid=None):
    gantt_df = pd.DataFrame(gantt_data_dict)
    downtime_df = pd.DataFrame(downtime_data_dict)
    fig = go.Figure()

    if not gantt_df.empty and (not all_machine_ids_sorted or not machine_display_names_map or not machine_to_y_mapping):
        return fig

    for phase, color_map_entry in [('Setup', 'orange'), ('Proc', 'royalblue'), ('Dwell', 'lightslategrey')]:
        phase_df = gantt_df[gantt_df['Phase'] == phase]
        if phase_df.empty: continue

        customdata_list = []
        for _, row in phase_df.iterrows():
            customdata_list.append([
                row['uid'], row['Phase'], row.get('MachineFormatted', f"M-{row['Machine']}({row['Machine']})"),
                row['Task'], row['Duration'],
                format_time_as_days_hours_minutes(row['Start']),
                format_time_as_days_hours_minutes(row['Start'] + row['Duration']),
                row.get('StateID', -1)
            ])

        opacities = [0.6 if str(row['uid']) == str(selected_task_uid) else (0.7 if phase == 'Dwell' else 1.0) for _, row
                     in phase_df.iterrows()]
        marker_line_colors = ['magenta' if str(row['uid']) == str(selected_task_uid) else 'black' for _, row in
                              phase_df.iterrows()]
        marker_line_widths = [2.5 if str(row['uid']) == str(selected_task_uid) else 0.5 for _, row in
                              phase_df.iterrows()]

        fig.add_trace(go.Bar(
            x=phase_df['Duration'],
            y=[machine_to_y_mapping.get(m, -1) for m in phase_df['Machine']],
            base=phase_df['Start'], orientation='h', name=phase, marker_color=color_map_entry,
            opacity=opacities, marker_line_color=marker_line_colors, marker_line_width=marker_line_widths,
            customdata=customdata_list,
            hovertemplate=(
                "<b>%{customdata[3]}</b> (%{customdata[1]})<br>"
                "UID: %{customdata[0]} | Machine: %{customdata[2]}<br>"
                "Start: %{customdata[5]} | End: %{customdata[6]}<br>"
                "Duration: %{customdata[4]} min | State: %{customdata[7]}<extra></extra>"
            )
        ))

    if not downtime_df.empty:
        for _, row in downtime_df.iterrows():
            y_pos = machine_to_y_mapping.get(row['Machine'])
            if y_pos is not None:
                start_fmt, end_fmt = format_time_as_days_hours_minutes(row['Start']), format_time_as_days_hours_minutes(
                    row['End'])
                fig.add_shape(type="rect", x0=row['Start'], x1=row['End'], y0=y_pos - 0.45, y1=y_pos + 0.45,
                              fillcolor="grey", opacity=0.5, layer="below", line_width=0)
                fig.add_trace(go.Scatter(
                    x=[(row['Start'] + row['End']) / 2], y=[y_pos], mode='markers',
                    marker=dict(color="rgba(0,0,0,0)", size=1), showlegend=False,
                    hovertemplate=f"Downtime<br>Start: {start_fmt}<br>End: {end_fmt}<br>Duration: {row['Duration']} min<extra></extra>"
                ))
        fig.add_trace(
            go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="grey", opacity=0.5), name="Downtime",
                       showlegend=True))

    if not gantt_df.empty:
        fig = add_setup_transition_info_to_fig(fig, gantt_df, machine_to_y_mapping, all_machine_ids_sorted,
                                               machine_display_names_map)

    max_time_val = 0
    if not gantt_df.empty: max_time_val = (gantt_df['Start'].fillna(0) + gantt_df['Duration'].fillna(0)).max()
    if not downtime_df.empty and 'End' in downtime_df.columns and not downtime_df['End'].empty:
        max_time_val = max(max_time_val, downtime_df['End'].max(skipna=True) if not downtime_df.empty else 0)
    max_time_val = max(max_time_val * 1.05, max_time_val + 200) if pd.notna(max_time_val) and max_time_val > 0 else 1000

    minutes_per_day, num_days_on_axis = 24 * 60, math.ceil(max_time_val / (24 * 60)) + 1 if max_time_val > 0 else 2

    fig.update_layout(
        title="Production Schedule Gantt Chart", xaxis_title="Time (days)", yaxis_title="Machine",
        yaxis=dict(
            ticktext=[machine_display_names_map.get(idx, f"M-{idx}") for idx in all_machine_ids_sorted],
            tickvals=[machine_to_y_mapping.get(idx) for idx in all_machine_ids_sorted if
                      machine_to_y_mapping.get(idx) is not None],
            autorange="reversed"
        ),
        barmode='overlay', legend_title_text='Phase', xaxis_range=[0, max_time_val],
        xaxis=dict(tickvals=[i * minutes_per_day for i in range(num_days_on_axis)],
                   ticktext=[f"{i}" for i in range(num_days_on_axis)],
                   tickangle=0, tickmode='array', gridwidth=0.5, gridcolor='lightgrey'),
        bargap=0.2, height=max(600, len(all_machine_ids_sorted) * 35 + 200),
        clickmode='event+select', dragmode=False
    )
    return fig


# --- Dash App Definition ---
app = dash.Dash(__name__)
app.title = "Interactive Gantt Chart"

app.layout = html.Div([
    dcc.Store(id='gantt-data-store'),
    dcc.Store(id='downtime-data-store'),
    dcc.Store(id='machine-config-store'),
    dcc.Store(id='selected-task-store', data={'uid': None, 'duration': None}),
    # Stores selected task UID and its duration

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
    prevent_initial_call=False  # Load data on app start
)
def load_initial_data_callback(n_clicks_reload):
    gantt_data, downtime_data, all_ids, display_map, to_y_map = load_and_prepare_data()
    machine_config = {
        'all_machine_ids_sorted': all_ids,
        'machine_display_names_map': display_map,
        'machine_to_y_mapping': to_y_map
    }
    initial_message = "Data loaded. Click a task bar to select it. Click again on the chart to place it."
    if not gantt_data: initial_message = "Warning: No Gantt data loaded. Check gantt_data.csv and console for errors."

    return gantt_data, downtime_data, machine_config, initial_message, {'uid': None, 'duration': None}


# Callback to update the Gantt chart figure when data changes
@app.callback(
    Output('gantt-chart-graph', 'figure'),
    [Input('gantt-data-store', 'data'),
     Input('downtime-data-store', 'data'),
     Input('machine-config-store', 'data'),
     Input('selected-task-store', 'data')]
)
def update_gantt_chart_callback(gantt_data_dict, downtime_data_dict, machine_config, selected_task_info):
    if not gantt_data_dict or not machine_config or not machine_config.get('all_machine_ids_sorted'):
        fig = go.Figure()
        fig.update_layout(title="No data loaded or machine configuration missing.", xaxis=dict(visible=False),
                          yaxis=dict(visible=False))
        return fig

    selected_uid = selected_task_info['uid'] if selected_task_info and selected_task_info['uid'] is not None else None
    return create_gantt_figure(
        gantt_data_dict, downtime_data_dict,
        machine_config['all_machine_ids_sorted'], machine_config['machine_display_names_map'],
        machine_config['machine_to_y_mapping'], selected_uid=selected_uid
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
def handle_task_interaction_callback(clickData, n_clicks_reset, selected_task_info, gantt_data_records, machine_config):
    triggered_id, no_update = ctx.triggered_id, dash.no_update

    if triggered_id == 'reset-selection-button':
        return {'uid': None, 'duration': None}, no_update, "Task selection reset."

    if not clickData or not gantt_data_records or not machine_config or not machine_config.get(
            'all_machine_ids_sorted'):
        return no_update, no_update, "Interaction not possible: data or configuration missing."

    gantt_df = pd.DataFrame(gantt_data_records)
    all_machine_ids_sorted = machine_config['all_machine_ids_sorted']
    y_to_machine_id_map = {i: mid for mid, i in machine_config['machine_to_y_mapping'].items()}
    clicked_point = clickData['points'][0]

    if selected_task_info['uid'] is None:  # Selection phase
        if 'customdata' in clicked_point:
            uid_selected, task_name_sel, duration_sel = str(clicked_point['customdata'][0]), \
            clicked_point['customdata'][3], clicked_point['customdata'][4]
            return {'uid': uid_selected,
                    'duration': duration_sel}, no_update, f"Task '{task_name_sel}' (UID: {uid_selected}) selected. Click new position to move."
        else:
            return no_update, no_update, "Clicked on empty space. Click on a task bar to select it."
    else:  # Placement phase
        uid_to_move, duration_to_move = str(selected_task_info['uid']), selected_task_info['duration']
        clicked_y_val, target_start_time = clicked_point['y'], clicked_point['x']

        y_idx = int(np.clip(round(clicked_y_val), 0, len(all_machine_ids_sorted) - 1))
        target_machine_id = y_to_machine_id_map.get(y_idx)

        if target_machine_id is None:
            return {'uid': None,
                    'duration': None}, no_update, "Error: Could not determine target machine. Movement cancelled."
        if target_start_time < 0: target_start_time = 0

        task_indices = gantt_df[gantt_df['uid'] == uid_to_move].index
        if not task_indices.empty:
            idx = task_indices[0]
            original_task_name = gantt_df.loc[idx, 'Task']
            gantt_df.loc[idx, 'Start'] = target_start_time
            gantt_df.loc[idx, 'End'] = target_start_time + duration_to_move  # Duration is a number of minutes
            gantt_df.loc[idx, 'Machine'] = target_machine_id

            target_machine_fmt_name = machine_config['machine_display_names_map'].get(target_machine_id,
                                                                                      f"M-{target_machine_id}({target_machine_id})")
            gantt_df.loc[idx, 'MachineFormatted'] = target_machine_fmt_name
            message = f"Task '{original_task_name}' (UID: {uid_to_move}) moved to {target_machine_fmt_name} at {format_time_as_days_hours_minutes(target_start_time)}."
        else:
            message = f"Error: Task UID {uid_to_move} not found. Movement cancelled."
        return {'uid': None, 'duration': None}, gantt_df.to_dict('records'), message


if __name__ == '__main__':
    # Create dummy optional files if they don't exist for robust startup
    dummy_files_content = {
        'new_jobs.csv': "JobNumber,TaskID,StateID,MachineOptions\nJOB1,0,10,F00B/D3001\nJOB1,1,12,F00B/D3007\nJOB2,0,15,F00B/D3001",
        'machine_capacity.csv': "Machine,MachineName,StartTime,EndTime\n6,F00B/D3001,2880,2940\n7,F00B/D3002,5760,5820",
        'setup_transitions.csv': "FromStateID,ToStateID,SetupTime,SetupScrap\n10,12,30,1\n12,10,25,0.5\n10,15,40,2"
    }
    for fname, content in dummy_files_content.items():
        if not os.path.exists(fname):
            with open(fname, 'w') as f: f.write(content)

    if not os.path.exists('gantt_data.csv'):
        print("FATAL ERROR: gantt_data.csv is missing. A minimal sample file will be created.")
        minimal_gantt_data = "Machine,MachineName,Task,Start,End,Duration,Phase\n6,F00B/D3001,SAMPLE_TASK T0,0,60,60,Setup\n6,F00B/D3001,SAMPLE_TASK T0,60,120,60,Proc\n7,F00B/D3002,ANOTHER_TASK T0,10,80,70,Setup"
        with open('gantt_data.csv', 'w') as f: f.write(minimal_gantt_data)

    app.run_server(debug=True)