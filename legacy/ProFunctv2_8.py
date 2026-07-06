import pandas as pd
import numpy as np
from ortools.sat.python import cp_model
import time
import json
import os
import csv  # Add this import at the top
import datetime
import os.path

def load_config(config_file="scheduler_config.json"):
    """
    Load configuration from a JSON file with fallback to default values.
    Designed to be non-intrusive and maintain backward compatibility.

    Args:
        config_file: Path to the configuration file

    Returns:
        Dictionary containing configuration parameters with defaults for missing values
    """
    # Define default configuration that matches current hardcoded values
    default_config = {
        "solver_parameters": {
            "max_time_in_seconds": 1800.0,
            "use_penalties": True
        },
        "cost_parameters": {
            "setup_cost": 10,
            "weight_tardiness": 5.0,
            "must_do_penalty": 10.0,
            "rush_penalty_multiplier": 10,
            "precision_factor": 10,
            "setup_scrap_cost_per_unit": 5
        },
        "machine_parameters": {
            "horizon_padding": 1000,
            "machines_count": 10,
            "machine_cost_per_unit": {
                "0": 5, "1": 3, "2": 3, "3": 4, "4": 2,
                "5": 6, "6": 3, "7": 4, "8": 5, "9": 2
            }
        },
        "tool_parameters": {
            "max_tools": {
                "0": 1, "1": 4, "2": 2
            }
        },
        "feature_flags": {
            "use_seq_dependent_setup": True
        }
    }

    # Try to load configuration file
    config = default_config.copy()
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                # Update with user-provided values using recursive merge
                merge_configs(config, user_config)
            print(f"Loaded configuration from {config_file}")
        else:
            print(f"Configuration file {config_file} not found. Using default values.")
            # Create a template configuration file if it doesn't exist
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            print(f"Created template configuration file at {config_file}")
    except Exception as e:
        print(f"Error loading configuration: {e}. Using default values.")

    # Convert string keys to integers for certain dictionaries
    if "machine_parameters" in config and "machine_cost_per_unit" in config["machine_parameters"]:
        config["machine_parameters"]["machine_cost_per_unit"] = {
            int(k): v for k, v in config["machine_parameters"]["machine_cost_per_unit"].items()
        }

    if "tool_parameters" in config and "max_tools" in config["tool_parameters"]:
        config["tool_parameters"]["max_tools"] = {
            int(k): v for k, v in config["tool_parameters"]["max_tools"].items()
        }

    return config
def load_workcenters(machine_map, config_file="workcenters.csv"):
    """
    Load workcenter definitions from CSV file with robust error handling.

    Args:
        machine_map: Dictionary mapping machine names to indices
        config_file: Path to the workcenters CSV file

    Returns:
        Dictionary of workcenters with their properties
    """
    workcenters = {}

    try:
        # Check if file exists
        if not os.path.exists(config_file):
            print(f"Workcenters file {config_file} not found. No workcenters defined.")
            return {}

        df = pd.read_csv(config_file)
        if df.empty:
            print("Workcenter file is empty. No workcenters defined.")
            return {}

        print(f"Loading workcenters from {config_file}")

        for _, row in df.iterrows():
            workcenter_id = row['WorkcenterID']
            workcenter_name = row['WorkcenterName']

            # Parse machine list
            machine_names = [m.strip() for m in row['Machines'].split(';')]
            machine_indices = []

            # Convert machine names to indices
            for machine_name in machine_names:
                if machine_name in machine_map:
                    machine_indices.append(machine_map[machine_name])
                else:
                    print(f"Warning: Machine '{machine_name}' in workcenter '{workcenter_id}' not found in machine map. Skipping.")

            # Skip workcenter if no valid machines
            if not machine_indices:
                print(f"Warning: Workcenter '{workcenter_id}' has no valid machines. Skipping.")
                continue

            # Get capacity (default to the number of machines if not specified or invalid)
            try:
                capacity = int(row['Capacity'])
                if capacity <= 0:
                    print(f"Warning: Invalid capacity {capacity} for workcenter '{workcenter_id}'. Using machine count {len(machine_indices)} instead.")
                    capacity = len(machine_indices)
            except (ValueError, TypeError):
                print(f"Warning: Invalid capacity for workcenter '{workcenter_id}'. Using machine count {len(machine_indices)} instead.")
                capacity = len(machine_indices)

            # Cap capacity at the number of machines (higher values are redundant)
            if capacity > len(machine_indices):
                print(f"Note: Capacity {capacity} exceeds machine count {len(machine_indices)} for workcenter '{workcenter_id}'. This is redundant.")

            # Parse time windows if provided
            windows = []
            try:
                if 'Windows' in row and not pd.isna(row['Windows']) and row['Windows']:
                    for window in row['Windows'].split(';'):
                        start, end = map(int, window.split('-'))
                        if start >= 0 and end > start:
                            windows.append((start, end))
                        else:
                            print(f"Warning: Invalid window {start}-{end} for workcenter '{workcenter_id}'. Skipping.")
            except Exception as e:
                print(f"Warning: Error parsing windows for workcenter '{workcenter_id}': {e}. Using full horizon.")

            # Store workcenter definition
            workcenters[workcenter_id] = {
                'name': workcenter_name,
                'machines': machine_indices,
                'capacity': capacity,
                'windows': windows
            }

            machines_str = ", ".join([f"{m}({machine_map.get(m, 'unknown')})" for m in machine_names])
            windows_str = "; ".join([f"{start}-{end}" for start, end in windows]) if windows else "full horizon"
            print(f"Loaded workcenter {workcenter_id} ('{workcenter_name}'): machines=[{machines_str}], capacity={capacity}, windows=[{windows_str}]")

        if not workcenters:
            print("No valid workcenters defined after parsing.")

        return workcenters
    except Exception as e:
        print(f"Error loading workcenters: {e}")
        print("Disabling workcenter functionality.")
        return {}
def build_machine_to_workcenter_map(workcenters, machines_count):
    """
    Build a mapping from machine indices to workcenters.

    Args:
        workcenters: Dictionary of workcenters
        machines_count: Total number of machines

    Returns:
        Dictionary mapping machine indices to workcenter IDs
    """
    machine_to_workcenter = {}

    # Initialize all machines as not belonging to any workcenter
    for m in range(machines_count):
        machine_to_workcenter[m] = None

    # Assign machines to workcenters
    for wc_id, wc_info in workcenters.items():
        for machine in wc_info['machines']:
            if machine_to_workcenter[machine] is not None:
                print(f"Warning: Machine {machine} already belongs to workcenter {machine_to_workcenter[machine]}.")
                print(f"It will be reassigned to workcenter {wc_id}.")
            machine_to_workcenter[machine] = wc_id

    # Print machine assignments
    print("Machine to workcenter mapping:")
    for m in range(machines_count):
        wc = machine_to_workcenter[m]
        wc_name = workcenters[wc]['name'] if wc is not None else "Standalone"
        print(f"  Machine {m}: {wc_name} ({wc})")

    return machine_to_workcenter


def validate_solution_downtime(solver, all_tasks, downtime_windows):
    """
    Check the solution for any downtime violations.
    """
    print("\n=== DOWNTIME CONSTRAINT VALIDATION ===")
    violations = []

    for (job_id, task_id), task in all_tasks.items():
        # Get chosen machine
        chosen_machine = None
        for m in task['machine_choice']:
            if solver.BooleanValue(task['machine_choice'][m]):
                chosen_machine = m
                break

        if chosen_machine not in downtime_windows or not downtime_windows[chosen_machine]:
            continue

        # Check if this task overlaps with any downtime
        if task.get('chunk_eligible', False) and solver.BooleanValue(task.get('should_chunk', False)):
            # Chunked task - check both chunks
            proc_start1 = solver.Value(task['proc_starts_all'][0])
            proc_end1 = solver.Value(task['proc_ends_all'][0])
            proc_start2 = solver.Value(task['proc_starts_all'][1])
            proc_end2 = solver.Value(task['proc_ends_all'][1])

            for dt_start, dt_end in downtime_windows[chosen_machine]:
                # Check chunk 1
                if (proc_start1 < dt_end and proc_end1 > dt_start):
                    violations.append({
                        'job_id': job_id,
                        'task_id': task_id,
                        'machine': chosen_machine,
                        'chunk': 1,
                        'dt_start': dt_start,
                        'dt_end': dt_end,
                        'start': proc_start1,
                        'end': proc_end1
                    })

                # Check chunk 2
                if (proc_start2 < dt_end and proc_end2 > dt_start):
                    violations.append({
                        'job_id': job_id,
                        'task_id': task_id,
                        'machine': chosen_machine,
                        'chunk': 2,
                        'dt_start': dt_start,
                        'dt_end': dt_end,
                        'start': proc_start2,
                        'end': proc_end2
                    })
        else:
            # Non-chunked task
            proc_idx = 2 if task.get('chunk_eligible', False) else 0
            proc_start = solver.Value(task['proc_starts_all'][proc_idx])
            proc_end = solver.Value(task['proc_ends_all'][proc_idx])

            for dt_start, dt_end in downtime_windows[chosen_machine]:
                if (proc_start < dt_end and proc_end > dt_start):
                    violations.append({
                        'job_id': job_id,
                        'task_id': task_id,
                        'machine': chosen_machine,
                        'chunk': None,
                        'dt_start': dt_start,
                        'dt_end': dt_end,
                        'start': proc_start,
                        'end': proc_end
                    })

    if violations:
        print(f"Found {len(violations)} downtime violations:")
        for v in violations:
            chunk_info = f" (chunk {v['chunk']})" if v['chunk'] is not None else ""
            print(f"  Job {v['job_id']}, Task {v['task_id']}{chunk_info} on Machine {v['machine']}")
            print(f"    Processing: {v['start']}-{v['end']}")
            print(f"    Downtime:   {v['dt_start']}-{v['dt_end']}")
    else:
        print("No downtime violations found!")

    print("=== END OF VALIDATION ===\n")
    return violations
def check_interval_overlap(model, interval_start, interval_end, window_start, window_end, var_name_prefix):
    """
    Create a variable that indicates if an interval overlaps with a time window.

    Args:
        model: CP-SAT model
        interval_start, interval_end: Start and end variables of the interval
        window_start, window_end: Start and end times of the window
        var_name_prefix: Prefix for variable naming

    Returns:
        Boolean variable that is True if the interval overlaps with the window
    """
    overlaps = model.NewBoolVar(f'{var_name_prefix}_overlap')

    # Interval overlaps window if:
    # 1. It starts before window ends AND
    # 2. It ends after window starts

    # Check if interval starts before window ends
    starts_before_window_end = model.NewBoolVar(f'{var_name_prefix}_starts_before_window_end')
    model.Add(interval_start < window_end).OnlyEnforceIf(starts_before_window_end)
    model.Add(interval_start >= window_end).OnlyEnforceIf(starts_before_window_end.Not())

    # Check if interval ends after window starts
    ends_after_window_start = model.NewBoolVar(f'{var_name_prefix}_ends_after_window_start')
    model.Add(interval_end > window_start).OnlyEnforceIf(ends_after_window_start)
    model.Add(interval_end <= window_start).OnlyEnforceIf(ends_after_window_start.Not())

    # Overlap occurs when both conditions are true
    model.AddBoolAnd([starts_before_window_end, ends_after_window_start]).OnlyEnforceIf(overlaps)
    model.AddBoolOr([starts_before_window_end.Not(), ends_after_window_start.Not()]).OnlyEnforceIf(overlaps.Not())

    return overlaps
def create_task_window_overlap_variable(model, task, window_start, window_end, job_id, task_id, window_idx, wc_id):
    """
    Create a variable that indicates if a task overlaps with a time window.
    This handles both chunked and non-chunked tasks.

    Args:
        model: CP-SAT model
        task: Task dictionary
        window_start: Start time of the window
        window_end: End time of the window
        job_id, task_id: IDs for variable naming
        window_idx: Window index for variable naming
        wc_id: Workcenter ID for variable naming

    Returns:
        Boolean variable that is True if the task overlaps with the window
    """
    # Ensure window boundaries are reasonable
    if window_start < 0 or window_end <= window_start:
        print(f"Warning: Adjusting invalid window boundaries: {window_start}-{window_end}")
        window_start = max(0, window_start)
        window_end = max(window_start + 1, window_end)

    task_overlaps = model.NewBoolVar(f'j{job_id}_t{task_id}_overlaps_wc{wc_id}_w{window_idx}')

    # Check for overlap based on task type (chunked or not)
    if task.get('chunk_eligible', False) and 'should_chunk' in task:
        # For chunked tasks, we need to check both chunks or the non-chunked version
        chunked_overlaps = model.NewBoolVar(f'j{job_id}_t{task_id}_chunked_overlaps_wc{wc_id}_w{window_idx}')
        no_chunk_overlaps = model.NewBoolVar(f'j{job_id}_t{task_id}_no_chunk_overlaps_wc{wc_id}_w{window_idx}')

        # Check if either chunk overlaps the window
        chunk1_overlaps = check_interval_overlap(model, task['proc_starts_all'][0], task['proc_ends_all'][0],
                                               window_start, window_end,
                                               f'j{job_id}_t{task_id}_ch1_wc{wc_id}_w{window_idx}')

        chunk2_overlaps = check_interval_overlap(model, task['proc_starts_all'][1], task['proc_ends_all'][1],
                                               window_start, window_end,
                                               f'j{job_id}_t{task_id}_ch2_wc{wc_id}_w{window_idx}')

        # Either chunk can overlap with the window
        model.AddBoolOr([chunk1_overlaps, chunk2_overlaps]).OnlyEnforceIf(chunked_overlaps)
        model.AddBoolAnd([chunk1_overlaps.Not(), chunk2_overlaps.Not()]).OnlyEnforceIf(chunked_overlaps.Not())

        # Check non-chunked version
        non_chunk_overlaps = check_interval_overlap(model, task['proc_starts_all'][2], task['proc_ends_all'][2],
                                                  window_start, window_end,
                                                  f'j{job_id}_t{task_id}_nc_wc{wc_id}_w{window_idx}')

        # Link no_chunk_overlaps to non_chunk_overlaps
        model.Add(no_chunk_overlaps == non_chunk_overlaps)

        # Task overlaps window if:
        # 1. It's chunked and at least one chunk overlaps, OR
        # 2. It's not chunked and the single interval overlaps
        model.AddBoolAnd([task['should_chunk'], chunked_overlaps]).OnlyEnforceIf(task_overlaps)
        model.AddBoolAnd([task['should_chunk'].Not(), no_chunk_overlaps]).OnlyEnforceIf(task_overlaps)
        model.AddBoolAnd([
            task['should_chunk'], chunked_overlaps.Not()
        ]).OnlyEnforceIf(task_overlaps.Not())
        model.AddBoolAnd([
            task['should_chunk'].Not(), no_chunk_overlaps.Not()
        ]).OnlyEnforceIf(task_overlaps.Not())
    else:
        # For non-chunked tasks, simple overlap check
        proc_start = task['proc_starts_all'][0]
        proc_end = task['proc_ends_all'][0]

        overlap = check_interval_overlap(model, proc_start, proc_end, window_start, window_end,
                                       f'j{job_id}_t{task_id}_wc{wc_id}_w{window_idx}')

        model.Add(task_overlaps == overlap)

    return task_overlaps

def add_hybrid_capacity_constraints(model, all_tasks, downtime_windows, machine_to_intervals,
                                   workcenters, machine_to_workcenter, horizon):
    """
    Add both machine-level and workcenter-level capacity constraints.

    The hybrid approach:
    1. Always apply machine-level no-overlap constraints for all machines
    2. Additionally apply workcenter capacity constraints for machines in workcenters

    Args:
        model: CP-SAT model
        all_tasks: Dictionary of all tasks
        downtime_windows: Dictionary of downtime windows
        machine_to_intervals: Dictionary of intervals per machine
        workcenters: Dictionary of workcenters
        machine_to_workcenter: Mapping from machines to workcenters
        horizon: Time horizon for the model
    """
    # First, always apply the regular machine-level capacity constraints
    # This ensures each machine can only process one task at a time
    add_capacity_window_constraints(model, all_tasks, downtime_windows, machine_to_intervals)

    # If no workcenters defined, we're done
    if not workcenters:
        print("No workcenters defined. Using only machine-level capacity constraints.")
        return

    print("Adding workcenter capacity constraints...")

    # For each workcenter, apply capacity constraints
    for wc_id, wc_info in workcenters.items():
        capacity = wc_info['capacity']
        machines = wc_info['machines']

        # Skip workcenters with no machines
        if not machines:
            print(f"Skipping workcenter {wc_id} with no machines.")
            continue

        # Skip workcenters with capacity equal to or greater than machine count
        # (this would be redundant as machine-level constraints already enforce one task per machine)
        if capacity >= len(machines):
            print(f"Skipping workcenter {wc_id} with capacity {capacity} >= machine count {len(machines)} (redundant constraint).")
            continue

        print(f"Processing workcenter {wc_id} with capacity {capacity} and machines {machines}")

        # Get all time windows (either from workcenter definition or entire horizon)
        windows = wc_info['windows']
        if not windows:
            # If no specific windows, use the entire horizon
            windows = [(0, horizon)]
            print(f"  No specific windows defined. Using full horizon: [(0, {horizon})]")

        # For each time window, limit the number of tasks
        for window_idx, (window_start, window_end) in enumerate(windows):
            # Ensure window boundaries are valid
            if window_start < 0:
                window_start = 0
            if window_end <= window_start:
                window_end = horizon

            print(f"  Adding capacity constraint for window {window_idx}: [{window_start}, {window_end}]")
            window_tasks = []

            # Find all tasks that could overlap with this window on any machine in this workcenter
            for (job_id, task_id), task in all_tasks.items():
                # Check if task uses any machine in this workcenter
                task_machines = []
                for m in task['machine_choice']:
                    if m in machines:
                        task_machines.append(m)

                if not task_machines:
                    continue

                print(f"    Task {job_id},{task_id} uses machines {task_machines} in this workcenter")

                # Create task choice variables for each machine in this workcenter
                machine_choice_vars = []
                for m in task_machines:
                    machine_choice_vars.append(task['machine_choice'][m])

                # This task uses a machine in this workcenter if any machine_choice var is true
                uses_workcenter_machine = model.NewBoolVar(f'j{job_id}_t{task_id}_uses_wc{wc_id}')
                model.Add(sum(machine_choice_vars) >= 1).OnlyEnforceIf(uses_workcenter_machine)
                model.Add(sum(machine_choice_vars) == 0).OnlyEnforceIf(uses_workcenter_machine.Not())

                # Create an overlap detection variable
                task_in_window = model.NewBoolVar(f'j{job_id}_t{task_id}_in_w{window_idx}_wc{wc_id}')
                overlaps = create_task_window_overlap_variable(
                    model, task, window_start, window_end, job_id, task_id, window_idx, wc_id)

                # Task is in the window if it both uses a workcenter machine and overlaps with the window
                model.AddBoolAnd([uses_workcenter_machine, overlaps]).OnlyEnforceIf(task_in_window)
                model.AddBoolOr([uses_workcenter_machine.Not(), overlaps.Not()]).OnlyEnforceIf(task_in_window.Not())

                window_tasks.append(task_in_window)

            # Apply capacity constraint for this window
            if window_tasks:
                model.Add(sum(window_tasks) <= capacity)
                print(f"  Added capacity constraint: sum of {len(window_tasks)} tasks <= {capacity} in window {window_start}-{window_end}")
            else:
                print(f"  No tasks found that could use this workcenter in window {window_start}-{window_end}")

def print_workcenter_usage(solver, all_tasks, workcenters, machine_to_workcenter):
    """
    Print information about workcenter usage in the solution.

    Args:
        solver: Solved CP-SAT solver
        all_tasks: Dictionary of all tasks
        workcenters: Dictionary of workcenters
        machine_to_workcenter: Mapping from machines to workcenters
    """
    print("\n=== WORKCENTER USAGE REPORT ===")

    # Check if we have a valid solution first
    if solver.StatusName() not in ("OPTIMAL", "FEASIBLE"):
        print("No valid solution found. Workcenter usage report unavailable.")
        print("\n=== END OF WORKCENTER USAGE REPORT ===")
        return

    # Function to check if time values are reasonable
    def is_valid_time(time_value):
        """Check if a time value is reasonably valid"""
        return isinstance(time_value, int) and -1000000 <= time_value <= 1000000

    # Create dictionary to track task assignments to workcenters and machines
    wc_assignments = {}
    for wc_id in workcenters:
        wc_assignments[wc_id] = []

    # Collect task assignments
    for (job_id, task_id), task in all_tasks.items():
        # Find which machine was chosen for this task
        chosen_machine = None
        for m in task['machine_choice']:
            if solver.BooleanValue(task['machine_choice'][m]):
                chosen_machine = m
                break

        if chosen_machine is None:
            continue  # Should not happen in a valid solution

        # Get workcenter for this machine
        wc_id = machine_to_workcenter.get(chosen_machine)
        if wc_id is None:
            continue  # Machine not in any workcenter

        # Determine task start and end time
        if task.get('chunk_eligible', False) and solver.BooleanValue(task['should_chunk']):
            # For chunked tasks, we need both chunks
            starts = [solver.Value(task['proc_starts_all'][0]), solver.Value(task['proc_starts_all'][1])]
            ends = [solver.Value(task['proc_ends_all'][0]), solver.Value(task['proc_ends_all'][1])]

            # Create an entry for each valid chunk
            for i in range(2):
                if is_valid_time(starts[i]) and is_valid_time(ends[i]) and starts[i] < ends[i]:
                    wc_assignments[wc_id].append({
                        'job_id': job_id,
                        'task_id': task_id,
                        'machine': chosen_machine,
                        'start': starts[i],
                        'end': ends[i],
                        'duration': ends[i] - starts[i],
                        'chunk': i + 1
                    })
                else:
                    print(f"Warning: Skipping invalid time values for Job {job_id}, Task {task_id}, Chunk {i+1}: {starts[i]}-{ends[i]}")
        else:
            # Non-chunked or non-split task
            idx = 2 if task.get('chunk_eligible', False) and not solver.BooleanValue(task['should_chunk']) else 0
            start = solver.Value(task['proc_starts_all'][idx])
            end = solver.Value(task['proc_ends_all'][idx])

            if is_valid_time(start) and is_valid_time(end) and start < end:
                wc_assignments[wc_id].append({
                    'job_id': job_id,
                    'task_id': task_id,
                    'machine': chosen_machine,
                    'start': start,
                    'end': end,
                    'duration': end - start,
                    'chunk': None
                })
            else:
                print(f"Warning: Skipping invalid time values for Job {job_id}, Task {task_id}: {start}-{end}")

    # Now analyze usage for each workcenter
    for wc_id, assignments in wc_assignments.items():
        wc_info = workcenters[wc_id]
        capacity = wc_info['capacity']
        print(f"\nWorkcenter: {wc_id} ({wc_info['name']})")
        print(f"Capacity: {capacity}")

        if not assignments:
            print("  No tasks assigned to this workcenter")
            continue

        print(f"Tasks assigned: {len(assignments)}")

        # Sort tasks by start time
        assignments.sort(key=lambda x: x['start'])

        # Find periods where capacity is exceeded
        time_points = sorted(list(set([a['start'] for a in assignments] + [a['end'] for a in assignments])))
        max_concurrent = 0
        concurrent_periods = []

        for i in range(len(time_points) - 1):
            period_start = time_points[i]
            period_end = time_points[i + 1]

            # Skip zero-length periods
            if period_start == period_end:
                continue

            # Count tasks active during this period
            active_tasks = []
            for a in assignments:
                if a['start'] <= period_start and a['end'] > period_start:
                    active_tasks.append(a)

            concurrent_count = len(active_tasks)
            if concurrent_count > max_concurrent:
                max_concurrent = concurrent_count

            # Record periods with multiple concurrent tasks
            if concurrent_count > 1:
                concurrent_periods.append({
                    'start': period_start,
                    'end': period_end,
                    'count': concurrent_count,
                    'tasks': active_tasks
                })

        print(f"Maximum concurrent tasks: {max_concurrent} (capacity: {capacity})")

        # Check if capacity is ever exceeded
        if max_concurrent > capacity:
            print("WARNING: Workcenter capacity is exceeded!")

        # Print details of concurrent task periods
        if concurrent_periods:
            print("\nPeriods with concurrent tasks:")
            for period in concurrent_periods:
                print(f"  Time {period['start']}-{period['end']} ({period['end']-period['start']} units): {period['count']} tasks")
                for task in period['tasks']:
                    chunk_info = f" (chunk {task['chunk']})" if task['chunk'] is not None else ""
                    print(f"    Job {task['job_id']}, Task {task['task_id']} on Machine {task['machine']}{chunk_info}: {task['start']}-{task['end']}")

        # Print task details
        print("\nTask details:")
        for a in sorted(assignments, key=lambda x: (x['job_id'], x['task_id'], x['start'])):
            chunk_info = f" (chunk {a['chunk']})" if a['chunk'] is not None else ""
            print(f"  Job {a['job_id']}, Task {a['task_id']} on Machine {a['machine']}{chunk_info}: {a['start']}-{a['end']} (duration: {a['duration']})")

    print("\n=== END OF WORKCENTER USAGE REPORT ===")

def print_workcenter_usage2(solver, all_tasks, workcenters, machine_to_workcenter):
    """
    Print information about workcenter usage in the solution.

    Args:
        solver: Solved CP-SAT solver
        all_tasks: Dictionary of all tasks
        workcenters: Dictionary of workcenters
        machine_to_workcenter: Mapping from machines to workcenters
    """
    print("\n=== WORKCENTER USAGE REPORT ===")

    # Check if we have a valid solution first
    if solver.StatusName() not in ("OPTIMAL", "FEASIBLE"):
        print("No valid solution found. Workcenter usage report unavailable.")
        print("\n=== END OF WORKCENTER USAGE REPORT ===")
        return

    # Function to check if time values are reasonable
    def is_valid_time(time_value):
        """Check if a time value is reasonably valid"""
        return isinstance(time_value, int) and -1000000 <= time_value <= 1000000

    # Create dictionary to track task assignments to workcenters and machines
    wc_assignments = {}
    for wc_id in workcenters:
        wc_assignments[wc_id] = []

    # Collect task assignments
    for (job_id, task_id), task in all_tasks.items():
        # Find which machine was chosen for this task
        chosen_machine = None
        for m in task['machine_choice']:
            if solver.BooleanValue(task['machine_choice'][m]):
                chosen_machine = m
                break

        if chosen_machine is None:
            continue  # Should not happen in a valid solution

        # Get workcenter for this machine
        wc_id = machine_to_workcenter.get(chosen_machine)
        if wc_id is None:
            continue  # Machine not in any workcenter

        # Determine task start and end time
        if task.get('chunk_eligible', False) and solver.BooleanValue(task['should_chunk']):
            # For chunked tasks, we need both chunks
            starts = [solver.Value(task['proc_starts_all'][0]), solver.Value(task['proc_starts_all'][1])]
            ends = [solver.Value(task['proc_ends_all'][0]), solver.Value(task['proc_ends_all'][1])]

            # Create an entry for each valid chunk
            for i in range(2):
                if is_valid_time(starts[i]) and is_valid_time(ends[i]) and starts[i] < ends[i]:
                    wc_assignments[wc_id].append({
                        'job_id': job_id,
                        'task_id': task_id,
                        'machine': chosen_machine,
                        'start': starts[i],
                        'end': ends[i],
                        'duration': ends[i] - starts[i],
                        'chunk': i + 1
                    })
                else:
                    print(f"Warning: Skipping invalid time values for Job {job_id}, Task {task_id}, Chunk {i+1}: {starts[i]}-{ends[i]}")
        else:
            # Non-chunked or non-split task
            idx = 2 if task.get('chunk_eligible', False) and not solver.BooleanValue(task['should_chunk']) else 0
            start = solver.Value(task['proc_starts_all'][idx])
            end = solver.Value(task['proc_ends_all'][idx])

            if is_valid_time(start) and is_valid_time(end) and start < end:
                wc_assignments[wc_id].append({
                    'job_id': job_id,
                    'task_id': task_id,
                    'machine': chosen_machine,
                    'start': start,
                    'end': end,
                    'duration': end - start,
                    'chunk': None
                })
            else:
                print(f"Warning: Skipping invalid time values for Job {job_id}, Task {task_id}: {start}-{end}")

    # Now analyze usage for each workcenter
    for wc_id, assignments in wc_assignments.items():
        wc_info = workcenters[wc_id]
        capacity = wc_info['capacity']
        print(f"\nWorkcenter: {wc_id} ({wc_info['name']})")
        print(f"Capacity: {capacity}")

        if not assignments:
            print("  No tasks assigned to this workcenter")
            continue

        print(f"Tasks assigned: {len(assignments)}")

        # Sort tasks by start time
        assignments.sort(key=lambda x: x['start'])

        # Find periods where capacity is exceeded
        time_points = sorted(list(set([a['start'] for a in assignments] + [a['end'] for a in assignments])))
        max_concurrent = 0
        concurrent_periods = []

        for i in range(len(time_points) - 1):
            period_start = time_points[i]
            period_end = time_points[i + 1]

            # Skip zero-length periods
            if period_start == period_end:
                continue

            # Count tasks active during this period
            active_tasks = []
            for a in assignments:
                if a['start'] <= period_start and a['end'] > period_start:
                    active_tasks.append(a)

            concurrent_count = len(active_tasks)
            if concurrent_count > max_concurrent:
                max_concurrent = concurrent_count

            # Record periods with multiple concurrent tasks
            if concurrent_count > 1:
                concurrent_periods.append({
                    'start': period_start,
                    'end': period_end,
                    'count': concurrent_count,
                    'tasks': active_tasks
                })

        print(f"Maximum concurrent tasks: {max_concurrent} (capacity: {capacity})")

        # Check if capacity is ever exceeded
        if max_concurrent > capacity:
            print("WARNING: Workcenter capacity is exceeded!")

        # Print details of concurrent task periods
        if concurrent_periods:
            print("\nPeriods with concurrent tasks:")
            for period in concurrent_periods:
                print(f"  Time {period['start']}-{period['end']} ({period['end']-period['start']} units): {period['count']} tasks")
                for task in period['tasks']:
                    chunk_info = f" (chunk {task['chunk']})" if task['chunk'] is not None else ""
                    print(f"    Job {task['job_id']}, Task {task['task_id']} on Machine {task['machine']}{chunk_info}: {task['start']}-{task['end']}")

        # Print task details
        print("\nTask details:")
        for a in sorted(assignments, key=lambda x: (x['job_id'], x['task_id'], x['start'])):
            chunk_info = f" (chunk {a['chunk']})" if a['chunk'] is not None else ""
            print(f"  Job {a['job_id']}, Task {a['task_id']} on Machine {a['machine']}{chunk_info}: {a['start']}-{a['end']} (duration: {a['duration']})")

    print("\n=== END OF WORKCENTER USAGE REPORT ===")


def build_machine_map_from_csv():
    """
    Build machine map directly from CSV files with more robust handling.
    """
    try:
        # Load new_jobs.csv
        new_df = pd.read_csv("new_jobs.csv")

        # Extract all unique machine names
        all_machines = set()

        if 'MachineOptions' in new_df.columns:
            for machine in new_df['MachineOptions'].dropna().unique():
                if isinstance(machine, str):
                    # Handle comma-separated machines
                    if ',' in machine:
                        for m in machine.split(','):
                            all_machines.add(m.strip())
                    else:
                        all_machines.add(machine.strip())

        # Try to load fixed_jobs.csv
        try:
            fixed_df = pd.read_csv("fixed_jobs.csv")
            if 'Machine' in fixed_df.columns:
                all_machines.update(fixed_df['Machine'].dropna().unique())
        except Exception as e:
            print(f"Note: Couldn't load fixed_jobs.csv: {e}")

        # Try to load machine_capacity.csv
        try:
            capacity_df = pd.read_csv("machine_capacity.csv")
            if 'Machine' in capacity_df.columns:
                all_machines.update(capacity_df['Machine'].dropna().unique())
        except Exception as e:
            print(f"Note: Couldn't load machine_capacity.csv: {e}")

        # Sort machines for consistent indexing
        all_machines = sorted(list(all_machines))
        print(f"Direct CSV read found {len(all_machines)} unique machines")

        # Create machine map and default costs
        machine_map = {machine: idx for idx, machine in enumerate(all_machines)}
        machine_cost_per_unit = {idx: 4 for idx in range(len(all_machines))}  # Default cost 4

        return machine_map, machine_cost_per_unit, len(all_machines)

    except Exception as e:
        print(f"Error building machine map from CSV: {e}")
        print("Falling back to hardcoded machine map")

        # Fallback to hardcoded map
        machine_map = {
            "CNC-1": 0, "Lathe-2": 1, "Miller-3": 2, "Drill-4": 3, "Grinder-5": 4,
            "Saw-6": 5, "Press-7": 6, "Lathe-8": 7, "Mill-9": 8, "Polish-10": 9
        }
        machine_cost_per_unit = {i: 4 for i in range(10)}
        return machine_map, machine_cost_per_unit, 10


def build_machine_map(new_df, fixed_df, config, default_machine_cost=4):
    """
    Build machine map directly from the CSV file to avoid any DataFrame issues.
    """
    all_machines = set()

    # Try direct CSV reading for reliable machine names
    try:
        with open('new_jobs.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'MachineOptions' in row and row['MachineOptions']:
                    all_machines.add(row['MachineOptions'])

        print(f"Direct CSV read found {len(all_machines)} unique machines")
    except Exception as e:
        print(f"Error reading directly from CSV: {e}")

    # If no machines found, fallback to DataFrame
    if not all_machines and 'MachineOptions' in new_df.columns:
        for machine in new_df['MachineOptions'].dropna().unique():
            all_machines.add(str(machine))
        print(f"DataFrame extraction found {len(all_machines)} unique machines")

    # Add fixed_df machines if any
    if not fixed_df.empty and 'Machine' in fixed_df.columns:
        for machine in fixed_df['Machine'].dropna().unique():
            all_machines.add(str(machine))

    # Final fallback
    if not all_machines:
        all_machines.add("Default-Machine")
        print("No machines found, using Default-Machine")

    # Sort for consistency
    all_machines = sorted(all_machines)

    # Create machine maps
    machine_map = {machine: idx for idx, machine in enumerate(all_machines)}
    reverse_machine_map = {idx: machine for machine, idx in machine_map.items()}

    # Create machine costs
    machine_cost_per_unit = {idx: default_machine_cost for idx in range(len(all_machines))}

    # Update config
    machines_count = len(machine_map)
    config["machine_parameters"]["machines_count"] = machines_count

    # Debug output
    print(f"\nBuilt machine map with {len(machine_map)} machines")
    print("Machine mapping:")
    for machine, idx in machine_map.items():
        print(f"  {machine} -> index {idx} (cost: {machine_cost_per_unit[idx]})")

    return machine_map, machine_cost_per_unit, machines_count, reverse_machine_map

def merge_configs(base_config, user_config):
    """
    Recursively merge user_config into base_config.

    Args:
        base_config: Base configuration to update
        user_config: User-provided configuration values
    """
    for key, value in user_config.items():
        # If both values are dictionaries, merge them recursively
        if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
            merge_configs(base_config[key], value)
        else:
            # Otherwise, overwrite the value
            base_config[key] = value

# Helper functions
def load_data():
    fixed_df = pd.read_csv("fixed_jobs.csv")
    new_df = pd.read_csv("new_jobs.csv")
    capacity_df = pd.read_csv("machine_capacity.csv")
    return fixed_df, new_df, capacity_df


def preprocess_data(fixed_df, new_df, capacity_df, machine_map):
    # Handle fixed jobs
    if not fixed_df.empty and 'Machine' in fixed_df.columns:
        fixed_df['MachineIdx'] = fixed_df['Machine'].map(machine_map)
        fixed_df.dropna(subset=['MachineIdx'], inplace=True)
        if not fixed_df.empty:
            fixed_df['MachineIdx'] = fixed_df['MachineIdx'].astype(int)

    # Debug machine options before conversion
    print("Initial MachineOptions examples:")
    if 'MachineOptions' in new_df.columns:
        print(new_df['MachineOptions'].head().to_dict())

    # Handle MachineOptions in new_df
    if 'MachineOptions' in new_df.columns:
        # Create a new column to hold the machine indices
        def convert_machine_option(machine_str):
            if isinstance(machine_str, str):
                if ',' in machine_str:
                    # Handle multiple machines
                    return [machine_map[m.strip()] for m in machine_str.split(',')]
                else:
                    # Handle single machine
                    return [machine_map[machine_str.strip()]]
            return [machine_map[machine_str]]  # Handle other cases

        # Apply the conversion and store in a new column temporarily
        new_df['MachineIndices'] = new_df['MachineOptions'].apply(convert_machine_option)

        # Replace the original column
        new_df['MachineOptions'] = new_df['MachineIndices']
        new_df.drop('MachineIndices', axis=1, inplace=True)

        # Debug after conversion
        print("Converted MachineOptions examples:")
        print(new_df['MachineOptions'].head().to_dict())

    # Handle capacity data
    if not capacity_df.empty and 'Machine' in capacity_df.columns:
        capacity_df['MachineIdx'] = capacity_df['Machine'].map(machine_map)
        capacity_df.dropna(subset=['MachineIdx'], inplace=True)
        if not capacity_df.empty:
            capacity_df['MachineIdx'] = capacity_df['MachineIdx'].astype(int)

    print("Preprocessing complete. MachineOptions converted to indices.")


def process_machine_options(machine_option):
    if not machine_option or pd.isna(machine_option):
        # Default to first machine if empty
        first_machine = next(iter(machine_map.keys())) if machine_map else "Machine-0"
        return [machine_map.get(first_machine, 0)]

    # Handle both comma-separated and single machine options
    if isinstance(machine_option, str) and ',' in machine_option:
        machines = [m.strip() for m in machine_option.split(',')]
    else:
        machines = [str(machine_option).strip()]

    # Map to indices, filtering out any machines not in the map
    machine_indices = []
    for m in machines:
        if m in machine_map:
            machine_indices.append(machine_map[m])
        else:
            print(f"Warning: Machine '{m}' not found in machine map. Skipping.")

    # If no valid machines found, use first available machine
    if not machine_indices and machine_map:
        first_machine = next(iter(machine_map.keys()))
        print(f"Warning: No valid machines found for '{machine_option}'. Using {first_machine} as default.")
        machine_indices = [machine_map[first_machine]]

    return machine_indices

    # Apply the processing function


def build_fixed_jobs(fixed_df):
    """
    Build list of fixed jobs from DataFrame.
    Handles empty DataFrames properly.
    """
    # Check if fixed_df is empty
    if fixed_df.empty:
        print("Fixed jobs DataFrame is empty. No fixed jobs to process.")
        return []

    # Ensure required columns exist
    if 'MachineIdx' not in fixed_df.columns:
        print("Creating MachineIdx column with default value 0")
        fixed_df['MachineIdx'] = 0

    if 'StartTime' not in fixed_df.columns:
        print("Creating StartTime column with default value 0")
        fixed_df['StartTime'] = 0

    if 'EndTime' not in fixed_df.columns:
        print("Creating EndTime column with default value 0")
        fixed_df['EndTime'] = 0

    if 'ToolID' not in fixed_df.columns:
        print("Creating ToolID column with default value 1")
        fixed_df['ToolID'] = 1

    # Create list of fixed jobs
    fixed_jobs = list(fixed_df[['MachineIdx', 'StartTime', 'EndTime', 'ToolID']].itertuples(index=False, name=None))
    print(f"Fixed jobs: {fixed_jobs}")
    return fixed_jobs


def build_jobs_data(new_df):
    job_groups = new_df.groupby('JobNumber')
    jobs_data = []
    for job_num, group in job_groups:
        tasks = []
        group = group.sort_values('TaskID')
        for _, row in group.iterrows():
            # Make sure machine_options is correctly accessed as a list
            machine_options = row['MachineOptions']
            # Log to verify machine_options format
            print(f"Task {row['JobNumber']}-{row['TaskID']} machine options: {machine_options}")

            # Remaining code as before
            must_do = int(row['MustDo']) if 'MustDo' in row and not pd.isna(row['MustDo']) else None
            task_preempt = 1 if row['TaskPreempt'] == True or (
                    isinstance(row['TaskPreempt'], (int, float)) and row['TaskPreempt'] == 1) else 0
            min_split_task = int(row['MinSplitTask']) if 'MinSplitTask' in row and not pd.isna(
                row['MinSplitTask']) else 1

            state_id = int(row['StateID']) if 'StateID' in row and not pd.isna(row['StateID']) else 0

            task = (
                machine_options[0],  # Use first machine as default
                int(row['ProcTime']),
                int(row['Slack']) if not pd.isna(row['Slack']) else 0,
                int(row['Setup']),
                int(row['Due']),
                int(row['Priority']),
                int(row['Dwell']) if not pd.isna(row['Dwell']) else 0,
                int(row['Release']),
                row['JobPreempt'],
                task_preempt,
                int(row['MinSplitJob']),
                min_split_task,
                float(row['ReleaseThreshold']),
                must_do,
                float(row['CustomerWeight']),
                row['IsRush'],
                int(row['ToolID']),
                machine_options,  # Make sure this is passed as a list
                state_id
            )
            tasks.append(task)
        jobs_data.append(tasks)
    return jobs_data, job_groups


def compute_downtime_and_horizon(capacity_df, new_df, machines_count=10):
    total_processing = sum(int(job.ProcTime) + int(job.Setup) for job in new_df.itertuples())
    total_dwell = sum(int(job.Dwell) if not pd.isna(job.Dwell) else 0 for job in new_df.itertuples())
    max_release = max(int(job.Release) for job in new_df.itertuples())
    unavailable_time = {m: 0 for m in range(machines_count)}
    downtime_windows = {m: [] for m in range(machines_count)}
    max_capacity_end = 0

    for machine_idx in range(machines_count):
        machine_df = capacity_df[capacity_df['MachineIdx'] == machine_idx].sort_values('StartTime')
        if not machine_df.empty:
            prev_end = 0
            for row in machine_df.itertuples():
                if row.StartTime > prev_end:
                    unavailable_time[machine_idx] += row.StartTime - prev_end
                    downtime_windows[machine_idx].append((prev_end, row.StartTime))
                prev_end = row.EndTime
            max_capacity_end = max(max_capacity_end, prev_end)

    max_unavailable = max(unavailable_time.values())
    horizon = total_processing + total_dwell + max_release + max_unavailable + max_capacity_end + 1000
    print(
        f"Calculated horizon: {horizon}, Max unavailable time: {max_unavailable}, Max capacity end: {max_capacity_end}")
    for m in downtime_windows:
        print(f"Machine {m} downtime windows: {downtime_windows[m]}")
    return downtime_windows, horizon


def build_fixed_intervals(model, fixed_jobs, fixed_machine_intervals, fixed_tool_intervals):
    for machine, start, end, tool_id in fixed_jobs:
        fixed_start = model.NewIntVar(start, start, f'fixed_start_m{machine}_t{tool_id}')
        fixed_duration = model.NewIntVar(end - start, end - start, f'fixed_duration_m{machine}_t{tool_id}')
        fixed_end = model.NewIntVar(end, end, f'fixed_end_m{machine}_t{tool_id}')
        model.Add(fixed_end == fixed_start + fixed_duration)
        fixed_interval = model.NewIntervalVar(fixed_start, fixed_duration, fixed_end, f'fixed_m{machine}_t{tool_id}')
        fixed_machine_intervals[machine].append(fixed_interval)
        if tool_id in fixed_tool_intervals:
            fixed_tool_intervals[tool_id].append(fixed_interval)


def build_unavailability_intervals(model, capacity_df, unavailable_intervals, downtime_windows, machines_count):
    """
    Enhanced unavailability intervals builder that properly interprets machine capacity data.

    The capacity_df contains time windows when machines are available for work.
    This function creates unavailability intervals for the periods between these windows
    and also for the downtime periods specified in the capacity_df.
    """
    for machine_idx in range(machines_count):
        machine_df = capacity_df[capacity_df['MachineIdx'] == machine_idx].sort_values('StartTime')
        if not machine_df.empty:
            prev_end = 0
            for row in machine_df.itertuples():
                # Create unavailability interval for the gap between capacity windows
                if row.StartTime > prev_end:
                    start = model.NewIntVar(prev_end, prev_end, f'unavail_start_m{machine_idx}_{prev_end}')
                    duration = model.NewIntVar(row.StartTime - prev_end, row.StartTime - prev_end,
                                               f'unavail_duration_m{machine_idx}_{prev_end}')
                    end = model.NewIntVar(row.StartTime, row.StartTime, f'unavail_end_m{machine_idx}_{prev_end}')
                    model.Add(end == start + duration)
                    interval = model.NewIntervalVar(start, duration, end, f'unavail_m{machine_idx}_{prev_end}')
                    unavailable_intervals[machine_idx].append(interval)
                    print(f"Added unavailability interval for machine {machine_idx}: {prev_end}-{row.StartTime}")

                    # Also track this as a downtime window for constraints
                    if machine_idx not in downtime_windows:
                        downtime_windows[machine_idx] = []
                    downtime_windows[machine_idx].append((prev_end, row.StartTime))

                prev_end = row.EndTime


def is_chunk_eligible(task):
    return task[9] == 1


def determine_chunk_sizes(proc_time, min_chunk_size, machine_downtimes):
    if not machine_downtimes or proc_time < min_chunk_size * 2:
        return [proc_time]
    half_size = max(proc_time // 2, min_chunk_size)
    second_half = proc_time - half_size
    if second_half < min_chunk_size:
        half_size = proc_time - min_chunk_size
        second_half = min_chunk_size
    return [half_size, second_half]


def build_tasks(model, jobs_data, job_groups, downtime_windows, machine_to_intervals,
                tool_intervals, horizon, use_penalties, max_tools, setup_time_matrix=None,
                setup_scrap_matrix=None, use_seq_dependent_setup=False):
    """
    Build task variables and constraints for the optimization model.
    Enhanced with debugging for machine options and assignments.

    Args:
        model: CP-SAT model
        jobs_data: List of jobs with tasks
        job_groups: Grouped job data from pandas
        downtime_windows: Dictionary of machine downtime windows
        machine_to_intervals: Dictionary mapping machines to their intervals
        tool_intervals: Dictionary of tool intervals
        horizon: Time horizon for the model
        use_penalties: Flag to use penalties in objective
        max_tools: Dictionary of maximum tool usage
        setup_time_matrix: Matrix of setup times (if using sequence-dependent setup)
        setup_scrap_matrix: Matrix of setup scrap (if using sequence-dependent setup)
        use_seq_dependent_setup: Flag to use sequence-dependent setup

    Returns:
        all_tasks: Dictionary of all task variables
        total_setup_scrap: Total setup scrap cost
    """
    all_tasks = {}
    total_setup_scrap = 0

    print(f"\nBuilding tasks for {len(jobs_data)} jobs...")

    # Process each job
    for job_id, job in enumerate(jobs_data):
        job_name = list(job_groups.groups.keys())[job_id] if job_groups is not None else f"Job_{job_id}"
        print(f"\nProcessing job {job_name} with {len(job)} tasks")
        job_must_do = None

        # Process each task in the job
        for task_id, task_data in enumerate(job):
            suffix = f'_j{job_id}_t{task_id}'

            # Debug machine options
            machine_options = task_data[17]
            print(f"  Task {task_id} machine options: {machine_options}")

            # Validate machine options
            if not isinstance(machine_options, list) or len(machine_options) == 0:
                print(f"ERROR: Invalid machine options for task {job_name}-{task_id}: {machine_options}")
                if not isinstance(machine_options, list):
                    machine_options = [machine_options]
                if len(machine_options) == 0:
                    print(f"CRITICAL ERROR: No valid machines for task {job_name}-{task_id}")
                    machine_options = [0]  # Default to machine 0 as fallback

            # Get previous task data (if any) for sequence-dependent setup
            prev_task_data = None
            if task_id > 0:
                prev_task_data = job[task_id - 1]

            # Create machine choice variables
            machine_choice = {}
            for m in machine_options:
                var_name = f'{suffix}_machine_{m}'
                machine_choice[m] = model.NewBoolVar(var_name)
                print(f"    Created choice variable for machine {m}: {var_name}")

            # Ensure exactly one machine is chosen
            if machine_choice:
                model.AddExactlyOne(list(machine_choice.values()))
                print(f"    Added constraint: exactly one of {list(machine_choice.keys())} must be chosen")
            else:
                print(f"    ERROR: No machine choice variables created")

            # Setup phase with sequence-dependent times if enabled
            if use_seq_dependent_setup and setup_time_matrix is not None and setup_scrap_matrix is not None:
                setup_start, setup_end, setup_intervals, setup_scrap = setup_phase(
                    model, suffix, task_data, prev_task_data, setup_time_matrix, setup_scrap_matrix,
                    machine_options, machine_choice, machine_to_intervals, tool_intervals,
                    task_data[16], horizon, max_tools, use_seq_dependent_setup
                )
                total_setup_scrap += setup_scrap
                print(f"    Setup phase: sequence-dependent, scrap = {setup_scrap}")
            else:
                # Standard setup phase
                setup_start, setup_end, setup_intervals = standard_setup_phase(
                    model, suffix, task_data[3], machine_options, machine_choice,
                    machine_to_intervals, tool_intervals, task_data[16], horizon, max_tools
                )
                setup_scrap = 0
                print(f"    Setup phase: standard, duration = {task_data[3]}")

            # Processing phase
            if is_chunk_eligible(task_data):
                print(f"    Task {job_name}-{task_id} is chunk-eligible with min_split_task={task_data[11]}")
                proc_data = setup_chunked_processing(
                    model, suffix, task_data, horizon, setup_end, machine_options,
                    machine_choice, downtime_windows, machine_to_intervals, tool_intervals,
                    task_data[16], max_tools, job_id, task_id
                )
                print(f"    Processing phase: chunked, durations = {proc_data['durations']}")
            else:
                proc_data = setup_non_chunked_processing(
                    model, suffix, task_data[1], horizon, setup_end, machine_options,
                    machine_choice, machine_to_intervals, tool_intervals, task_data[16],
                    max_tools, downtime_windows
                )
                print(f"    Processing phase: non-chunked, duration = {task_data[1]}")

            # Dwell phase
            dwell_start, dwell_end, dwell_intervals = setup_dwell_phase(
                model, suffix, task_data[6], proc_data['proc_ends'],
                machine_options, machine_choice, machine_to_intervals,
                tool_intervals, task_data[16], horizon, max_tools
            )
            if task_data[6] > 0:
                print(f"    Dwell phase: duration = {task_data[6]}")
            else:
                print(f"    No dwell phase")

            # Determine task end
            task_end = model.NewIntVar(0, horizon, f'end_{suffix}')
            if task_data[6] > 0:  # If dwell exists
                model.Add(task_end == dwell_end)
            else:
                model.AddMaxEquality(task_end, [proc_data['proc_ends']])

            # Create task dictionary
            task_dict = {
                'task_end': task_end,
                'machine': task_data[0],
                'setup_start': setup_start,
                'setup_end': setup_end,
                'setup_scrap': setup_scrap,
                'proc_starts_all': proc_data['proc_starts_all'],
                'proc_ends_all': proc_data['proc_ends_all'],
                'proc_sub_intervals': proc_data['proc_sub_intervals'],
                'slack': task_data[2],
                'dwell': task_data[6],
                'priority': task_data[5],
                'customer_weight': task_data[14],
                'is_rush': task_data[15],
                'tool_id': task_data[16],
                'machine_choice': machine_choice,
                'setup_intervals': setup_intervals,
                'durations': proc_data['durations'],
                'straddling_reward': proc_data['straddling_reward'],
                'chunk_eligible': is_chunk_eligible(task_data),
                'state_id': task_data[18] if len(task_data) > 18 else 0
            }

            if task_dict['chunk_eligible']:
                task_dict['should_chunk'] = proc_data['should_chunk']

            if task_data[6] > 0:  # If dwell exists
                task_dict['dwell_start'] = dwell_start
                task_dict['dwell_end'] = dwell_end
                task_dict['dwell_intervals'] = dwell_intervals

            # Record if this is a MustDo task
            if task_data[13] is not None and task_id == len(job) - 1:
                job_must_do = task_data[13]
                print(f"    This is a MustDo task with due date {job_must_do}")

            # Add constraints for this task
            add_task_constraints(model, task_dict, task_data, job_id, task_id, job,
                                 all_tasks, horizon, use_penalties, job_must_do, suffix)
            print(f"    Added task constraints")

            # Store task in all_tasks dictionary
            all_tasks[(job_id, task_id)] = task_dict
            print(f"    Task {job_name}-{task_id} successfully created")

    print(f"Built {len(all_tasks)} tasks with total setup scrap of {total_setup_scrap}")
    return all_tasks, total_setup_scrap
def standard_setup_phase(model, suffix, setup_time, machine_options, machine_choice,
                        machine_to_intervals, tool_intervals, tool_id, horizon, max_tools):
    """
    Create setup phase variables and constraints without sequence-dependent setup.
    """
    setup_start = model.NewIntVar(0, horizon, f'{suffix}_setup_start')
    setup_duration = model.NewIntVar(setup_time, setup_time, f'{suffix}_setup_duration')
    setup_end = model.NewIntVar(0, horizon, f'{suffix}_setup_end')
    model.Add(setup_end == setup_start + setup_duration)

    setup_intervals = []
    for m in machine_options:
        is_present = model.NewBoolVar(f'{suffix}_m{m}_setup_present')
        model.Add(is_present == machine_choice[m])
        interval = model.NewOptionalIntervalVar(setup_start, setup_duration, setup_end, is_present,
                                                f'{suffix}_m{m}_setup')
        setup_intervals.append(interval)
        machine_to_intervals[m].append(interval)
        if tool_id in max_tools:
            tool_intervals[tool_id].append(interval)

    return setup_start, setup_end, setup_intervals

def initialize_task(model, task_data, suffix, machine_to_intervals, tool_intervals, horizon, max_tools, job_id, task_id,
                    downtime_windows):
    """
    Initialize a task with variables for setup, processing, and dwell phases.
    """
    # Extract just what we need from task_data to avoid unpacking errors
    machine_options = []
    proc_time = 10
    slack = 0
    setup = 0
    due = 0
    priority = 1
    dwell = 0
    release = 0
    job_preempt = False
    task_preempt = False
    min_split_job = 0
    min_split_task = 0
    release_threshold = 0.25
    must_do = None
    customer_weight = 1.0
    is_rush = False
    tool_id = 0
    state_id = 0

    # Safely extract fields from task_data
    if len(task_data) > 2:
        machine_options = task_data[2]
    if len(task_data) > 3:
        proc_time = task_data[3]
    if len(task_data) > 4:
        slack = task_data[4]
    if len(task_data) > 5:
        setup = task_data[5]
    if len(task_data) > 6:
        due = task_data[6]
    if len(task_data) > 7:
        priority = task_data[7]
    if len(task_data) > 8:
        dwell = task_data[8]
    if len(task_data) > 9:
        release = task_data[9]
    if len(task_data) > 10:
        job_preempt = task_data[10]
    if len(task_data) > 11:
        task_preempt = task_data[11]
    if len(task_data) > 12:
        min_split_job = task_data[12]
    if len(task_data) > 13:
        min_split_task = task_data[13]
    if len(task_data) > 14:
        release_threshold = task_data[14]
    if len(task_data) > 15:
        must_do = task_data[15]
    if len(task_data) > 16:
        customer_weight = task_data[16]
    if len(task_data) > 17:
        is_rush = task_data[17]
    if len(task_data) > 18:
        tool_id = task_data[18]
    if len(task_data) > 19:
        state_id = task_data[19]

    # Ensure machine_options is a list/iterable
    if isinstance(machine_options, (int, float, str)):
        machine_options = [machine_options]
    elif machine_options is None:
        machine_options = [0]

    # IMPORTANT: Ensure all machine_options exist in machine_to_intervals
    valid_machine_options = []
    for m in machine_options:
        if m in machine_to_intervals:
            valid_machine_options.append(m)
        else:
            print(f"Warning: Machine {m} not found in machine_to_intervals. Skipping.")

    # If no valid machines left, use the first available machine
    if not valid_machine_options and machine_to_intervals:
        first_machine = next(iter(machine_to_intervals.keys()))
        print(f"Warning: No valid machines for task {job_id},{task_id}. Using machine {first_machine} as default.")
        valid_machine_options = [first_machine]

    # Update machine_options with valid machines
    machine_options = valid_machine_options

    # Use first machine option as default_machine for display purposes
    default_machine = machine_options[0] if machine_options else 0

    machine_choice = {m: model.NewBoolVar(f'{suffix}_machine_{m}') for m in machine_options}
    model.AddExactlyOne(list(machine_choice.values()))

    # Simple setup phase implementation to avoid dependency on external setup_phase function
    setup_start = model.NewIntVar(0, horizon, f'{suffix}_setup_start')
    setup_duration = model.NewIntVar(setup, setup, f'{suffix}_setup_duration')
    setup_end = model.NewIntVar(0, horizon, f'{suffix}_setup_end')
    model.Add(setup_end == setup_start + setup_duration)

    setup_intervals = []
    for m in machine_options:
        is_present = model.NewBoolVar(f'{suffix}_m{m}_setup_present')
        model.Add(is_present == machine_choice[m])
        interval = model.NewOptionalIntervalVar(setup_start, setup_duration, setup_end, is_present,
                                                f'{suffix}_m{m}_setup')
        setup_intervals.append(interval)
        machine_to_intervals[m].append(interval)
        if tool_id in max_tools:
            tool_intervals[tool_id].append(interval)

    setup_scrap = 0  # Default value for setup_scrap

    if is_chunk_eligible(task_data):
        print(f"Task {job_id},{task_id} is chunk-eligible with min_split_task={min_split_task}")
        proc_data = setup_chunked_processing(model, suffix, task_data, horizon, setup_end, machine_options,
                                             machine_choice, downtime_windows, machine_to_intervals, tool_intervals,
                                             tool_id, max_tools, job_id, task_id)
    else:
        proc_data = setup_non_chunked_processing(model, suffix, proc_time, horizon, setup_end, machine_options,
                                                 machine_choice, machine_to_intervals, tool_intervals, tool_id,
                                                 max_tools, downtime_windows)

    dwell_start, dwell_end, dwell_intervals = setup_dwell_phase(model, suffix, dwell, proc_data['proc_ends'],
                                                                machine_options, machine_choice, machine_to_intervals,
                                                                tool_intervals, tool_id, horizon, max_tools)

    task_end = model.NewIntVar(0, horizon, f'end_{suffix}')
    if dwell > 0:
        model.Add(task_end == dwell_end)
    else:
        model.AddMaxEquality(task_end, [proc_data['proc_ends']])

    task_dict = {
        'task_end': task_end,
        'machine': default_machine,
        'setup_start': setup_start,
        'setup_end': setup_end,
        'setup_scrap': setup_scrap,
        'proc_starts_all': proc_data['proc_starts_all'],
        'proc_ends_all': proc_data['proc_ends_all'],
        'proc_sub_intervals': proc_data['proc_sub_intervals'],
        'slack': slack,
        'dwell': dwell,
        'priority': priority,
        'customer_weight': customer_weight,
        'is_rush': is_rush,
        'tool_id': tool_id,
        'machine_choice': machine_choice,
        'setup_intervals': setup_intervals,
        'durations': proc_data['durations'],
        'straddling_reward': proc_data['straddling_reward'],
        'chunk_eligible': is_chunk_eligible(task_data),
        'state_id': state_id
    }

    if task_dict['chunk_eligible']:
        task_dict['should_chunk'] = proc_data['should_chunk']

    if dwell > 0:
        task_dict['dwell_start'] = dwell_start
        task_dict['dwell_end'] = dwell_end
        task_dict['dwell_intervals'] = dwell_intervals

    return task_dict


def setup_phase(model, suffix, task_data, prev_task_data, setup_time_matrix, setup_scrap_matrix,
                machine_options, machine_choice, machine_to_intervals, tool_intervals, tool_id,
                horizon, max_tools, use_seq_dependent_setup):
    """
    Modified setup_phase function that handles sequence-dependent setup times.

    Args:
        task_data: Current task data tuple
        prev_task_data: Previous task data tuple (or None if this is the first task)
        setup_time_matrix: 2D numpy array of setup times
        setup_scrap_matrix: 2D numpy array of setup scrap amounts
        use_seq_dependent_setup: Boolean flag to enable/disable sequence-dependent setups
    """
    # Default setup time from task data
    default_setup_time = task_data[3]

    # Determine actual setup time based on transitions if enabled
    if use_seq_dependent_setup and setup_time_matrix is not None and prev_task_data is not None:
        # Extract state IDs (assuming they're at index 18 in the task tuple)
        current_state_id = task_data[18]
        prev_state_id = prev_task_data[18]

        # Look up setup time and scrap directly from matrices
        setup_time = setup_time_matrix[prev_state_id, current_state_id]
        setup_scrap = setup_scrap_matrix[prev_state_id, current_state_id]

        # Fall back to default if transition not defined (setup_time == 0)
        if setup_time == 0:
            setup_time = default_setup_time
            setup_scrap = 0

        print(f"Task {suffix}: State transition {prev_state_id}->{current_state_id}, "
              f"Setup time: {setup_time}, Scrap: {setup_scrap}")
    else:
        # Use default setup time from task data
        setup_time = default_setup_time
        setup_scrap = 0

    # Create setup variables as before
    setup_start = model.NewIntVar(0, horizon, f'{suffix}_setup_start')
    setup_duration = model.NewIntVar(setup_time, setup_time, f'{suffix}_setup_duration')
    setup_end = model.NewIntVar(0, horizon, f'{suffix}_setup_end')
    model.Add(setup_end == setup_start + setup_duration)

    setup_intervals = []
    for m in machine_options:
        is_present = model.NewBoolVar(f'{suffix}_m{m}_setup_present')
        model.Add(is_present == machine_choice[m])
        interval = model.NewOptionalIntervalVar(setup_start, setup_duration, setup_end, is_present,
                                                f'{suffix}_m{m}_setup')
        setup_intervals.append(interval)
        machine_to_intervals[m].append(interval)
        if tool_id in max_tools:
            tool_intervals[tool_id].append(interval)

    # Return setup variables and scrap amount
    return setup_start, setup_end, setup_intervals, setup_scrap


# Functions to add to ProFunctv2.6.py for sequence-dependent setup times

def load_transition_matrices():
    """
    Load transition matrices for setup time and setup scrap.
    Uses numpy arrays for fast O(1) lookups.

    Returns:
        setup_time_matrix: 2D numpy array where [from_state, to_state] gives setup time
        setup_scrap_matrix: 2D numpy array where [from_state, to_state] gives setup scrap
        max_state_id: The maximum state ID in the system
    """
    try:
        transition_df = pd.read_csv("setup_transitions.csv")
        # Find the maximum state ID to size our arrays
        max_state_id = max(
            transition_df['FromStateID'].max(),
            transition_df['ToStateID'].max()
        )

        # Initialize matrices with default values
        # Using int32 for memory efficiency
        setup_time_matrix = np.zeros((max_state_id + 1, max_state_id + 1), dtype=np.int32)
        setup_scrap_matrix = np.zeros((max_state_id + 1, max_state_id + 1), dtype=np.int32)

        # Fill matrices with transition data
        for _, row in transition_df.iterrows():
            from_id = int(row['FromStateID'])
            to_id = int(row['ToStateID'])
            setup_time_matrix[from_id, to_id] = int(row['SetupTime'])
            setup_scrap_matrix[from_id, to_id] = int(row['SetupScrap'])

        print(f"Loaded setup transition matrices with {len(transition_df)} transitions")
        print(f"Maximum state ID: {max_state_id}")

        return setup_time_matrix, setup_scrap_matrix, max_state_id

    except FileNotFoundError:
        print("setup_transitions.csv not found. Using default setup times from new_jobs.csv.")
        # Return empty matrices to signal we should use default setup times
        return None, None, 0


def setup_chunked_processing(model, suffix, task_data, horizon, setup_end, machine_options,
                            machine_choice, downtime_windows, machine_to_intervals, tool_intervals,
                            tool_id, max_tools, job_id, task_id):
    """
    Enhanced approach for chunk-eligible tasks that uses MinSplitTask from the task data.
    """
    _, proc_time, _, setup, _, _, _, _, _, _, min_split_job, min_split_task, _, _, _, _, _, machine_options, _ = task_data

    print(f"Setting up chunked processing for task {job_id},{task_id} with min_split_task={min_split_task}")

    # Variable to decide if task should be chunked
    should_chunk = model.NewBoolVar(f'{suffix}_should_chunk')

    # First chunk variables
    proc_start1 = model.NewIntVar(0, horizon, f'{suffix}_proc_start1')
    proc_duration1 = model.NewIntVar(min_split_task, proc_time - min_split_task, f'{suffix}_proc_duration1')
    proc_end1 = model.NewIntVar(0, horizon, f'{suffix}_proc_end1')
    model.Add(proc_end1 == proc_start1 + proc_duration1)

    # Second chunk variables
    proc_start2 = model.NewIntVar(0, horizon, f'{suffix}_proc_start2')
    proc_duration2 = model.NewIntVar(min_split_task, proc_time - min_split_task, f'{suffix}_proc_duration2')
    proc_end2 = model.NewIntVar(0, horizon, f'{suffix}_proc_end2')
    model.Add(proc_end2 == proc_start2 + proc_duration2)

    # Total processing time constraint
    model.Add(proc_duration1 + proc_duration2 == proc_time)

    # Non-chunked variables
    proc_start_no_chunk = model.NewIntVar(0, horizon, f'{suffix}_proc_start_no_chunk')
    proc_duration_no_chunk = model.NewIntVar(proc_time, proc_time, f'{suffix}_proc_duration_no_chunk')
    proc_end_no_chunk = model.NewIntVar(0, horizon, f'{suffix}_proc_end_no_chunk')
    model.Add(proc_end_no_chunk == proc_start_no_chunk + proc_duration_no_chunk)

    # First chunk must start immediately after setup unless delayed by downtime
    model.Add(proc_start1 == setup_end).OnlyEnforceIf(should_chunk)
    model.Add(proc_start_no_chunk == setup_end).OnlyEnforceIf(should_chunk.Not())

    # Second chunk must start after first chunk (enforced per machine later)
    model.Add(proc_start2 > proc_end1).OnlyEnforceIf(should_chunk)

    # Create variables for straddling downtime windows (crossing between chunks)
    straddling_vars = []

    for m in machine_options:
        if m in downtime_windows and downtime_windows[m]:
            m_straddling_vars = []
            print(f"Machine {m} has {len(downtime_windows[m])} downtime windows")

            for dt_idx, (dt_start, dt_end) in enumerate(downtime_windows[m]):
                straddle_dt = model.NewBoolVar(f'{suffix}_m{m}_straddle_dt{dt_idx}')

                # Conditions for straddling:
                # 1. This machine is chosen
                # 2. Task is chunked
                # 3. First chunk ends exactly at downtime start
                # 4. Second chunk starts exactly at downtime end
                model.Add(machine_choice[m] == 1).OnlyEnforceIf(straddle_dt)
                model.Add(should_chunk == 1).OnlyEnforceIf(straddle_dt)
                model.Add(proc_end1 == dt_start).OnlyEnforceIf(straddle_dt)
                model.Add(proc_start2 == dt_end).OnlyEnforceIf(straddle_dt)

                m_straddling_vars.append(straddle_dt)

            # This machine straddles some downtime if any of its straddling vars is true
            if m_straddling_vars:
                machine_straddles = model.NewBoolVar(f'{suffix}_m{m}_straddles_some_dt')
                model.AddBoolAnd([machine_choice[m], should_chunk]).OnlyEnforceIf(machine_straddles)
                model.Add(sum(m_straddling_vars) >= 1).OnlyEnforceIf(machine_straddles)
                straddling_vars.append(machine_straddles)

    # Determine if chunking is even possible based on downtime availability
    if straddling_vars:
        can_straddle = model.NewBoolVar(f'{suffix}_can_straddle')
        model.Add(sum(straddling_vars) >= 1).OnlyEnforceIf(can_straddle)
        model.Add(sum(straddling_vars) == 0).OnlyEnforceIf(can_straddle.Not())

        # We only chunk if we can straddle downtime (this is the core policy)
        model.AddImplication(should_chunk, can_straddle)
        print(f"  Task {job_id},{task_id} has potential to straddle downtime")
    else:
        # If no downtime to straddle, no chunking
        model.Add(should_chunk == 0)
        can_straddle = model.NewConstant(0)
        print(f"  Task {job_id},{task_id} has no downtime to straddle, will not be chunked")

    # Create interval variables for each potential machine
    proc_intervals1, proc_intervals2, proc_intervals_no_chunk = [], [], []

    # First chunk intervals
    for m in machine_options:
        is_present1 = model.NewBoolVar(f'{suffix}_m{m}_proc1_present')
        model.AddBoolAnd([machine_choice[m], should_chunk]).OnlyEnforceIf(is_present1)
        interval1 = model.NewOptionalIntervalVar(proc_start1, proc_duration1, proc_end1, is_present1,
                                               f'{suffix}_m{m}_proc1')
        proc_intervals1.append(interval1)
        machine_to_intervals[m].append(interval1)
        if tool_id in max_tools:
            tool_intervals[tool_id].append(interval1)

    # Second chunk intervals
    for m in machine_options:
        is_present2 = model.NewBoolVar(f'{suffix}_m{m}_proc2_present')
        model.AddBoolAnd([machine_choice[m], should_chunk]).OnlyEnforceIf(is_present2)
        interval2 = model.NewOptionalIntervalVar(proc_start2, proc_duration2, proc_end2, is_present2,
                                               f'{suffix}_m{m}_proc2')
        proc_intervals2.append(interval2)
        machine_to_intervals[m].append(interval2)
        if tool_id in max_tools:
            tool_intervals[tool_id].append(interval2)

    # Non-chunked intervals
    for m in machine_options:
        is_present_no_chunk = model.NewBoolVar(f'{suffix}_m{m}_proc_no_chunk_present')
        model.AddBoolAnd([machine_choice[m], should_chunk.Not()]).OnlyEnforceIf(is_present_no_chunk)
        interval_no_chunk = model.NewOptionalIntervalVar(proc_start_no_chunk, proc_duration_no_chunk, proc_end_no_chunk,
                                                       is_present_no_chunk, f'{suffix}_m{m}_proc_no_chunk')
        proc_intervals_no_chunk.append(interval_no_chunk)
        machine_to_intervals[m].append(interval_no_chunk)
        if tool_id in max_tools:
            tool_intervals[tool_id].append(interval_no_chunk)

    # Add special constraints to ensure chunks are properly scheduled within capacity windows
    for m in machine_options:
        if m in downtime_windows and downtime_windows[m]:
            for dt_idx, (dt_start, dt_end) in enumerate(downtime_windows[m]):
                # Create variables to detect if chunk would overlap with downtime
                overlap1 = model.NewBoolVar(f'{suffix}_m{m}_dt{dt_idx}_overlap1')
                overlap2 = model.NewBoolVar(f'{suffix}_m{m}_dt{dt_idx}_overlap2')

                # Chunk 1 overlaps downtime if it starts before dt_end and ends after dt_start
                model.AddBoolAnd([
                    machine_choice[m],
                    should_chunk
                ]).OnlyEnforceIf(overlap1)

                # Either chunk1 ends before downtime starts or starts after downtime ends
                ends_before1 = model.NewBoolVar(f'{suffix}_m{m}_dt{dt_idx}_ends_before1')
                model.Add(proc_end1 <= dt_start).OnlyEnforceIf(ends_before1)

                starts_after1 = model.NewBoolVar(f'{suffix}_m{m}_dt{dt_idx}_starts_after1')
                model.Add(proc_start1 >= dt_end).OnlyEnforceIf(starts_after1)

                model.AddBoolOr([ends_before1, starts_after1]).OnlyEnforceIf(overlap1.Not())

                # Same for chunk 2
                model.AddBoolAnd([
                    machine_choice[m],
                    should_chunk
                ]).OnlyEnforceIf(overlap2)

                ends_before2 = model.NewBoolVar(f'{suffix}_m{m}_dt{dt_idx}_ends_before2')
                model.Add(proc_end2 <= dt_start).OnlyEnforceIf(ends_before2)

                starts_after2 = model.NewBoolVar(f'{suffix}_m{m}_dt{dt_idx}_starts_after2')
                model.Add(proc_start2 >= dt_end).OnlyEnforceIf(starts_after2)

                model.AddBoolOr([ends_before2, starts_after2]).OnlyEnforceIf(overlap2.Not())

    # Create straddling reward variable - using a consistent value for all tasks
    straddling_reward = model.NewIntVar(0, 5000, f'{suffix}_straddling_reward')

    # Reward is given when the task can straddle downtime
    if straddling_vars:
        model.Add(straddling_reward == 5000).OnlyEnforceIf(can_straddle)
        model.Add(straddling_reward == 0).OnlyEnforceIf(can_straddle.Not())
    else:
        model.Add(straddling_reward == 0)

    # Create variable for the overall end time of processing
    proc_ends = model.NewIntVar(0, horizon, f'{suffix}_proc_end_max')
    model.Add(proc_ends == proc_end2).OnlyEnforceIf(should_chunk)
    model.Add(proc_ends == proc_end_no_chunk).OnlyEnforceIf(should_chunk.Not())

    # Create default chunk sizes for reporting
    chunk_sizes_by_machine = {m: determine_chunk_sizes(proc_time, min_split_task, downtime_windows.get(m, [])) for m in
                              machine_options}
    default_chunks = [proc_time // 2, proc_time - proc_time // 2]

    return {
        'proc_starts_all': [proc_start1, proc_start2, proc_start_no_chunk],
        'proc_ends_all': [proc_end1, proc_end2, proc_end_no_chunk],
        'proc_sub_intervals': [proc_intervals1, proc_intervals2, proc_intervals_no_chunk],
        'proc_ends': proc_ends,
        'durations': [setup] + default_chunks,
        'straddling_reward': straddling_reward,
        'should_chunk': should_chunk
    }


def setup_non_chunked_processing(model, suffix, proc_time, horizon, setup_end, machine_options, machine_choice,
                                 machine_to_intervals, tool_intervals, tool_id, max_tools, downtime_windows):
    """
    Improved approach for non-chunked tasks that forces processing to start
    immediately after setup unless it needs to be delayed for downtime.

    This version handles post-setup downtime better by ensuring processing
    starts immediately after the downtime window if setup ends at downtime start.
    """
    proc_start = model.NewIntVar(0, horizon, f'{suffix}_proc_start')
    proc_duration = model.NewIntVar(proc_time, proc_time, f'{suffix}_proc_duration')
    proc_end = model.NewIntVar(0, horizon, f'{suffix}_proc_end')
    model.Add(proc_end == proc_start + proc_duration)

    # By default, processing starts exactly after setup
    model.Add(proc_start == setup_end)

    # For each machine, check if processing needs to be delayed due to downtime
    for m in machine_options:
        if m in downtime_windows and downtime_windows[m]:
            for dt_idx, (dt_start, dt_end) in enumerate(downtime_windows[m]):
                # Create variable to detect if setup ends exactly at downtime start
                setup_ends_at_dt = model.NewBoolVar(f'{suffix}_m{m}_setup_ends_at_dt_{dt_idx}')

                # Setup ends exactly at downtime start
                model.Add(setup_end == dt_start).OnlyEnforceIf(setup_ends_at_dt)
                model.Add(setup_end != dt_start).OnlyEnforceIf(setup_ends_at_dt.Not())

                # If setup ends at downtime start AND this machine is selected,
                # then processing must start exactly at downtime end
                dt_delay = model.NewBoolVar(f'{suffix}_m{m}_dt{dt_idx}_delay')

                # Create the AND condition correctly
                model.AddBoolAnd([setup_ends_at_dt, machine_choice[m]]).OnlyEnforceIf(dt_delay)
                model.AddBoolOr([setup_ends_at_dt.Not(), machine_choice[m].Not()]).OnlyEnforceIf(dt_delay.Not())

                # If delay is needed, processing starts exactly at downtime end
                model.Add(proc_start == dt_end).OnlyEnforceIf(dt_delay)

    # Create intervals for each machine
    proc_intervals = []
    for m in machine_options:
        is_present = model.NewBoolVar(f'{suffix}_m{m}_proc_present')
        model.Add(is_present == machine_choice[m])
        interval = model.NewOptionalIntervalVar(proc_start, proc_duration, proc_end, is_present, f'{suffix}_m{m}_proc')
        proc_intervals.append(interval)
        machine_to_intervals[m].append(interval)
        if tool_id in max_tools:
            tool_intervals[tool_id].append(interval)

    return {
        'proc_starts_all': [proc_start],
        'proc_ends_all': [proc_end],
        'proc_sub_intervals': [proc_intervals],
        'proc_ends': proc_end,
        'durations': [proc_time],
        'straddling_reward': model.NewConstant(0)
    }


def setup_dwell_phase(model, suffix, dwell, proc_ends, machine_options, machine_choice, machine_to_intervals,
                      tool_intervals, tool_id, horizon, max_tools):
    """
    Sets up dwell phase variables. Dwell doesn't actually use the machine,
    so we don't add dwell intervals to machine_to_intervals.
    """
    if dwell > 0:
        dwell_start = model.NewIntVar(0, horizon, f'{suffix}_dwell_start')
        dwell_duration = model.NewIntVar(dwell, dwell, f'{suffix}_dwell_duration')
        dwell_end = model.NewIntVar(0, horizon, f'{suffix}_dwell_end')
        model.Add(dwell_end == dwell_start + dwell_duration)
        model.AddMaxEquality(dwell_start, [proc_ends])

        dwell_intervals = []
        for m in machine_options:
            is_present = model.NewBoolVar(f'{suffix}_m{m}_dwell_present')
            model.Add(is_present == machine_choice[m])
            interval = model.NewOptionalIntervalVar(dwell_start, dwell_duration, dwell_end, is_present,
                                                    f'{suffix}_m{m}_dwell')
            dwell_intervals.append(interval)

            # Don't add dwell intervals to machine_to_intervals since they don't use the machine
            # machine_to_intervals[m].append(interval)

            if tool_id in max_tools:
                tool_intervals[tool_id].append(interval)

        return dwell_start, dwell_end, dwell_intervals

    return None, None, None


def add_task_constraints(model, task_dict, task_data, job_id, task_id, job, all_tasks, horizon, use_penalties,
                         job_must_do, suffix):
    release = task_data[7]
    due = task_data[4]
    slack = task_data[2]

    if task_id == 0:
        model.Add(task_dict['setup_start'] >= release)
    else:
        prev_task = all_tasks[(job_id, task_id - 1)]
        model.Add(task_dict['setup_start'] >= prev_task['task_end'])
        if release > 0:
            model.Add(task_dict['setup_start'] >= release)

    if (not use_penalties) and (task_id == len(job) - 1) and (job_must_do is not None):
        model.Add(task_dict['task_end'] <= job_must_do)

    tardiness = model.NewIntVar(0, horizon, f'tardiness_{suffix}')  # suffix is now in scope
    effective_due = horizon if due == 0 else due
    model.Add(tardiness >= task_dict['task_end'] - (effective_due + slack))
    model.Add(tardiness >= 0)
    task_dict['tardiness'] = tardiness

    if use_penalties and job_must_do is not None and task_id == len(job) - 1:
        must_do_tardiness = model.NewIntVar(0, horizon, f'must_do_tardiness_{suffix}')
        model.Add(must_do_tardiness >= task_dict['task_end'] - job_must_do)
        model.Add(must_do_tardiness >= 0)
        task_dict['must_do_tardiness'] = must_do_tardiness


def add_enforced_downtime_constraint(model, task, machine, dt_start, dt_end, job_id, task_id,
                                     chunk_idx, is_chunked, label):
    """
    Add enforced constraints for a specific chunk or non-chunked version of a task.
    Returns the number of constraints added.
    """
    constraints_added = 0
    proc_start = task['proc_starts_all'][chunk_idx]
    proc_end = task['proc_ends_all'][chunk_idx]

    # Create enforced constraint variables
    task_on_machine = model.NewBoolVar(f'j{job_id}_t{task_id}_on_m{machine}_{label}')

    # Condition: This machine is chosen AND either (task is chunked AND we're checking chunks)
    # OR (task is not chunked AND we're checking non-chunked version)
    should_chunk = task['should_chunk']
    if is_chunked:
        model.AddBoolAnd([task['machine_choice'][machine], should_chunk]).OnlyEnforceIf(task_on_machine)
    else:
        model.AddBoolAnd([task['machine_choice'][machine], should_chunk.Not()]).OnlyEnforceIf(task_on_machine)

    # Create overlap avoidance variables
    prevent_overlap = model.NewBoolVar(f'prevent_{label}_overlap_j{job_id}_t{task_id}_m{machine}_dt{dt_start}')
    model.Add(task_on_machine == 1).OnlyEnforceIf(prevent_overlap)

    # Either ends before downtime or starts after downtime
    end_before_dt = model.NewBoolVar(f'{label}_end_before_dt_j{job_id}_t{task_id}_m{machine}_dt{dt_start}')
    model.Add(proc_end <= dt_start).OnlyEnforceIf(end_before_dt)
    model.Add(proc_end > dt_start).OnlyEnforceIf(end_before_dt.Not())

    start_after_dt = model.NewBoolVar(f'{label}_start_after_dt_j{job_id}_t{task_id}_m{machine}_dt{dt_start}')
    model.Add(proc_start >= dt_end).OnlyEnforceIf(start_after_dt)
    model.Add(proc_start < dt_end).OnlyEnforceIf(start_after_dt.Not())

    model.AddBoolOr([end_before_dt, start_after_dt]).OnlyEnforceIf(prevent_overlap)

    # Enforce the constraint: if this configuration is active, it must avoid downtime
    model.Add(prevent_overlap == task_on_machine)

    return 1


def add_non_chunked_downtime_constraint(model, task, machine, dt_start, dt_end, job_id, task_id, proc_idx):
    """
    Add constraints to prevent a non-chunked task from overlapping with downtime.
    Returns the number of constraints added.
    """
    constraints_added = 0
    proc_start = task['proc_starts_all'][proc_idx]
    proc_end = task['proc_ends_all'][proc_idx]

    # Create enforced constraints to prevent overlap with downtime
    prevent_overlap = model.NewBoolVar(f'prevent_overlap_j{job_id}_t{task_id}_m{machine}_dt{dt_start}')

    # Only apply if this machine is chosen
    model.Add(task['machine_choice'][machine] == 1).OnlyEnforceIf(prevent_overlap)

    # Either ends before downtime or starts after downtime
    end_before_dt = model.NewBoolVar(f'end_before_dt_j{job_id}_t{task_id}_m{machine}_dt{dt_start}')
    model.Add(proc_end <= dt_start).OnlyEnforceIf(end_before_dt)
    model.Add(proc_end > dt_start).OnlyEnforceIf(end_before_dt.Not())

    start_after_dt = model.NewBoolVar(f'start_after_dt_j{job_id}_t{task_id}_m{machine}_dt{dt_start}')
    model.Add(proc_start >= dt_end).OnlyEnforceIf(start_after_dt)
    model.Add(proc_start < dt_end).OnlyEnforceIf(start_after_dt.Not())

    model.AddBoolOr([end_before_dt, start_after_dt]).OnlyEnforceIf(prevent_overlap)

    # Enforce the constraint unconditionally when this machine is chosen
    model.Add(prevent_overlap == task['machine_choice'][machine])

    return 1


def add_downtime_constraints(model, all_tasks, downtime_windows, machine_to_intervals):
    """
    Add explicit constraints to prevent any processing from starting or occurring
    during machine downtime windows.
    """
    print("Adding downtime constraints...")
    constraints_added = 0

    for (job_id, task_id), task in all_tasks.items():
        for m in task['machine_choice']:
            if m in downtime_windows and downtime_windows[m]:
                print(
                    f"  Checking task {job_id},{task_id} for machine {m} with {len(downtime_windows[m])} downtime windows")

                # Create a variable that indicates this machine is chosen
                machine_chosen = task['machine_choice'][m]

                # Handle task based on whether it's chunk-eligible
                if task.get('chunk_eligible', False) and 'should_chunk' in task:
                    # Handle chunked task - we need separate constraints for each possible state
                    should_chunk = task['should_chunk']

                    # First chunk when chunked
                    for dt_start, dt_end in downtime_windows[m]:
                        chunk1_avoids_downtime = add_strict_downtime_constraint(
                            model, task['proc_starts_all'][0], task['proc_ends_all'][0],
                            dt_start, dt_end, job_id, task_id, m, f"chunk1_{dt_start}")

                        # Only enforce when this machine is chosen AND task is chunked
                        combined_choice = model.NewBoolVar(f'j{job_id}_t{task_id}_m{m}_chunked_choice_{dt_start}')
                        model.AddBoolAnd([machine_chosen, should_chunk]).OnlyEnforceIf(combined_choice)
                        model.AddBoolOr([machine_chosen.Not(), should_chunk.Not()]).OnlyEnforceIf(combined_choice.Not())

                        # If this configuration is active, chunk must avoid downtime
                        model.AddImplication(combined_choice, chunk1_avoids_downtime)
                        constraints_added += 1

                    # Second chunk when chunked
                    for dt_start, dt_end in downtime_windows[m]:
                        chunk2_avoids_downtime = add_strict_downtime_constraint(
                            model, task['proc_starts_all'][1], task['proc_ends_all'][1],
                            dt_start, dt_end, job_id, task_id, m, f"chunk2_{dt_start}")

                        # Only enforce when this machine is chosen AND task is chunked
                        combined_choice = model.NewBoolVar(f'j{job_id}_t{task_id}_m{m}_chunked_choice2_{dt_start}')
                        model.AddBoolAnd([machine_chosen, should_chunk]).OnlyEnforceIf(combined_choice)
                        model.AddBoolOr([machine_chosen.Not(), should_chunk.Not()]).OnlyEnforceIf(combined_choice.Not())

                        # If this configuration is active, chunk must avoid downtime
                        model.AddImplication(combined_choice, chunk2_avoids_downtime)
                        constraints_added += 1

                    # Non-chunked version
                    for dt_start, dt_end in downtime_windows[m]:
                        nonchunk_avoids_downtime = add_strict_downtime_constraint(
                            model, task['proc_starts_all'][2], task['proc_ends_all'][2],
                            dt_start, dt_end, job_id, task_id, m, f"nonchunk_{dt_start}")

                        # Only enforce when this machine is chosen AND task is NOT chunked
                        combined_choice = model.NewBoolVar(f'j{job_id}_t{task_id}_m{m}_nonchunked_choice_{dt_start}')
                        model.AddBoolAnd([machine_chosen, should_chunk.Not()]).OnlyEnforceIf(combined_choice)
                        model.AddBoolOr([machine_chosen.Not(), should_chunk]).OnlyEnforceIf(combined_choice.Not())

                        # If this configuration is active, non-chunked version must avoid downtime
                        model.AddImplication(combined_choice, nonchunk_avoids_downtime)
                        constraints_added += 1
                else:
                    # Regular non-chunked task
                    for dt_start, dt_end in downtime_windows[m]:
                        task_avoids_downtime = add_strict_downtime_constraint(
                            model, task['proc_starts_all'][0], task['proc_ends_all'][0],
                            dt_start, dt_end, job_id, task_id, m, f"regular_{dt_start}")

                        # If this machine is chosen, task must avoid downtime
                        model.AddImplication(machine_chosen, task_avoids_downtime)
                        constraints_added += 1

    print(f"Added {constraints_added} downtime constraints total")
    return constraints_added


def add_strict_downtime_constraint(model, proc_start, proc_end, dt_start, dt_end, job_id, task_id, machine, label):
    """
    Creates a boolean variable that is true if processing does not overlap with downtime.

    Args:
        proc_start: Start variable of processing
        proc_end: End variable of processing
        dt_start: Start time of downtime window
        dt_end: End time of downtime window
        job_id, task_id, machine, label: Used for variable naming

    Returns:
        A boolean variable that is true if and only if processing does not overlap with downtime
    """
    # Constraint is satisfied if either:
    # 1. Processing ends before or at downtime start, OR
    # 2. Processing starts after or at downtime end
    avoids_downtime = model.NewBoolVar(f'j{job_id}_t{task_id}_m{machine}_{label}_avoids_downtime')

    ends_before = model.NewBoolVar(f'j{job_id}_t{task_id}_m{machine}_{label}_ends_before')
    model.Add(proc_end <= dt_start).OnlyEnforceIf(ends_before)
    model.Add(proc_end > dt_start).OnlyEnforceIf(ends_before.Not())

    starts_after = model.NewBoolVar(f'j{job_id}_t{task_id}_m{machine}_{label}_starts_after')
    model.Add(proc_start >= dt_end).OnlyEnforceIf(starts_after)
    model.Add(proc_start < dt_end).OnlyEnforceIf(starts_after.Not())

    # Satisfy constraint if either condition is true
    model.AddBoolOr([ends_before, starts_after]).OnlyEnforceIf(avoids_downtime)
    model.AddBoolAnd([ends_before.Not(), starts_after.Not()]).OnlyEnforceIf(avoids_downtime.Not())

    return avoids_downtime


def add_no_overlap_constraints(model, fixed_machine_intervals, machine_to_intervals, unavailable_intervals,
                               machines_count):
    """
    Enhanced to ensure proper no-overlap constraints between tasks.

    This function ensures that no intervals for the same machine will overlap,
    including both fixed intervals, scheduled task intervals, and unavailable intervals.
    """
    # Get all unique machine indices to consider
    all_machines = set(machine_to_intervals.keys())

    # Make sure we include any machines up to machines_count
    for m in range(machines_count):
        all_machines.add(m)

    # Add no-overlap constraints for each machine
    for machine in all_machines:
        # Get intervals, handling cases where some dictionaries don't have an entry
        fixed_ints = fixed_machine_intervals.get(machine, [])
        machine_ints = machine_to_intervals.get(machine, [])
        unavail_ints = unavailable_intervals.get(machine, [])

        # Collect all intervals for this machine
        intervals = fixed_ints + machine_ints + unavail_ints

        # Add a no-overlap constraint for the machine
        if intervals:
            model.AddNoOverlap(intervals)
            print(f"Adding no-overlap constraint for machine {machine} with {len(intervals)} intervals")
        else:
            print(f"No intervals found for machine {machine}, skipping no-overlap constraint")
def add_tool_capacity_constraints(model, fixed_tool_intervals, tool_intervals, max_tools):
    for tool_id in max_tools:
        fixed_ints = fixed_tool_intervals.get(tool_id, [])
        new_ints = tool_intervals.get(tool_id, [])
        if fixed_ints or new_ints:
            model.AddCumulative(fixed_ints + new_ints, [1] * (len(fixed_ints) + len(new_ints)), max_tools[tool_id])


def compute_valid_processing_start_times(model, setup_end, machine_options, machine_choice, downtime_windows, suffix):
    """
    Creates constraints to ensure processing doesn't start during downtime windows.
    Returns a dictionary mapping each machine to its adjusted processing start time.
    """
    proc_start_times = {}

    for m in machine_options:
        # Default: processing starts immediately after setup
        proc_start_m = model.NewIntVar(0, model.GetIntegerUpperBound(setup_end), f'{suffix}_proc_start_adjusted_m{m}')

        if m in downtime_windows and downtime_windows[m]:
            # For each downtime window, check if setup ends at its start
            setup_ends_at_dt_vars = []

            for dt_idx, (dt_start, dt_end) in enumerate(downtime_windows[m]):
                # Variable to detect if setup ends exactly at downtime start
                setup_ends_at_dt = model.NewBoolVar(f'{suffix}_m{m}_setup_ends_at_dt_{dt_idx}')
                model.Add(setup_end == dt_start).OnlyEnforceIf(setup_ends_at_dt)
                model.Add(setup_end != dt_start).OnlyEnforceIf(setup_ends_at_dt.Not())

                # If setup ends at downtime start, processing must start after downtime
                model.Add(proc_start_m >= dt_end).OnlyEnforceIf(setup_ends_at_dt)

                setup_ends_at_dt_vars.append(setup_ends_at_dt)

            # If setup doesn't end at any downtime start, processing starts immediately after setup
            setup_ends_at_any_dt = model.NewBoolVar(f'{suffix}_m{m}_setup_ends_at_any_dt')
            model.Add(sum(setup_ends_at_dt_vars) >= 1).OnlyEnforceIf(setup_ends_at_any_dt)
            model.Add(sum(setup_ends_at_dt_vars) == 0).OnlyEnforceIf(setup_ends_at_any_dt.Not())

            # If not ending at downtime, just start after setup
            model.Add(proc_start_m == setup_end).OnlyEnforceIf(setup_ends_at_any_dt.Not())
        else:
            # No downtime for this machine, processing starts immediately after setup
            model.Add(proc_start_m == setup_end)

        # Only apply this constraint if this machine is chosen
        proc_start_times[m] = proc_start_m

    return proc_start_times


def add_capacity_window_constraints(model, all_tasks, downtime_windows, machine_to_intervals):
    """
    Improved function to add constraints for capacity windows on all machines.

    Key improvements:
    1. Better detection of tasks that overlap with capacity windows
    2. Stricter enforcement of the single-job-per-window constraint
    3. Special handling for chunked tasks to ensure chunks respect window boundaries
    """
    # Track all the capacity windows from machine_capacity.csv
    capacity_windows = {}

    # Extract capacity windows from machine_capacity CSV data
    if 'single_job_capacity' not in downtime_windows:
        return

    # Process all machines with their capacity windows
    for machine_idx, windows in downtime_windows['single_job_capacity'].items():
        print(f"Adding single-job capacity constraints for machine {machine_idx}")

        # Store the capacity windows for this machine
        if machine_idx not in capacity_windows:
            capacity_windows[machine_idx] = []

        for window_idx, (window_start, window_end) in enumerate(windows):
            capacity_windows[machine_idx].append((window_start, window_end))

            # Create a list of tasks that could potentially be scheduled in this window
            window_jobs = []

            # Check each task to see if it could run in this window
            for (job_id, task_id), task in all_tasks.items():
                # Only consider tasks that could run on this machine
                if machine_idx not in task['machine_choice']:
                    continue

                # For non-chunked tasks
                if not task.get('chunk_eligible', False):
                    # Single proc phase
                    proc_start = task['proc_starts_all'][0]
                    proc_end = task['proc_ends_all'][0]

                    # Create a variable to indicate if this task overlaps with the window
                    task_overlaps_window = model.NewBoolVar(
                        f'j{job_id}_t{task_id}_overlaps_m{machine_idx}_w{window_idx}')

                    # Conditions for overlap:
                    # 1. This machine is chosen
                    # 2. Task starts before window ends
                    # 3. Task ends after window starts
                    model.Add(task['machine_choice'][machine_idx] == 1).OnlyEnforceIf(task_overlaps_window)

                    # Check if task starts before window ends
                    starts_before_end = model.NewBoolVar(
                        f'j{job_id}_t{task_id}_starts_before_end_m{machine_idx}_w{window_idx}')
                    model.Add(proc_start < window_end).OnlyEnforceIf(starts_before_end)
                    model.Add(proc_start >= window_end).OnlyEnforceIf(starts_before_end.Not())

                    # Check if task ends after window starts
                    ends_after_start = model.NewBoolVar(
                        f'j{job_id}_t{task_id}_ends_after_start_m{machine_idx}_w{window_idx}')
                    model.Add(proc_end > window_start).OnlyEnforceIf(ends_after_start)
                    model.Add(proc_end <= window_start).OnlyEnforceIf(ends_after_start.Not())

                    # Task overlaps with window if both conditions are true
                    model.AddBoolAnd(
                        [starts_before_end, ends_after_start, task['machine_choice'][machine_idx]]).OnlyEnforceIf(
                        task_overlaps_window)
                    model.AddBoolOr([starts_before_end.Not(), ends_after_start.Not(),
                                     task['machine_choice'][machine_idx].Not()]).OnlyEnforceIf(
                        task_overlaps_window.Not())

                    # Add this task to the window jobs list
                    window_jobs.append(task_overlaps_window)
                else:
                    # For chunked tasks, check both chunks separately
                    should_chunk = task.get('should_chunk', None)
                    if should_chunk is not None:
                        # First chunk
                        proc_start1 = task['proc_starts_all'][0]
                        proc_end1 = task['proc_ends_all'][0]

                        # Check if first chunk overlaps with window
                        chunk1_overlaps = model.NewBoolVar(
                            f'j{job_id}_t{task_id}_chunk1_overlaps_m{machine_idx}_w{window_idx}')

                        model.AddBoolAnd([task['machine_choice'][machine_idx], should_chunk]).OnlyEnforceIf(
                            chunk1_overlaps)

                        # Overlap conditions for chunk 1
                        starts_before_end1 = model.NewBoolVar(
                            f'j{job_id}_t{task_id}_ch1_starts_before_end_m{machine_idx}_w{window_idx}')
                        model.Add(proc_start1 < window_end).OnlyEnforceIf(starts_before_end1)
                        model.Add(proc_start1 >= window_end).OnlyEnforceIf(starts_before_end1.Not())

                        ends_after_start1 = model.NewBoolVar(
                            f'j{job_id}_t{task_id}_ch1_ends_after_start_m{machine_idx}_w{window_idx}')
                        model.Add(proc_end1 > window_start).OnlyEnforceIf(ends_after_start1)
                        model.Add(proc_end1 <= window_start).OnlyEnforceIf(ends_after_start1.Not())

                        model.AddBoolAnd([starts_before_end1, ends_after_start1, task['machine_choice'][machine_idx],
                                          should_chunk]).OnlyEnforceIf(chunk1_overlaps)
                        model.AddBoolOr([starts_before_end1.Not(), ends_after_start1.Not(),
                                         task['machine_choice'][machine_idx].Not(), should_chunk.Not()]).OnlyEnforceIf(
                            chunk1_overlaps.Not())

                        window_jobs.append(chunk1_overlaps)

                        # Second chunk
                        proc_start2 = task['proc_starts_all'][1]
                        proc_end2 = task['proc_ends_all'][1]

                        # Check if second chunk overlaps with window
                        chunk2_overlaps = model.NewBoolVar(
                            f'j{job_id}_t{task_id}_chunk2_overlaps_m{machine_idx}_w{window_idx}')

                        model.AddBoolAnd([task['machine_choice'][machine_idx], should_chunk]).OnlyEnforceIf(
                            chunk2_overlaps)

                        # Overlap conditions for chunk 2
                        starts_before_end2 = model.NewBoolVar(
                            f'j{job_id}_t{task_id}_ch2_starts_before_end_m{machine_idx}_w{window_idx}')
                        model.Add(proc_start2 < window_end).OnlyEnforceIf(starts_before_end2)
                        model.Add(proc_start2 >= window_end).OnlyEnforceIf(starts_before_end2.Not())

                        ends_after_start2 = model.NewBoolVar(
                            f'j{job_id}_t{task_id}_ch2_ends_after_start_m{machine_idx}_w{window_idx}')
                        model.Add(proc_end2 > window_start).OnlyEnforceIf(ends_after_start2)
                        model.Add(proc_end2 <= window_start).OnlyEnforceIf(ends_after_start2.Not())

                        model.AddBoolAnd([starts_before_end2, ends_after_start2, task['machine_choice'][machine_idx],
                                          should_chunk]).OnlyEnforceIf(chunk2_overlaps)
                        model.AddBoolOr([starts_before_end2.Not(), ends_after_start2.Not(),
                                         task['machine_choice'][machine_idx].Not(), should_chunk.Not()]).OnlyEnforceIf(
                            chunk2_overlaps.Not())

                        window_jobs.append(chunk2_overlaps)

                        # Non-chunked case
                        proc_start_no_chunk = task['proc_starts_all'][2]
                        proc_end_no_chunk = task['proc_ends_all'][2]

                        # Check if non-chunked task overlaps with window
                        no_chunk_overlaps = model.NewBoolVar(
                            f'j{job_id}_t{task_id}_no_chunk_overlaps_m{machine_idx}_w{window_idx}')

                        model.AddBoolAnd([task['machine_choice'][machine_idx], should_chunk.Not()]).OnlyEnforceIf(
                            no_chunk_overlaps)

                        # Overlap conditions for non-chunked case
                        starts_before_end_nc = model.NewBoolVar(
                            f'j{job_id}_t{task_id}_nc_starts_before_end_m{machine_idx}_w{window_idx}')
                        model.Add(proc_start_no_chunk < window_end).OnlyEnforceIf(starts_before_end_nc)
                        model.Add(proc_start_no_chunk >= window_end).OnlyEnforceIf(starts_before_end_nc.Not())

                        ends_after_start_nc = model.NewBoolVar(
                            f'j{job_id}_t{task_id}_nc_ends_after_start_m{machine_idx}_w{window_idx}')
                        model.Add(proc_end_no_chunk > window_start).OnlyEnforceIf(ends_after_start_nc)
                        model.Add(proc_end_no_chunk <= window_start).OnlyEnforceIf(ends_after_start_nc.Not())

                        model.AddBoolAnd(
                            [starts_before_end_nc, ends_after_start_nc, task['machine_choice'][machine_idx],
                             should_chunk.Not()]).OnlyEnforceIf(no_chunk_overlaps)
                        model.AddBoolOr([starts_before_end_nc.Not(), ends_after_start_nc.Not(),
                                         task['machine_choice'][machine_idx].Not(), should_chunk]).OnlyEnforceIf(
                            no_chunk_overlaps.Not())

                        window_jobs.append(no_chunk_overlaps)

            # Ensure at most one job uses this window (can be zero if no job uses it)
            if window_jobs:
                model.Add(sum(window_jobs) <= 1)
                print(
                    f"Added constraint: at most one job can use capacity window {window_start}-{window_end} on machine {machine_idx}")

    # Add additional constraints to ensure processing is entirely contained within capacity windows
    for machine_idx, windows in capacity_windows.items():
        for (job_id, task_id), task in all_tasks.items():
            # Only consider tasks that could run on this machine
            if machine_idx not in task['machine_choice']:
                continue

            # For chunked tasks, ensure each chunk is entirely within a capacity window
            if task.get('chunk_eligible', False) and task.get('should_chunk', None) is not None:
                # For each chunk, it must be entirely within some capacity window
                chunk1_within_window = model.NewBoolVar(f'j{job_id}_t{task_id}_chunk1_within_window_m{machine_idx}')
                chunk2_within_window = model.NewBoolVar(f'j{job_id}_t{task_id}_chunk2_within_window_m{machine_idx}')

                # Only apply these constraints if this machine is chosen and task is chunked
                model.AddBoolAnd([task['machine_choice'][machine_idx], task['should_chunk']]).OnlyEnforceIf(
                    chunk1_within_window)
                model.AddBoolAnd([task['machine_choice'][machine_idx], task['should_chunk']]).OnlyEnforceIf(
                    chunk2_within_window)

                # For each capacity window, check if chunk is entirely within that window
                chunk1_window_vars = []
                chunk2_window_vars = []

                for window_idx, (window_start, window_end) in enumerate(windows):
                    chunk1_in_this_window = model.NewBoolVar(
                        f'j{job_id}_t{task_id}_chunk1_in_window{window_idx}_m{machine_idx}')
                    model.Add(task['proc_starts_all'][0] >= window_start).OnlyEnforceIf(chunk1_in_this_window)
                    model.Add(task['proc_ends_all'][0] <= window_end).OnlyEnforceIf(chunk1_in_this_window)
                    chunk1_window_vars.append(chunk1_in_this_window)

                    chunk2_in_this_window = model.NewBoolVar(
                        f'j{job_id}_t{task_id}_chunk2_in_window{window_idx}_m{machine_idx}')
                    model.Add(task['proc_starts_all'][1] >= window_start).OnlyEnforceIf(chunk2_in_this_window)
                    model.Add(task['proc_ends_all'][1] <= window_end).OnlyEnforceIf(chunk2_in_this_window)
                    chunk2_window_vars.append(chunk2_in_this_window)

                # Chunk must be entirely within at least one capacity window
                if chunk1_window_vars:
                    model.Add(sum(chunk1_window_vars) >= 1).OnlyEnforceIf(chunk1_within_window)
                if chunk2_window_vars:
                    model.Add(sum(chunk2_window_vars) >= 1).OnlyEnforceIf(chunk2_within_window)

                # Enforce that chunks must be within capacity windows if this machine is chosen
                if chunk1_window_vars and chunk2_window_vars:
                    model.AddBoolAnd([chunk1_within_window, chunk2_within_window]).OnlyEnforceIf(
                        model.NewBoolAnd([task['machine_choice'][machine_idx], task['should_chunk']]))

            # For non-chunked tasks, ensure they are entirely within a capacity window
            else:
                task_within_window = model.NewBoolVar(f'j{job_id}_t{task_id}_within_window_m{machine_idx}')
                model.Add(task['machine_choice'][machine_idx] == 1).OnlyEnforceIf(task_within_window)

                # For each capacity window, check if task is entirely within that window
                task_window_vars = []

                for window_idx, (window_start, window_end) in enumerate(windows):
                    proc_start_idx = 2 if task.get('chunk_eligible', False) else 0
                    proc_end_idx = 2 if task.get('chunk_eligible', False) else 0

                    task_in_this_window = model.NewBoolVar(f'j{job_id}_t{task_id}_in_window{window_idx}_m{machine_idx}')
                    model.Add(task['proc_starts_all'][proc_start_idx] >= window_start).OnlyEnforceIf(
                        task_in_this_window)
                    model.Add(task['proc_ends_all'][proc_end_idx] <= window_end).OnlyEnforceIf(task_in_this_window)
                    task_window_vars.append(task_in_this_window)

                # Task must be entirely within at least one capacity window
                if task_window_vars:
                    model.Add(sum(task_window_vars) >= 1).OnlyEnforceIf(task_within_window)

                    # Enforce that task must be within a capacity window if this machine is chosen
                    model.AddBoolAnd([task_within_window]).OnlyEnforceIf(
                        model.NewBoolAnd([task['machine_choice'][machine_idx]]))


def define_objectives(model, all_tasks, jobs_data, horizon, machine_cost_per_unit,
                      setup_cost, weight_tardiness, must_do_penalty, use_penalties,
                      rush_penalty_multiplier, precision_factor, downtime_windows,
                      machine_to_intervals, max_tools, total_setup_scrap=0,
                      setup_scrap_cost_per_unit=0):
    """
    Define the optimization objectives and related constraints.
    Ensures all coefficients and values are integers as required by CP-SAT.

    Args:
        model: CP-SAT model
        all_tasks: Dictionary of all tasks
        jobs_data: List of jobs with tasks
        horizon: Time horizon for the model
        machine_cost_per_unit: Dictionary mapping machines to their costs
        setup_cost: Cost per setup
        weight_tardiness: Weight for tardiness in objective
        must_do_penalty: Penalty for missing must-do tasks
        use_penalties: Flag to use penalties in objective
        rush_penalty_multiplier: Multiplier for rush job penalties
        precision_factor: Factor for precision in calculations
        downtime_windows: Dictionary of machine downtime windows
        machine_to_intervals: Dictionary mapping machines to their intervals
        max_tools: Dictionary of maximum tool usage
        total_setup_scrap: Total setup scrap (for sequence-dependent setup)
        setup_scrap_cost_per_unit: Cost per unit of setup scrap

    Returns:
        makespan: Variable representing the makespan
        total_cost_vars: Dictionary of cost component variables
    """
    # Convert floating-point parameters to integers
    weight_tardiness_int = int(weight_tardiness)
    must_do_penalty_int = int(must_do_penalty)
    rush_penalty_multiplier_int = int(rush_penalty_multiplier)
    straddling_weight = 10  # Integer weight for straddling reward

    # Find the maximum machine cost to use for ranges
    default_machine_cost = 4
    max_machine_cost = default_machine_cost
    if machine_cost_per_unit:
        max_machine_cost = max(machine_cost_per_unit.values())

    # Define makespan
    makespan = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(makespan, [task['task_end'] for task in all_tasks.values()])

    # Production costs
    max_prod_cost = horizon * len(all_tasks) * max_machine_cost
    total_production_cost = model.NewIntVar(0, max_prod_cost, 'total_production_cost')
    production_costs = []

    # Process each task for setup and processing costs
    for job_id, job in enumerate(jobs_data):
        for task_id, task_data in enumerate(job):
            task = all_tasks[(job_id, task_id)]

            # Setup costs for each machine option
            for m in task['machine_choice']:
                # Create cost variable for setup on this machine
                setup_cost_var = model.NewIntVar(0, horizon * max_machine_cost,
                                                 f'setup_cost_j{job_id}_t{task_id}_m{m}')

                # Safely get machine cost with default fallback
                machine_cost = machine_cost_per_unit.get(m, default_machine_cost)

                # Add constraint only if setup time exists
                if task_data[3] > 0:
                    # Machine is chosen: setup cost = setup time × machine cost
                    model.Add(setup_cost_var == task_data[3] * machine_cost).OnlyEnforceIf(
                        task['machine_choice'][m])
                    # Machine not chosen: setup cost = 0
                    model.Add(setup_cost_var == 0).OnlyEnforceIf(task['machine_choice'][m].Not())
                else:
                    # No setup time: setup cost = 0
                    model.Add(setup_cost_var == 0)

                production_costs.append(setup_cost_var)

            # Processing costs calculation
            if task.get('chunk_eligible', False) and 'should_chunk' in task:
                # For chunked tasks, handle each chunk separately
                if len(task['durations']) > 1:  # Ensure we have chunk durations
                    for chunk_idx, duration in enumerate(task['durations'][1:]):
                        proc_cost_var = model.NewIntVar(0, horizon * max_machine_cost,
                                                        f'proc_cost_j{job_id}_t{task_id}_chunk{chunk_idx}')

                        # For each machine option
                        proc_constraints = []
                        for m in task['machine_choice']:
                            machine_cost = machine_cost_per_unit.get(m, default_machine_cost)

                            # If this machine is chosen AND task is chunked
                            chunk_condition = model.NewBoolVar(f'chunk_cond_j{job_id}_t{task_id}_m{m}_ch{chunk_idx}')
                            model.AddBoolAnd([task['machine_choice'][m], task['should_chunk']]).OnlyEnforceIf(
                                chunk_condition)
                            model.AddBoolOr(
                                [task['machine_choice'][m].Not(), task['should_chunk'].Not()]).OnlyEnforceIf(
                                chunk_condition.Not())

                            # Set cost for this machine if chosen
                            chunk_cost = model.NewIntVar(0, horizon * max_machine_cost,
                                                         f'chunk_cost_j{job_id}_t{task_id}_m{m}_ch{chunk_idx}')
                            model.Add(chunk_cost == duration * machine_cost).OnlyEnforceIf(chunk_condition)
                            model.Add(chunk_cost == 0).OnlyEnforceIf(chunk_condition.Not())
                            proc_constraints.append(chunk_cost)

                        # Sum of all possible machine costs (only one will be non-zero)
                        model.Add(proc_cost_var == sum(proc_constraints))
                        production_costs.append(proc_cost_var)

                # Handle non-chunked case as well
                proc_cost_non_chunked = model.NewIntVar(0, horizon * max_machine_cost,
                                                        f'proc_cost_j{job_id}_t{task_id}_no_chunk')

                # For each machine option in non-chunked case
                non_chunk_constraints = []
                for m in task['machine_choice']:
                    machine_cost = machine_cost_per_unit.get(m, default_machine_cost)

                    # If this machine is chosen AND task is NOT chunked
                    non_chunk_condition = model.NewBoolVar(f'no_chunk_cond_j{job_id}_t{task_id}_m{m}')
                    model.AddBoolAnd([task['machine_choice'][m], task['should_chunk'].Not()]).OnlyEnforceIf(
                        non_chunk_condition)
                    model.AddBoolOr([task['machine_choice'][m].Not(), task['should_chunk']]).OnlyEnforceIf(
                        non_chunk_condition.Not())

                    # Set cost for this machine if chosen in non-chunked mode
                    non_chunk_cost = model.NewIntVar(0, horizon * max_machine_cost,
                                                     f'no_chunk_cost_j{job_id}_t{task_id}_m{m}')
                    model.Add(non_chunk_cost == task_data[1] * machine_cost).OnlyEnforceIf(non_chunk_condition)
                    model.Add(non_chunk_cost == 0).OnlyEnforceIf(non_chunk_condition.Not())
                    non_chunk_constraints.append(non_chunk_cost)

                # Sum of all possible machine costs for non-chunked case
                model.Add(proc_cost_non_chunked == sum(non_chunk_constraints))
                production_costs.append(proc_cost_non_chunked)

            else:
                # For standard non-chunked tasks
                proc_cost_var = model.NewIntVar(0, horizon * max_machine_cost,
                                                f'proc_cost_j{job_id}_t{task_id}')

                # For each machine option
                machine_costs = []
                for m in task['machine_choice']:
                    machine_cost = machine_cost_per_unit.get(m, default_machine_cost)

                    # Create a variable for this machine's processing cost
                    m_cost = model.NewIntVar(0, horizon * max_machine_cost,
                                             f'proc_cost_j{job_id}_t{task_id}_m{m}')

                    # If this machine is chosen, cost = proc_time × machine_cost
                    model.Add(m_cost == task_data[1] * machine_cost).OnlyEnforceIf(task['machine_choice'][m])
                    model.Add(m_cost == 0).OnlyEnforceIf(task['machine_choice'][m].Not())
                    machine_costs.append(m_cost)

                # Sum of all possible machine costs
                model.Add(proc_cost_var == sum(machine_costs))
                production_costs.append(proc_cost_var)

    # Sum all production costs
    if production_costs:
        model.Add(total_production_cost == sum(production_costs))
    else:
        model.Add(total_production_cost == 0)

    # Setup costs - fixed cost per setup
    total_setup_cost = model.NewIntVar(0, horizon * setup_cost, 'total_setup_cost')
    setup_count = model.NewIntVar(0, len(all_tasks), 'setup_count')

    # Count setups
    setup_vars = []
    for job_id, job in enumerate(jobs_data):
        for task_id, task_data in enumerate(job):
            if task_data[3] > 0:  # Only count if setup time > 0
                setup_var = model.NewBoolVar(f'setup_exists_j{job_id}_t{task_id}')
                model.Add(setup_var == 1)  # Setup always exists if time > 0
                setup_vars.append(setup_var)

    if setup_vars:
        model.Add(setup_count == sum(setup_vars))
        model.Add(total_setup_cost == setup_cost * setup_count)
    else:
        model.Add(setup_count == 0)
        model.Add(total_setup_cost == 0)

    # Setup scrap costs (for sequence-dependent setup)
    setup_scrap_cost = model.NewIntVar(0, horizon * setup_scrap_cost_per_unit * 1000, 'setup_scrap_cost')
    model.Add(setup_scrap_cost == setup_scrap_cost_per_unit * total_setup_scrap)

    # Tardiness costs - with integer weights
    total_tardiness = model.NewIntVar(0, horizon * len(jobs_data) * 1000, 'total_tardiness')
    weighted_tardiness = model.NewIntVar(0, horizon * len(jobs_data) * 1000 * weight_tardiness_int,
                                         'weighted_tardiness')

    # Get unweighted tardiness values
    tardiness_vars = []
    for job_id, job in enumerate(jobs_data):
        for task_id, task_data in enumerate(job):
            task = all_tasks[(job_id, task_id)]
            if 'tardiness' in task:
                tardiness_vars.append(task['tardiness'])

    # Sum tardiness and apply weight
    if tardiness_vars:
        model.Add(total_tardiness == sum(tardiness_vars))
        model.Add(weighted_tardiness == weight_tardiness_int * total_tardiness)
    else:
        model.Add(total_tardiness == 0)
        model.Add(weighted_tardiness == 0)

    # Must-do tardiness if applicable
    must_do_tardiness_weighted = None
    if use_penalties and any(job[-1][13] is not None for job in jobs_data):
        total_must_do_tardiness = model.NewIntVar(0, horizon * len(jobs_data) * 1000,
                                                  'total_must_do_tardiness')
        must_do_tardiness_weighted = model.NewIntVar(0, horizon * len(jobs_data) * 1000 * must_do_penalty_int,
                                                     'must_do_tardiness_weighted')

        # Get must-do tardiness values
        must_do_vars = []
        for job_id, job in enumerate(jobs_data):
            for task_id, task_data in enumerate(job):
                task = all_tasks[(job_id, task_id)]
                if 'must_do_tardiness' in task:
                    must_do_vars.append(task['must_do_tardiness'])

        # Sum must-do tardiness and apply weight
        if must_do_vars:
            model.Add(total_must_do_tardiness == sum(must_do_vars))
            model.Add(must_do_tardiness_weighted == must_do_penalty_int * total_must_do_tardiness)
        else:
            model.Add(total_must_do_tardiness == 0)
            model.Add(must_do_tardiness_weighted == 0)

    # Straddling reward (for chunking across downtime)
    total_straddling_reward = model.NewIntVar(0, 5000 * len(jobs_data), 'total_straddling_reward')
    straddling_reward_weighted = model.NewIntVar(0, 5000 * len(jobs_data) * straddling_weight,
                                                 'straddling_reward_weighted')

    # Get straddling rewards
    straddling_vars = []
    for task in all_tasks.values():
        if 'straddling_reward' in task:
            straddling_vars.append(task['straddling_reward'])

    # Sum straddling rewards and apply weight
    if straddling_vars:
        model.Add(total_straddling_reward == sum(straddling_vars))
        model.Add(straddling_reward_weighted == straddling_weight * total_straddling_reward)
    else:
        model.Add(total_straddling_reward == 0)
        model.Add(straddling_reward_weighted == 0)

    # Define the objective function
    total_cost = model.NewIntVar(0, horizon * 1000000, 'total_cost')

    # Build objective components
    objective_terms = [
        total_production_cost,
        total_setup_cost,
        setup_scrap_cost,
        weighted_tardiness
    ]

    # Add must-do tardiness if applicable
    if must_do_tardiness_weighted is not None:
        objective_terms.append(must_do_tardiness_weighted)

    # Calculate positive terms and negative terms separately
    positive_terms = sum(objective_terms)

    # Define total cost with pure integer operations
    model.Add(total_cost == positive_terms - straddling_reward_weighted)

    # Minimize total cost
    model.Minimize(total_cost)

    # Create cost variables dictionary for reporting
    cost_vars = {
        'total_production_cost': total_production_cost,
        'total_setup_cost': total_setup_cost,
        'setup_scrap_cost': setup_scrap_cost,
        'total_tardiness': total_tardiness,
        'total_straddling_reward': total_straddling_reward
    }

    # Add must-do tardiness if applicable
    if must_do_tardiness_weighted is not None:
        cost_vars['total_must_do_tardiness'] = total_must_do_tardiness

    return makespan, cost_vars


def print_objective_breakdown(solver, total_cost_vars, weight_tardiness, must_do_penalty,
                              straddling_weight, setup_scrap_cost_per_unit):
    """
    Print a detailed breakdown of all components of the objective function.

    Args:
        solver: Solved CP-SAT solver
        total_cost_vars: Dictionary of cost variables from the objective function
        weight_tardiness: Weight for tardiness penalties
        must_do_penalty: Penalty for must-do tardiness
        straddling_weight: Weight for straddling reward
        setup_scrap_cost_per_unit: Cost per unit of setup scrap
    """
    # Extract all component values
    production_cost = solver.Value(total_cost_vars['total_production_cost'])
    setup_cost = solver.Value(total_cost_vars['total_setup_cost'])
    setup_scrap_cost = solver.Value(total_cost_vars['setup_scrap_cost'])
    tardiness_value = solver.Value(total_cost_vars['total_tardiness'])
    straddling_reward = solver.Value(total_cost_vars['total_straddling_reward'])

    # Get must-do tardiness if it exists
    must_do_tardiness = 0
    if 'total_must_do_tardiness' in total_cost_vars and total_cost_vars['total_must_do_tardiness'] is not None:
        must_do_tardiness = solver.Value(total_cost_vars['total_must_do_tardiness'])

    # Calculate weighted component values (as they would appear in the objective function)
    weighted_tardiness = weight_tardiness * tardiness_value
    weighted_must_do = must_do_penalty * must_do_tardiness
    weighted_straddling = straddling_weight * straddling_reward

    # Calculate total according to the objective function
    total_cost = (
            production_cost +
            setup_cost +
            setup_scrap_cost +
            weighted_tardiness +
            weighted_must_do -
            weighted_straddling
    )

    # Get solver's objective value
    reported_cost = float(solver.ObjectiveValue())

    print("\n=== OBJECTIVE FUNCTION BREAKDOWN ===")
    print(f"{'Component':<30} {'Raw Value':<15} {'Weight':<15} {'Weighted Value':<15} {'% of Total':<15}")
    print("-" * 90)

    # Production cost
    print(
        f"{'Production Cost':<30} {production_cost:<15} {'1':<15} {production_cost:<15,.2f} {production_cost / abs(total_cost) * 100:<15.2f}%")

    # Setup cost
    print(
        f"{'Setup Cost':<30} {setup_cost:<15} {'1':<15} {setup_cost:<15,.2f} {setup_cost / abs(total_cost) * 100:<15.2f}%")

    # Setup scrap cost
    print(
        f"{'Setup Scrap Cost':<30} {setup_scrap_cost:<15} {'1':<15} {setup_scrap_cost:<15,.2f} {setup_scrap_cost / abs(total_cost) * 100:<15.2f}%")

    # Regular tardiness
    print(
        f"{'Tardiness':<30} {tardiness_value:<15} {weight_tardiness:<15} {weighted_tardiness:<15,.2f} {weighted_tardiness / abs(total_cost) * 100:<15.2f}%")

    # Must-do tardiness
    if must_do_tardiness > 0:
        print(
            f"{'Must-Do Tardiness':<30} {must_do_tardiness:<15} {must_do_penalty:<15} {weighted_must_do:<15,.2f} {weighted_must_do / abs(total_cost) * 100:<15.2f}%")
    else:
        print(f"{'Must-Do Tardiness':<30} {must_do_tardiness:<15} {must_do_penalty:<15} {0:<15,.2f} {0:<15.2f}%")

    # Straddling reward (negative contribution)
    print(
        f"{'Straddling Reward':<30} {straddling_reward:<15} {straddling_weight:<15} {-weighted_straddling:<15,.2f} {-weighted_straddling / abs(total_cost) * 100:<15.2f}%")

    # Total
    print("-" * 90)
    print(f"{'TOTAL OBJECTIVE VALUE':<30} {'N/A':<15} {'N/A':<15} {total_cost:<15,.2f} {100:<15.2f}%")

    # Get the solver's objective value for comparison
    print(f"{'SOLVER OBJECTIVE VALUE':<30} {'N/A':<15} {'N/A':<15} {reported_cost:<15,.2f} {'N/A':<15}")

    # Check if total matches the reported total cost
    if abs(total_cost - reported_cost) > 1e-6:
        print(
            f"\nWARNING: Calculated total ({total_cost:,.2f}) doesn't match the reported objective value ({reported_cost:,.2f})!")
        print("This suggests an issue with how the objective function is being calculated or reported.")
        print(f"Difference: {abs(total_cost - reported_cost):,.2f}")

    print("\n=== MUST-DO TARDINESS ANALYSIS ===")
    if must_do_tardiness > 0:
        print(f"Must-do tardiness: {must_do_tardiness} units")
        print(f"Must-do penalty per unit: {must_do_penalty:,}")
        print(f"Weighted must-do penalty: {weighted_must_do:,}")
        print("\nDominance check:")
        other_components = production_cost + setup_cost + setup_scrap_cost + weighted_tardiness - weighted_straddling
        print(f"Must-do penalty: {weighted_must_do:,}")
        print(f"All other components combined: {other_components:,}")

        if weighted_must_do > other_components:
            print("✓ Must-do penalty is DOMINANT (greater than all other components combined)")
        else:
            print("✗ Must-do penalty is NOT dominant (less than or equal to other components combined)")
            print("\nTo make must-do penalty dominant, try increasing it to at least:")
            min_penalty = (other_components / must_do_tardiness) + 1
            print(f"  {min_penalty:,.0f} (instead of current {must_do_penalty:,})")
    else:
        print("No must-do tardiness in the current solution.")

    # Analyze what's going on with the MustDo job
    print("\n=== MUST-DO JOB DETAILS ===")
    found_must_do = False
    for job_id, job in enumerate(total_cost_vars.get('jobs_data', [])):
        if len(job) > 0 and job[-1][13] is not None:  # MustDo is not None
            found_must_do = True
            last_task_id = len(job) - 1
            task = total_cost_vars.get('all_tasks', {}).get((job_id, last_task_id))
            if task is not None:
                must_do_due = job[last_task_id][13]
                task_end = solver.Value(task.get('task_end', 0))
                tardiness = max(0, task_end - must_do_due)
                print(
                    f"Job {job_id}: Must-do deadline = {must_do_due}, Actual end = {task_end}, Tardiness = {tardiness}")
                print(f"Penalty per unit: {must_do_penalty:,}, Total penalty: {tardiness * must_do_penalty:,}")

    if not found_must_do and 'jobs_data' in total_cost_vars:
        print("No must-do jobs found in the data.")

    return total_cost


def original_build_tasks(model, jobs_data, job_groups, downtime_windows, machine_to_intervals, tool_intervals, horizon,
                         use_penalties, max_tools):
    """
    Original version of build_tasks for use when sequence-dependent setup is disabled.
    This function uses the setup times directly from new_jobs.csv.
    """
    all_tasks = {}

    for job_id, job in enumerate(jobs_data):
        job_must_do = None

        for task_id, task_data in enumerate(job):
            suffix = f'_j{job_id}_t{task_id}'

            # Get machine options and create choice variables
            machine_options = task_data[17]
            machine_choice = {m: model.NewBoolVar(f'{suffix}_machine_{m}') for m in machine_options}
            model.AddExactlyOne(list(machine_choice.values()))

            # Setup phase - use the setup time directly from new_jobs.csv
            setup_time = task_data[3]  # This is the Setup column from new_jobs.csv
            setup_start = model.NewIntVar(0, horizon, f'{suffix}_setup_start')
            setup_duration = model.NewIntVar(setup_time, setup_time, f'{suffix}_setup_duration')
            setup_end = model.NewIntVar(0, horizon, f'{suffix}_setup_end')
            model.Add(setup_end == setup_start + setup_duration)

            setup_intervals = []
            tool_id = task_data[16]

            for m in machine_options:
                is_present = model.NewBoolVar(f'{suffix}_m{m}_setup_present')
                model.Add(is_present == machine_choice[m])
                interval = model.NewOptionalIntervalVar(
                    setup_start, setup_duration, setup_end,
                    is_present, f'{suffix}_m{m}_setup'
                )
                setup_intervals.append(interval)
                machine_to_intervals[m].append(interval)

                if tool_id in max_tools:
                    tool_intervals[tool_id].append(interval)

            # Process phases for chunked or non-chunked tasks
            if is_chunk_eligible(task_data):
                print(f"Task {job_id},{task_id} is chunk-eligible with min_split_task={task_data[11]}")
                proc_data = setup_chunked_processing(
                    model, suffix, task_data, horizon, setup_end, machine_options,
                    machine_choice, downtime_windows, machine_to_intervals, tool_intervals,
                    tool_id, max_tools, job_id, task_id
                )
            else:
                proc_data = setup_non_chunked_processing(
                    model, suffix, task_data[1], horizon, setup_end, machine_options,
                    machine_choice, machine_to_intervals, tool_intervals, tool_id,
                    max_tools, downtime_windows
                )

            # Dwell phase
            dwell_start, dwell_end, dwell_intervals = setup_dwell_phase(
                model, suffix, task_data[6], proc_data['proc_ends'],
                machine_options, machine_choice, machine_to_intervals,
                tool_intervals, tool_id, horizon, max_tools
            )

            # Determine task end
            task_end = model.NewIntVar(0, horizon, f'end_{suffix}')
            if task_data[6] > 0:  # If dwell exists
                model.Add(task_end == dwell_end)
            else:
                model.AddMaxEquality(task_end, [proc_data['proc_ends']])

            # Create task dictionary
            task_dict = {
                'task_end': task_end,
                'machine': task_data[0],
                'setup_start': setup_start,
                'setup_end': setup_end,
                'setup_scrap': 0,  # No scrap when using static setup times
                'proc_starts_all': proc_data['proc_starts_all'],
                'proc_ends_all': proc_data['proc_ends_all'],
                'proc_sub_intervals': proc_data['proc_sub_intervals'],
                'slack': task_data[2],
                'dwell': task_data[6],
                'priority': task_data[5],
                'customer_weight': task_data[14],
                'is_rush': task_data[15],
                'tool_id': tool_id,
                'machine_choice': machine_choice,
                'setup_intervals': setup_intervals,
                'durations': proc_data['durations'],
                'straddling_reward': proc_data['straddling_reward'],
                'chunk_eligible': is_chunk_eligible(task_data),
                'state_id': task_data[18] if len(task_data) > 18 else 0
            }

            if task_dict['chunk_eligible']:
                task_dict['should_chunk'] = proc_data['should_chunk']

            if task_data[6] > 0:  # If dwell exists
                task_dict['dwell_start'] = dwell_start
                task_dict['dwell_end'] = dwell_end
                task_dict['dwell_intervals'] = dwell_intervals

            # Record if this is a MustDo task
            if task_data[13] is not None and task_id == len(job) - 1:
                job_must_do = task_data[13]

            # Add constraints for this task
            add_task_constraints(model, task_dict, task_data, job_id, task_id, job,
                                 all_tasks, horizon, use_penalties, job_must_do, suffix)

            # Store task in all_tasks dictionary
            all_tasks[(job_id, task_id)] = task_dict

    return all_tasks


def print_solution(solver, model, all_tasks, jobs_data, job_groups, downtime_windows,
                   machine_to_intervals, unavailable_intervals, horizon, use_penalties,
                   total_cost_vars, machine_cost_per_unit, setup_cost, weight_tardiness,
                   must_do_penalty, rush_penalty_multiplier, precision_factor, max_tools,
                   solve_time, makespan, machine_map, setup_scrap_cost_per_unit=0, solution_index=1):
    """
    Modified print_solution function that includes setup scrap information, machine names,
    and solution tracking with consistent CSV format.

    Each run of the solver will start with a truncated gantt_data file, and each viable
    solution during the optimization process will be appended with an incremented index.

    This function can handle both regular solver objects and SolutionCallback objects.
    """
    # Determine if solver is a regular solver or a callback
    is_callback = isinstance(solver, cp_model.CpSolverSolutionCallback)

    # For callbacks, we always proceed (they're only called when solutions are found)
    # For regular solvers, we check the status
    if is_callback or solver.StatusName() in ("OPTIMAL", "FEASIBLE"):
        # Define helper functions to get values from different solver types
        def get_value(var):
            return solver.Value(var) if not is_callback else solver.Value(var)

        def get_bool_value(var):
            return solver.BooleanValue(var) if not is_callback else solver.BooleanValue(var)

        # Create a reverse mapping from indices to machine names
        machine_index_to_name = {idx: name for name, idx in machine_map.items()}

        total_straddling_reward_value = get_value(total_cost_vars['total_straddling_reward'])
        setup_scrap_cost_value = get_value(total_cost_vars.get('setup_scrap_cost', 0))

        if use_penalties and any(job[-1][13] is not None for job in jobs_data):
            total_cost_value = (
                    get_value(total_cost_vars['total_production_cost']) +
                    get_value(total_cost_vars['total_setup_cost']) +
                    setup_scrap_cost_value +
                    get_value(total_cost_vars['total_tardiness']) * weight_tardiness +
                    get_value(total_cost_vars.get('total_must_do_tardiness', 0)) * must_do_penalty -
                    (5 * total_straddling_reward_value)
            )
            print(f'Makespan: {get_value(makespan)}')
            print(f'Total Cost: {total_cost_value}')
            print(f'Total Setup Cost: {get_value(total_cost_vars["total_setup_cost"])}')
            print(f'Total Setup Scrap Cost: {setup_scrap_cost_value}')
            print(f'Total Production Cost: {get_value(total_cost_vars["total_production_cost"])}')
            print(f'Total Tardiness (Weighted, scaled): {get_value(total_cost_vars["total_tardiness"])}')
            print(
                f'Total Must-Do Tardiness (Weighted, scaled): {get_value(total_cost_vars.get("total_must_do_tardiness", 0))}')
            print(f'Total Straddling Reward: {total_straddling_reward_value}')
        else:
            total_cost_value = (
                    get_value(total_cost_vars['total_production_cost']) +
                    get_value(total_cost_vars['total_setup_cost']) +
                    setup_scrap_cost_value +
                    get_value(total_cost_vars['total_tardiness']) * weight_tardiness -
                    (5 * total_straddling_reward_value)
            )
            print(f'Makespan: {get_value(makespan)}')
            print(f'Total Cost: {total_cost_value}')
            print(f'Total Setup Cost: {get_value(total_cost_vars["total_setup_cost"])}')
            print(f'Total Setup Scrap Cost: {setup_scrap_cost_value}')
            print(f'Total Production Cost: {get_value(total_cost_vars["total_production_cost"])}')
            print(f'Total Tardiness (Weighted, scaled): {get_value(total_cost_vars["total_tardiness"])}')
            print(f'Total Straddling Reward: {total_straddling_reward_value}')

        print(f"\n=== SOLUTION DETAILS (Solution Index: {solution_index}) ===")
        for job_id, job in enumerate(jobs_data):
            job_num = list(job_groups.groups.keys())[job_id]
            for task_id, task_data in enumerate(job):
                task = all_tasks[(job_id, task_id)]
                chosen_machine = next(
                    m for m in task['machine_choice'] if get_bool_value(task['machine_choice'][m]))
                machine_name = machine_index_to_name.get(chosen_machine, f"Machine-{chosen_machine}")

                setup_start_val = get_value(task['setup_start'])
                setup_end_val = get_value(task['setup_end'])
                proc_starts_vals = [get_value(s) for s in task['proc_starts_all']]
                proc_ends_vals = [get_value(e) for e in task['proc_ends_all']]
                tard = get_value(task['tardiness'])

                print(f"\nJob {job_num}, Task {task_id} on Machine {chosen_machine} ({machine_name}):")
                if 'state_id' in task:
                    print(f"  State ID: {task['state_id']}")
                print(
                    f"  Setup Start = {setup_start_val}, Setup End = {setup_end_val}, Setup Scrap = {task.get('setup_scrap', 0)}")

                if task.get('chunk_eligible', False):
                    chunk_decision = get_bool_value(task['should_chunk'])
                    print(f"  >> CHUNK-ELIGIBLE TASK <<")
                    print(f"  Chunking Decision: {'CHUNKED' if chunk_decision else 'NOT CHUNKED'}")
                    if chunk_decision:
                        print(f"  Number of chunks: 2")
                        print(
                            f"  Chunk 1: Start = {proc_starts_vals[0]}, End = {proc_ends_vals[0]}, Duration = {proc_ends_vals[0] - proc_starts_vals[0]}")
                        print(
                            f"  Chunk 2: Start = {proc_starts_vals[1]}, End = {proc_ends_vals[1]}, Duration = {proc_ends_vals[1] - proc_starts_vals[1]}")
                        gap_size = proc_starts_vals[1] - proc_ends_vals[0]
                        print(f"  -> Gap between chunks: {gap_size} time units")
                        is_straddling = False
                        for dt_start, dt_end in downtime_windows.get(chosen_machine, []):
                            if (proc_ends_vals[0] == dt_start and proc_starts_vals[1] == dt_end):
                                print(f"  -> SUCCESSFULLY STRADDLING DOWNTIME: {dt_start}-{dt_end}")
                                is_straddling = True
                                break
                        if not is_straddling:
                            print("  -> NOT STRADDLING ANY DOWNTIME")
                        if setup_end_val != proc_starts_vals[0]:
                            print(
                                f"  -> ISSUE: Gap between setup and processing: {proc_starts_vals[0] - setup_end_val}")
                        else:
                            print(f"  -> CORRECT: Setup and first processing chunk are contiguous")
                    else:
                        print(
                            f"  Proc Start = {proc_starts_vals[2]}, Proc End = {proc_ends_vals[2]}, Duration = {proc_ends_vals[2] - proc_starts_vals[2]}")
                        if setup_end_val != proc_starts_vals[2]:
                            print(
                                f"  -> ISSUE: Gap between setup and processing: {proc_starts_vals[2] - setup_end_val}")
                        else:
                            print(f"  -> CORRECT: Setup and processing are contiguous")
                else:
                    print(
                        f"  Proc Start = {proc_starts_vals[0]}, Proc End = {proc_ends_vals[0]}, Duration = {proc_ends_vals[0] - proc_starts_vals[0]}")
                    if setup_end_val != proc_starts_vals[0]:
                        print(f"  -> ISSUE: Gap between setup and processing: {proc_starts_vals[0] - setup_end_val}")
                    else:
                        print(f"  -> CORRECT: Setup and processing are contiguous")

                if 'dwell_start' in task:
                    dwell_start_val = get_value(task['dwell_start'])
                    dwell_end_val = get_value(task['dwell_end'])
                    print(f"  Dwell Start = {dwell_start_val}, Dwell End = {dwell_end_val}")

                print(f"  Task End = {get_value(task['task_end'])}, Tardiness = {tard}")

        gantt_data = []
        makespan_value = get_value(makespan)

        for job_id, job in enumerate(jobs_data):
            job_num = list(job_groups.groups.keys())[job_id]
            for task_id, _ in enumerate(job):
                task = all_tasks[(job_id, task_id)]
                chosen_machine = next(
                    m for m in task['machine_choice'] if get_bool_value(task['machine_choice'][m]))
                machine_name = machine_index_to_name.get(chosen_machine, f"Machine-{chosen_machine}")

                if task['durations'][0] > 0:
                    st = get_value(task['setup_start'])
                    en = get_value(task['setup_end'])
                    gantt_data.append({
                        'Machine': chosen_machine,
                        'MachineName': machine_name,
                        'Task': f"{job_num} T{task_id}",
                        'Start': st,
                        'End': en,
                        'Duration': en - st,
                        'Phase': 'Setup'
                    })

                if task.get('chunk_eligible', False) and get_bool_value(task['should_chunk']):
                    proc_starts = task['proc_starts_all'][:2]
                    proc_ends = task['proc_ends_all'][:2]
                    for s, e in zip(proc_starts, proc_ends):
                        start_val = get_value(s)
                        end_val = get_value(e)
                        dur = end_val - start_val
                        if dur > 0:
                            gantt_data.append({
                                'Machine': chosen_machine,
                                'MachineName': machine_name,
                                'Task': f"{job_num} T{task_id}",
                                'Start': start_val,
                                'End': end_val,
                                'Duration': dur,
                                'Phase': 'Proc'
                            })
                else:
                    s = task['proc_starts_all'][2 if task.get('chunk_eligible', False) else 0]
                    e = task['proc_ends_all'][2 if task.get('chunk_eligible', False) else 0]
                    start_val = get_value(s)
                    end_val = get_value(e)
                    dur = end_val - start_val
                    if dur > 0:
                        gantt_data.append({
                            'Machine': chosen_machine,
                            'MachineName': machine_name,
                            'Task': f"{job_num} T{task_id}",
                            'Start': start_val,
                            'End': end_val,
                            'Duration': dur,
                            'Phase': 'Proc'
                        })

                dwell = job[task_id][6]
                if dwell > 0 and 'dwell_start' in task and 'dwell_end' in task:
                    dwell_start_val = get_value(task['dwell_start'])
                    dwell_end_val = get_value(task['dwell_end'])
                    gantt_data.append({
                        'Machine': chosen_machine,
                        'MachineName': machine_name,
                        'Task': f"{job_num} T{task_id}",
                        'Start': dwell_start_val,
                        'End': dwell_end_val,
                        'Duration': dwell_end_val - dwell_start_val,
                        'Phase': 'Dwell'
                    })

        for machine_idx in range(len(unavailable_intervals)):
            machine_name = machine_index_to_name.get(machine_idx, f"Machine-{machine_idx}")
            for interval in unavailable_intervals[machine_idx]:
                start_val = get_value(interval.StartExpr())
                end_val = get_value(interval.EndExpr())
                gantt_data.append({
                    'Machine': machine_idx,
                    'MachineName': machine_name,
                    'Task': 'Downtime',
                    'Start': start_val,
                    'End': end_val,
                    'Duration': end_val - start_val,
                    'Phase': 'Unavailable'
                })

        # Add solution tracking information to current solution
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for entry in gantt_data:
            entry['SolutionIndex'] = solution_index
            entry['Timestamp'] = timestamp
            entry['Makespan'] = makespan_value
            entry['TotalCost'] = total_cost_value

        # Create DataFrame from current solution
        gantt_df = pd.DataFrame(gantt_data)

        # Determine mode for writing to CSV (append if solution_index > 1, otherwise create new)
        if solution_index > 1:
            # Append mode
            try:
                gantt_df.to_csv('gantt_data.csv', mode='a', header=False, index=False)
                print(f"\nSolution {solution_index} appended to gantt_data.csv")
            except Exception as e:
                print(f"Error appending to gantt_data.csv: {e}")
                gantt_df.to_csv(f'gantt_data_solution_{solution_index}.csv', index=False)
                print(f"Saved to alternate file: gantt_data_solution_{solution_index}.csv")
        else:
            # Create/overwrite mode for first solution
            try:
                gantt_df.to_csv('gantt_data.csv', index=False)
                print(f"\nSolution {solution_index} saved to gantt_data.csv (first solution)")
            except Exception as e:
                print(f"Error writing to gantt_data.csv: {e}")
                gantt_df.to_csv(f'gantt_data_solution_{solution_index}.csv', index=False)
                print(f"Saved to alternate file: gantt_data_solution_{solution_index}.csv")

        if not is_callback:  # Only print this for the final solution, not callbacks
            print(f"Optimization Time: {solve_time:.2f} seconds")
    else:
        print("No solution found.")
        print(f"Solver Status: {solver.StatusName()}")
        print(f"Optimization Time: {solve_time:.2f} seconds")


def print_configuration_values(config, used_values):
    """
    Print all configuration values and the actual values used in the solver.
    This helps verify which values are coming from config vs. hardcoded defaults.

    Args:
        config: The loaded configuration dictionary
        used_values: Dictionary of values actually used in the solver
    """
    print("\n=====================================================")
    print("CONFIGURATION VERIFICATION")
    print("=====================================================")

    print("\nSOLVER PARAMETERS:")
    print(f"  max_time_in_seconds: {used_values['max_time_in_seconds']} (Config: {config['solver_parameters'].get('max_time_in_seconds', 'Not set')})")
    print(f"  use_penalties: {used_values['use_penalties']} (Config: {config['solver_parameters'].get('use_penalties', 'Not set')})")

    print("\nCOST PARAMETERS:")
    print(f"  setup_cost: {used_values['setup_cost']} (Config: {config['cost_parameters'].get('setup_cost', 'Not set')})")
    print(f"  weight_tardiness: {used_values['weight_tardiness']} (Config: {config['cost_parameters'].get('weight_tardiness', 'Not set')})")
    print(f"  must_do_penalty: {used_values['must_do_penalty']} (Config: {config['cost_parameters'].get('must_do_penalty', 'Not set')})")
    print(f"  rush_penalty_multiplier: {used_values['rush_penalty_multiplier']} (Config: {config['cost_parameters'].get('rush_penalty_multiplier', 'Not set')})")
    print(f"  precision_factor: {used_values['precision_factor']} (Config: {config['cost_parameters'].get('precision_factor', 'Not set')})")
    print(f"  setup_scrap_cost_per_unit: {used_values['setup_scrap_cost_per_unit']} (Config: {config['cost_parameters'].get('setup_scrap_cost_per_unit', 'Not set')})")

    print("\nMACHINE PARAMETERS:")
    print(f"  machines_count: {used_values['machines_count']} (Config: {config['machine_parameters'].get('machines_count', 'Not set')})")
    print("  machine_cost_per_unit: (showing actual values used)")
    for m, cost in sorted(used_values['machine_cost_per_unit'].items()):
        config_cost = config['machine_parameters']['machine_cost_per_unit'].get(m, 'Not set')
        print(f"    Machine {m}: {cost} (Config: {config_cost})")

    print("\nTOOL PARAMETERS:")
    print("  max_tools: (showing actual values used)")
    for tool_id, max_count in sorted(used_values['max_tools'].items()):
        config_max = config['tool_parameters']['max_tools'].get(tool_id, 'Not set')
        print(f"    Tool {tool_id}: {max_count} (Config: {config_max})")

    print("\nFEATURE FLAGS:")
    print(f"  use_seq_dependent_setup: {used_values['use_seq_dependent_setup']} (Config: {config['feature_flags'].get('use_seq_dependent_setup', 'Not set')})")
    print(f"  use_workcenters: {used_values['use_workcenters']} (Config: {config['feature_flags'].get('use_workcenters', 'Not set')})")

    print("\n=====================================================")
    print("NOTE: 'Not set' means the value isn't specified in config and the default was used")
    print("=====================================================\n")

def validate_solution_intervals(solver, all_tasks, machines, machine_map=None):
    """Check the solution for any interval overlaps."""
    print("\n=== INTERVAL OVERLAP VALIDATION ===")
    overlaps = []

    # Create reverse machine map for better reporting
    machine_names = {}
    if machine_map:
        machine_names = {idx: name for name, idx in machine_map.items()}

    # Group task intervals by machine
    machine_intervals = {m: [] for m in machines}

    for (job_id, task_id), task in all_tasks.items():
        # Get chosen machine
        chosen_machine = None
        for m in task['machine_choice']:
            if solver.BooleanValue(task['machine_choice'][m]):
                chosen_machine = m
                break

        if chosen_machine is None:
            continue

        # Add setup interval
        setup_start = solver.Value(task['setup_start'])
        setup_end = solver.Value(task['setup_end'])
        machine_intervals[chosen_machine].append({
            'job_id': job_id,
            'task_id': task_id,
            'type': 'Setup',
            'start': setup_start,
            'end': setup_end
        })

        # Add processing interval(s)
        if task.get('chunk_eligible', False) and solver.BooleanValue(task.get('should_chunk', False)):
            # Both chunks
            proc_start1 = solver.Value(task['proc_starts_all'][0])
            proc_end1 = solver.Value(task['proc_ends_all'][0])
            proc_start2 = solver.Value(task['proc_starts_all'][1])
            proc_end2 = solver.Value(task['proc_ends_all'][1])

            machine_intervals[chosen_machine].append({
                'job_id': job_id,
                'task_id': task_id,
                'type': 'Proc1',
                'start': proc_start1,
                'end': proc_end1
            })

            machine_intervals[chosen_machine].append({
                'job_id': job_id,
                'task_id': task_id,
                'type': 'Proc2',
                'start': proc_start2,
                'end': proc_end2
            })
        else:
            # Non-chunked
            idx = 2 if task.get('chunk_eligible', False) else 0
            proc_start = solver.Value(task['proc_starts_all'][idx])
            proc_end = solver.Value(task['proc_ends_all'][idx])

            machine_intervals[chosen_machine].append({
                'job_id': job_id,
                'task_id': task_id,
                'type': 'Proc',
                'start': proc_start,
                'end': proc_end
            })

    # Check for overlaps on each machine
    for m, intervals in machine_intervals.items():
        # Sort intervals by start time
        intervals.sort(key=lambda x: x['start'])

        # Check for overlaps
        for i in range(len(intervals) - 1):
            curr = intervals[i]
            next_int = intervals[i + 1]

            if curr['end'] > next_int['start']:
                machine_name = machine_names.get(m, f"Machine-{m}")
                overlaps.append({
                    'machine': m,
                    'machine_name': machine_name,
                    'interval1': curr,
                    'interval2': next_int,
                    'overlap': min(curr['end'], next_int['end']) - next_int['start']
                })

    # Report overlaps
    if overlaps:
        print(f"Found {len(overlaps)} overlapping intervals:")
        for o in overlaps:
            int1 = o['interval1']
            int2 = o['interval2']
            print(f"Machine {o['machine']} ({o['machine_name']}):")
            print(f"  Job {int1['job_id']}, Task {int1['task_id']} ({int1['type']}): {int1['start']}-{int1['end']}")
            print(f"  Job {int2['job_id']}, Task {int2['task_id']} ({int2['type']}): {int2['start']}-{int2['end']}")
            print(f"  Overlap: {o['overlap']} time units")
    else:
        print("No overlaps found. Schedule is valid.")

    print("=== END OF VALIDATION ===\n")
    return overlaps

# Main procedure
def main():
    """
    Main function that orchestrates the scheduling optimization process.
    Includes enhanced debugging for machine assignments and solution tracking.
    The solver will record each valid solution found during optimization.
    """

    # Define a solution callback class to capture multiple solutions
    class SolutionCallback(cp_model.CpSolverSolutionCallback):
        """Callback to log intermediate solutions during the solving process."""

        def __init__(self, model, all_tasks, jobs_data, job_groups, downtime_windows,
                     machine_to_intervals, unavailable_intervals, horizon, use_penalties,
                     total_cost_vars, machine_cost_per_unit, setup_cost, weight_tardiness,
                     must_do_penalty, rush_penalty_multiplier, precision_factor, max_tools,
                     makespan, machine_map, setup_scrap_cost_per_unit):
            cp_model.CpSolverSolutionCallback.__init__(self)
            self.model = model
            self.all_tasks = all_tasks
            self.jobs_data = jobs_data
            self.job_groups = job_groups
            self.downtime_windows = downtime_windows
            self.machine_to_intervals = machine_to_intervals
            self.unavailable_intervals = unavailable_intervals
            self.horizon = horizon
            self.use_penalties = use_penalties
            self.total_cost_vars = total_cost_vars
            self.machine_cost_per_unit = machine_cost_per_unit
            self.setup_cost = setup_cost
            self.weight_tardiness = weight_tardiness
            self.must_do_penalty = must_do_penalty
            self.rush_penalty_multiplier = rush_penalty_multiplier
            self.precision_factor = precision_factor
            self.max_tools = max_tools
            self.makespan = makespan
            self.machine_map = machine_map
            self.setup_scrap_cost_per_unit = setup_scrap_cost_per_unit
            self.solution_count = 0
            self.last_objective_value = float('inf')
            self.min_improvement_pct = 0.05  # Only log solutions that improve by at least 5%

        def on_solution_callback(self):
            """Called when the solver finds a new solution."""
            current_objective = self.ObjectiveValue()

            # Calculate improvement over previous solution
            improvement = 0
            if self.last_objective_value != float('inf'):
                improvement = (self.last_objective_value - current_objective) / self.last_objective_value

            # Only log solutions with significant improvement (or the first solution)
            if self.solution_count == 0 or improvement >= self.min_improvement_pct:
                self.solution_count += 1
                print(f"\n>>> Solution {self.solution_count} found (objective = {current_objective}) <<<")
                if self.solution_count > 1:
                    print(f">>> Improvement: {improvement:.2%} over previous best <<<")

                # Log the solution
                solve_time = 0  # We don't have the exact time for intermediate solutions
                print_solution(
                    self, self.model, self.all_tasks, self.jobs_data, self.job_groups, self.downtime_windows,
                    self.machine_to_intervals, self.unavailable_intervals, self.horizon, self.use_penalties,
                    self.total_cost_vars, self.machine_cost_per_unit, self.setup_cost, self.weight_tardiness,
                    self.must_do_penalty, self.rush_penalty_multiplier, self.precision_factor, self.max_tools,
                    solve_time, self.makespan, self.machine_map, self.setup_scrap_cost_per_unit, self.solution_count
                )

                # Update last objective value
                self.last_objective_value = current_objective
            else:
                print(
                    f"Found solution with objective {current_objective} (improvement: {improvement:.2%}) - not logging")

    # Start of main function logic
    # Delete existing gantt_data.csv at the beginning of each run
    if os.path.exists('gantt_data.csv'):
        try:
            os.remove('gantt_data.csv')
            print("Deleted existing gantt_data.csv to start fresh")
        except Exception as e:
            print(f"Warning: Could not delete existing gantt_data.csv: {e}")

    # Load configuration
    config = load_config()

    # Extract configuration values
    use_seq_dependent_setup = config["feature_flags"].get("use_seq_dependent_setup", True)
    use_workcenters = config["feature_flags"].get("use_workcenters", False)
    use_penalties = config["solver_parameters"].get("use_penalties", True)
    machine_cost_per_unit = config["machine_parameters"].get("machine_cost_per_unit",
                                                             {0: 5, 1: 3, 2: 3, 3: 4, 4: 2, 5: 6, 6: 3, 7: 4, 8: 5,
                                                              9: 2})
    setup_cost = config["cost_parameters"].get("setup_cost", 10)
    weight_tardiness = config["cost_parameters"].get("weight_tardiness", 5.0)
    must_do_penalty = config["cost_parameters"].get("must_do_penalty", 10.0)
    rush_penalty_multiplier = config["cost_parameters"].get("rush_penalty_multiplier", 10)
    precision_factor = config["cost_parameters"].get("precision_factor", 10)
    max_tools = config["tool_parameters"].get("max_tools", {0: 1, 1: 4, 2: 2})
    setup_scrap_cost_per_unit = config["cost_parameters"].get("setup_scrap_cost_per_unit", 5)
    solver_time_limit = config["solver_parameters"].get("max_time_in_seconds", 1800.0)

    # Build machine map
    machine_map = {
        "F00B/D000E": 0, "F00B/D202F": 1, "F00B/D202J": 2, "F00B/D202Z": 3, "F00B/D205Z": 4,
        "F00B/D2062": 5, "F00B/D3001": 6, "F00B/D3002": 7, "F00B/D3007": 8, "F00B/D3014": 9,
        "F00B/DD005": 10
    }
    machines_count = max(machine_map.values()) + 1
    print("Machine mapping:")
    for k, v in machine_map.items():
        print(f"  {k} -> {v} (cost: {machine_cost_per_unit.get(v, 4)})")

    # Load data
    fixed_df, new_df, capacity_df = load_data()

    # Debug data before preprocessing
    print("\nBefore preprocessing:")
    sample_jobs = new_df['JobNumber'].unique()[:3]  # First 3 unique jobs
    for job in sample_jobs:
        job_tasks = new_df[new_df['JobNumber'] == job].sort_values('TaskID')
        print(f"\nJob {job} tasks:")
        for _, task in job_tasks.iterrows():
            print(f"  Task {task['TaskID']}: Machine = {task['MachineOptions']}")

    # Preprocess data
    preprocess_data(fixed_df, new_df, capacity_df, machine_map)

    # Debug data after preprocessing
    print("\nAfter preprocessing:")
    for job in sample_jobs:
        job_tasks = new_df[new_df['JobNumber'] == job].sort_values('TaskID')
        print(f"\nJob {job} tasks:")
        for _, task in job_tasks.iterrows():
            print(f"  Task {task['TaskID']}: Machine = {task['MachineOptions']}")

    # Load workcenters if feature is enabled
    workcenters = {}
    machine_to_workcenter = {}
    if use_workcenters:
        workcenters = load_workcenters(machine_map)
        if workcenters:
            machine_to_workcenter = build_machine_to_workcenter_map(workcenters, machines_count)
            print(f"Loaded {len(workcenters)} workcenters")
        else:
            use_workcenters = False
            print("No workcenters found. Disabling workcenter feature.")

    # Load sequence-dependent setup transition matrices if feature is enabled
    setup_time_matrix, setup_scrap_matrix, max_state_id = None, None, 0
    if use_seq_dependent_setup:
        try:
            setup_time_matrix, setup_scrap_matrix, max_state_id = load_transition_matrices()
        except Exception as e:
            print(f"Error loading transition matrices: {e}")
            print("Disabling sequence-dependent setup.")
            use_seq_dependent_setup = False

    # Build fixed jobs
    fixed_jobs = build_fixed_jobs(fixed_df)
    if fixed_jobs:
        print(f"Fixed jobs: {len(fixed_jobs)}")
    else:
        print("Fixed jobs DataFrame is empty. No fixed jobs to process.")

    # Build jobs data
    jobs_data, job_groups = build_jobs_data(new_df)

    # Debug jobs_data structure
    print("\nJobs data check:")
    for job_id, job in enumerate(jobs_data[:2]):  # Check first 2 jobs
        job_name = list(job_groups.groups.keys())[job_id]
        print(f"\nJob {job_name} tasks:")
        for task_id, task in enumerate(job[:2]):  # Check first 2 tasks
            print(f"  Task {task_id}:")
            print(f"    Default machine: {task[0]}")
            print(f"    Machine options: {task[17]}")

    # Compute downtime and horizon
    downtime_windows, horizon = compute_downtime_and_horizon(capacity_df, new_df, machines_count)

    # Create model
    model = cp_model.CpModel()
    print("Model validation (initial):", model.Validate())

    # Initialize intervals collections
    machine_to_intervals = {m: [] for m in machine_map.values()}
    tool_intervals = {tool_id: [] for tool_id in max_tools.keys()}
    fixed_machine_intervals = {m: [] for m in range(machines_count)}
    fixed_tool_intervals = {tool_id: [] for tool_id in max_tools.keys()}
    unavailable_intervals = {m: [] for m in range(machines_count)}

    # Build intervals and constraints
    build_fixed_intervals(model, fixed_jobs, fixed_machine_intervals, fixed_tool_intervals)
    build_unavailability_intervals(model, capacity_df, unavailable_intervals, downtime_windows, machines_count)

    # Build tasks with or without sequence-dependent setup
    print("\nBuilding tasks:")
    if use_seq_dependent_setup:
        all_tasks, total_setup_scrap = build_tasks(
            model, jobs_data, job_groups, downtime_windows, machine_to_intervals, tool_intervals,
            horizon, use_penalties, max_tools, setup_time_matrix, setup_scrap_matrix, use_seq_dependent_setup
        )
    else:
        # Fallback to original build_tasks if sequence-dependent setup is disabled
        all_tasks, total_setup_scrap = build_tasks(
            model, jobs_data, job_groups, downtime_windows, machine_to_intervals, tool_intervals,
            horizon, use_penalties, max_tools
        )

    print("Model validation (after variable creation):", model.Validate())

    # Add constraints
    print("\nAdding capacity constraints:")
    add_no_overlap_constraints(model, fixed_machine_intervals, machine_to_intervals, unavailable_intervals,
                               machines_count)
    add_downtime_constraints(model, all_tasks, downtime_windows, machine_to_intervals)

    # Test feasibility without workcenter constraints first
    if use_workcenters and workcenters:
        # Create a copy of the model for testing
        base_model = cp_model.CpModel()
        base_model.Proto().CopyFrom(model.Proto())

        # Add regular capacity constraints for testing
        add_capacity_window_constraints(base_model, all_tasks, downtime_windows, machine_to_intervals)

        print("Testing feasibility without workcenter constraints...")
        base_solver = cp_model.CpSolver()
        base_solver.parameters.max_time_in_seconds = 60.0  # Limited test time
        base_status = base_solver.Solve(base_model)

        if base_solver.StatusName() not in ("OPTIMAL", "FEASIBLE"):
            print("WARNING: Base model is already infeasible without workcenter constraints!")
            print("Disabling workcenters to help diagnose the core issue.")
            use_workcenters = False
        else:
            print(f"Base model is feasible ({base_solver.StatusName()}). Adding workcenter constraints...")
            # Apply hybrid constraints to the real model
            add_hybrid_capacity_constraints(model, all_tasks, downtime_windows, machine_to_intervals,
                                            workcenters, machine_to_workcenter, horizon)

    # If workcenters are disabled or the test failed, use regular capacity constraints
    if not use_workcenters or not workcenters:
        print("Using regular capacity constraints (no workcenters)")
        add_capacity_window_constraints(model, all_tasks, downtime_windows, machine_to_intervals)

    # Apply tool capacity constraints
    add_tool_capacity_constraints(model, fixed_tool_intervals, tool_intervals, max_tools)

    # Define objectives with setup scrap
    makespan, total_cost_vars = define_objectives(
        model, all_tasks, jobs_data, horizon, machine_cost_per_unit,
        setup_cost, weight_tardiness, must_do_penalty, use_penalties,
        rush_penalty_multiplier, precision_factor, downtime_windows,
        machine_to_intervals, max_tools, total_setup_scrap, setup_scrap_cost_per_unit
    )

    print("Model validation (final):", model.Validate())

    # Setup callback for multi-solution tracking
    solution_callback = SolutionCallback(
        model, all_tasks, jobs_data, job_groups, downtime_windows,
        machine_to_intervals, unavailable_intervals, horizon, use_penalties,
        total_cost_vars, machine_cost_per_unit, setup_cost, weight_tardiness,
        must_do_penalty, rush_penalty_multiplier, precision_factor, max_tools,
        makespan, machine_map, setup_scrap_cost_per_unit
    )

    # Solve model with callback to track multiple solutions
    print(f"Starting solver with {solver_time_limit} seconds time limit, tracking multiple solutions...")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solver_time_limit
    solver.parameters.enumerate_all_solutions = False  # We don't need all solutions, just improving ones
    solver.parameters.log_search_progress = True  # Show search progress

    # Set a relative gap to control solution quality
    solver.parameters.relative_gap_limit = 0.10  # 10% gap is acceptable

    start_time = time.time()
    status = solver.Solve(model, solution_callback)
    end_time = time.time()
    solve_time = end_time - start_time

    print(f"\nSolver finished. Status: {solver.StatusName()}")
    print(f"Found {solution_callback.solution_count} solutions with significant improvements")
    if solution_callback.solution_count > 0:
        print(f"Final objective value: {solution_callback.last_objective_value}")
    print(f"Total optimization time: {solve_time:.2f} seconds")

    # Print information about workcenter usage in the solution if enabled
    if use_workcenters and workcenters and solution_callback.solution_count > 0:
        print_workcenter_usage(solver, all_tasks, workcenters, machine_to_workcenter)

    # Verify which configuration values were actually used
    used_values = {
        # Solver parameters
        'max_time_in_seconds': solver.parameters.max_time_in_seconds,
        'use_penalties': use_penalties,

        # Cost parameters
        'setup_cost': setup_cost,
        'weight_tardiness': weight_tardiness,
        'must_do_penalty': must_do_penalty,
        'rush_penalty_multiplier': rush_penalty_multiplier,
        'precision_factor': precision_factor,
        'setup_scrap_cost_per_unit': setup_scrap_cost_per_unit,

        # Machine parameters
        'machines_count': machines_count,
        'machine_cost_per_unit': machine_cost_per_unit,

        # Tool parameters
        'max_tools': max_tools,

        # Feature flags
        'use_seq_dependent_setup': use_seq_dependent_setup,
        'use_workcenters': use_workcenters
    }

    print_configuration_values(config, used_values)


if __name__ == '__main__':
    main()