import pandas as pd
import numpy as np
from ortools.sat.python import cp_model
import time


# Helper functions
def load_data():
    fixed_df = pd.read_csv("fixed_jobs.csv")
    new_df = pd.read_csv("new_jobs.csv")
    capacity_df = pd.read_csv("machine_capacity.csv")
    return fixed_df, new_df, capacity_df


def preprocess_data(fixed_df, new_df, capacity_df, machine_map):
    fixed_df['MachineIdx'] = fixed_df['Machine'].map(machine_map)
    new_df['MachineOptions'] = new_df['MachineOptions'].fillna("CNC-1")
    new_df['MachineOptions'] = new_df['MachineOptions'].apply(lambda x: [machine_map[m] for m in x.split(',')])
    capacity_df['MachineIdx'] = capacity_df['Machine'].map(machine_map)
    fixed_df.dropna(subset=['MachineIdx'], inplace=True)
    fixed_df['MachineIdx'] = fixed_df['MachineIdx'].astype(int)
    capacity_df.dropna(subset=['MachineIdx'], inplace=True)
    capacity_df['MachineIdx'] = capacity_df['MachineIdx'].astype(int)


def build_fixed_jobs(fixed_df):
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
            must_do = int(row['MustDo']) if 'MustDo' in row and not pd.isna(row['MustDo']) else None
            task_preempt = 1 if row['TaskPreempt'] == True or (
                        isinstance(row['TaskPreempt'], (int, float)) and row['TaskPreempt'] == 1) else 0
            min_split_task = int(row['MinSplitTask']) if 'MinSplitTask' in row and not pd.isna(
                row['MinSplitTask']) else 1
            task = (
                row['MachineOptions'][0],
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
                row['MachineOptions']
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
    # Use the task_preempt value from the CSV (index 9 in task tuple)
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


def build_tasks(model, jobs_data, job_groups, downtime_windows, machine_to_intervals, tool_intervals, horizon,
                use_penalties, max_tools):
    all_tasks = {}
    for job_id, job in enumerate(jobs_data):
        job_must_do = None
        for task_id, task_data in enumerate(job):
            suffix = f'_j{job_id}_t{task_id}'
            task_dict = initialize_task(model, task_data, suffix, machine_to_intervals, tool_intervals, horizon,
                                        max_tools, job_id, task_id, downtime_windows)  # Pass downtime_windows
            if task_data[13] is not None and task_id == len(job) - 1:
                job_must_do = task_data[13]
            add_task_constraints(model, task_dict, task_data, job_id, task_id, job, all_tasks, horizon,
                                 use_penalties, job_must_do, suffix)
            all_tasks[(job_id, task_id)] = task_dict
    return all_tasks


def initialize_task(model, task_data, suffix, machine_to_intervals, tool_intervals, horizon, max_tools, job_id, task_id,
                    downtime_windows):
    default_machine, proc_time, slack, setup, due, priority, dwell, release, job_preempt, task_preempt, min_split_job, min_split_task, release_threshold, must_do, customer_weight, is_rush, tool_id, machine_options = task_data

    machine_choice = {m: model.NewBoolVar(f'{suffix}_machine_{m}') for m in machine_options}
    model.AddExactlyOne(list(machine_choice.values()))

    setup_start, setup_end, setup_intervals = setup_phase(model, suffix, setup, machine_options, machine_choice,
                                                          machine_to_intervals, tool_intervals, tool_id, horizon,
                                                          max_tools)

    if is_chunk_eligible(task_data):
        print(f"Task {job_id},{task_id} is chunk-eligible with min_split_task={min_split_task}")
        proc_data = setup_chunked_processing(model, suffix, task_data, horizon, setup_end, machine_options,
                                             machine_choice, downtime_windows, machine_to_intervals, tool_intervals,
                                             tool_id, max_tools, job_id, task_id)
    else:
        # Make sure to pass downtime_windows to setup_non_chunked_processing
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
        'chunk_eligible': is_chunk_eligible(task_data)
    }
    if task_dict['chunk_eligible']:
        task_dict['should_chunk'] = proc_data['should_chunk']
    if dwell > 0:
        task_dict['dwell_start'] = dwell_start
        task_dict['dwell_end'] = dwell_end
        task_dict['dwell_intervals'] = dwell_intervals
    return task_dict


def setup_phase(model, suffix, setup, machine_options, machine_choice, machine_to_intervals, tool_intervals, tool_id,
                horizon, max_tools):
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
        if tool_id in max_tools:  # Now max_tools is in scope
            tool_intervals[tool_id].append(interval)
    return setup_start, setup_end, setup_intervals


def setup_chunked_processing(model, suffix, task_data, horizon, setup_end, machine_options, machine_choice,
                             downtime_windows, machine_to_intervals, tool_intervals, tool_id, max_tools, job_id,
                             task_id):
    """
    Enhanced approach for chunk-eligible tasks that uses MinSplitTask from the task data.
    No longer has special handling for the T3 case - all chunking is driven by data.
    """
    _, proc_time, _, setup, _, _, _, _, _, _, min_split_job, min_split_task, _, _, _, _, _, machine_options = task_data

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
    else:
        # If no downtime to straddle, no chunking
        model.Add(should_chunk == 0)
        can_straddle = model.NewConstant(0)

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
    Simplified approach for non-chunked tasks that forces processing to start
    immediately after setup unless it needs to be delayed for downtime.
    """
    proc_start = model.NewIntVar(0, horizon, f'{suffix}_proc_start')
    proc_duration = model.NewIntVar(proc_time, proc_time, f'{suffix}_proc_duration')
    proc_end = model.NewIntVar(0, horizon, f'{suffix}_proc_end')
    model.Add(proc_end == proc_start + proc_duration)

    # Always start by assuming processing starts exactly after setup
    delay_needed = model.NewBoolVar(f'{suffix}_delay_needed')
    model.Add(proc_start == setup_end).OnlyEnforceIf(delay_needed.Not())

    # For each machine, check if processing needs to be delayed due to downtime
    delay_vars = []

    for m in machine_options:
        if m in downtime_windows and downtime_windows[m]:
            for dt_idx, (dt_start, dt_end) in enumerate(downtime_windows[m]):
                # This machine is used and setup ends exactly at downtime start
                machine_dt_delay = model.NewBoolVar(f'{suffix}_m{m}_dt{dt_idx}_delay')
                model.Add(machine_choice[m] == 1).OnlyEnforceIf(machine_dt_delay)
                model.Add(setup_end == dt_start).OnlyEnforceIf(machine_dt_delay)
                delay_vars.append(machine_dt_delay)

                # If this specific delay is needed, proc starts after downtime
                model.Add(proc_start == dt_end).OnlyEnforceIf(machine_dt_delay)

    # If any delay is needed, set the global delay_needed variable
    if delay_vars:
        model.Add(sum(delay_vars) >= 1).OnlyEnforceIf(delay_needed)
        model.Add(sum(delay_vars) == 0).OnlyEnforceIf(delay_needed.Not())
    else:
        model.Add(delay_needed == 0)  # No delay possible if no downtime windows

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


def add_downtime_constraints(model, all_tasks, downtime_windows, machine_to_intervals):
    """
    Add explicit constraints to prevent any processing from starting or occurring
    during machine downtime windows.

    This is a critical final safety check to catch any cases the regular logic might miss.
    """
    for (job_id, task_id), task in all_tasks.items():
        for m in task['machine_choice']:
            if m in downtime_windows and downtime_windows[m]:
                for dt_start, dt_end in downtime_windows[m]:
                    # For regular processing or first chunk
                    if not task.get('chunk_eligible', False):
                        proc_start = task['proc_starts_all'][0]
                        proc_end = task['proc_ends_all'][0]
                        prevent_start_in_dt = model.NewBoolVar(f'prevent_start_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                        prevent_overlap_dt = model.NewBoolVar(f'prevent_overlap_j{job_id}_t{task_id}_m{m}_dt{dt_start}')

                        # Only apply these constraints if this machine is chosen
                        model.Add(task['machine_choice'][m] == 1).OnlyEnforceIf(prevent_start_in_dt)
                        model.Add(task['machine_choice'][m] == 1).OnlyEnforceIf(prevent_overlap_dt)

                        # Processing must not start during downtime
                        # Either starts before downtime or after downtime
                        start_before_dt = model.NewBoolVar(f'start_before_dt_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                        model.Add(proc_start < dt_start).OnlyEnforceIf(start_before_dt)
                        model.Add(proc_start >= dt_start).OnlyEnforceIf(start_before_dt.Not())

                        start_after_dt = model.NewBoolVar(f'start_after_dt_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                        model.Add(proc_start >= dt_end).OnlyEnforceIf(start_after_dt)
                        model.Add(proc_start < dt_end).OnlyEnforceIf(start_after_dt.Not())

                        model.AddBoolOr([start_before_dt, start_after_dt]).OnlyEnforceIf(prevent_start_in_dt)

                        # Processing must not overlap with downtime
                        # Either ends before downtime or starts after downtime
                        end_before_dt = model.NewBoolVar(f'end_before_dt_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                        model.Add(proc_end <= dt_start).OnlyEnforceIf(end_before_dt)
                        model.Add(proc_end > dt_start).OnlyEnforceIf(end_before_dt.Not())

                        model.AddBoolOr([end_before_dt, start_after_dt]).OnlyEnforceIf(prevent_overlap_dt)
                    else:
                        # For chunked tasks, need to check each chunk separately
                        if task.get('should_chunk', None) is not None:
                            # First chunk
                            proc_start1 = task['proc_starts_all'][0]
                            proc_end1 = task['proc_ends_all'][0]

                            prevent_overlap1_dt = model.NewBoolVar(
                                f'prevent_overlap1_j{job_id}_t{task_id}_m{m}_dt{dt_start}')

                            # If this machine is chosen and task is chunked
                            chunk_this_machine = model.NewBoolVar(f'chunk_j{job_id}_t{task_id}_m{m}')
                            model.AddBoolAnd([task['machine_choice'][m], task['should_chunk']]).OnlyEnforceIf(
                                chunk_this_machine)
                            model.Add(chunk_this_machine == 1).OnlyEnforceIf(prevent_overlap1_dt)

                            # First chunk must not overlap with downtime
                            end_before_dt1 = model.NewBoolVar(f'end_before_dt1_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                            model.Add(proc_end1 <= dt_start).OnlyEnforceIf(end_before_dt1)
                            model.Add(proc_end1 > dt_start).OnlyEnforceIf(end_before_dt1.Not())

                            start_after_dt1 = model.NewBoolVar(
                                f'start_after_dt1_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                            model.Add(proc_start1 >= dt_end).OnlyEnforceIf(start_after_dt1)
                            model.Add(proc_start1 < dt_end).OnlyEnforceIf(start_after_dt1.Not())

                            model.AddBoolOr([end_before_dt1, start_after_dt1]).OnlyEnforceIf(prevent_overlap1_dt)

                            # Second chunk
                            proc_start2 = task['proc_starts_all'][1]
                            proc_end2 = task['proc_ends_all'][1]

                            prevent_overlap2_dt = model.NewBoolVar(
                                f'prevent_overlap2_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                            model.Add(chunk_this_machine == 1).OnlyEnforceIf(prevent_overlap2_dt)

                            # Second chunk must not overlap with downtime
                            end_before_dt2 = model.NewBoolVar(f'end_before_dt2_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                            model.Add(proc_end2 <= dt_start).OnlyEnforceIf(end_before_dt2)
                            model.Add(proc_end2 > dt_start).OnlyEnforceIf(end_before_dt2.Not())

                            start_after_dt2 = model.NewBoolVar(
                                f'start_after_dt2_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                            model.Add(proc_start2 >= dt_end).OnlyEnforceIf(start_after_dt2)
                            model.Add(proc_start2 < dt_end).OnlyEnforceIf(start_after_dt2.Not())

                            model.AddBoolOr([end_before_dt2, start_after_dt2]).OnlyEnforceIf(prevent_overlap2_dt)

                            # Non-chunked case
                            proc_start_no_chunk = task['proc_starts_all'][2]
                            proc_end_no_chunk = task['proc_ends_all'][2]

                            prevent_overlap_no_chunk_dt = model.NewBoolVar(
                                f'prevent_overlap_no_chunk_j{job_id}_t{task_id}_m{m}_dt{dt_start}')

                            no_chunk_this_machine = model.NewBoolVar(f'no_chunk_j{job_id}_t{task_id}_m{m}')
                            model.AddBoolAnd([task['machine_choice'][m], task['should_chunk'].Not()]).OnlyEnforceIf(
                                no_chunk_this_machine)
                            model.Add(no_chunk_this_machine == 1).OnlyEnforceIf(prevent_overlap_no_chunk_dt)

                            # Non-chunked processing must not overlap with downtime
                            end_before_dt_no_chunk = model.NewBoolVar(
                                f'end_before_dt_no_chunk_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                            model.Add(proc_end_no_chunk <= dt_start).OnlyEnforceIf(end_before_dt_no_chunk)
                            model.Add(proc_end_no_chunk > dt_start).OnlyEnforceIf(end_before_dt_no_chunk.Not())

                            start_after_dt_no_chunk = model.NewBoolVar(
                                f'start_after_dt_no_chunk_j{job_id}_t{task_id}_m{m}_dt{dt_start}')
                            model.Add(proc_start_no_chunk >= dt_end).OnlyEnforceIf(start_after_dt_no_chunk)
                            model.Add(proc_start_no_chunk < dt_end).OnlyEnforceIf(start_after_dt_no_chunk.Not())

                            model.AddBoolOr([end_before_dt_no_chunk, start_after_dt_no_chunk]).OnlyEnforceIf(
                                prevent_overlap_no_chunk_dt)


def add_no_overlap_constraints(model, fixed_machine_intervals, machine_to_intervals, unavailable_intervals,
                               machines_count):
    """
    Enhanced to ensure proper no-overlap constraints between tasks.

    This function ensures that no intervals for the same machine will overlap,
    including both fixed intervals, scheduled task intervals, and unavailable intervals.
    """
    for machine in range(machines_count):
        # Collect all intervals for this machine
        intervals = fixed_machine_intervals[machine] + machine_to_intervals[machine] + unavailable_intervals[machine]

        # Add a no-overlap constraint for the machine
        if intervals:
            model.AddNoOverlap(intervals)

            # Add logging to debug interval creation
            print(f"Adding no-overlap constraint for machine {machine} with {len(intervals)} intervals")


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

                    # Enforce that task must be