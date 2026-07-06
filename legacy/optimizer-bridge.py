"""
Optimizer Bridge Script

This script acts as a bridge between the ProFunctv2.7.py optimizer and the web interface.
It provides functions to:
1. Parse the output of the optimizer
2. Extract key metrics
3. Format the data for the web interface
4. Save results in a structured format
"""

import os
import sys
import json
import argparse
import pandas as pd
import re
import time
import datetime
from pathlib import Path

# Define paths
ROOT_DIR = Path(__file__).parent
OUTPUT_DIR = ROOT_DIR / "output"


def parse_optimizer_output(output_text):
    """
    Parse the optimizer output to extract key metrics

    Args:
        output_text (str): The text output from the optimizer

    Returns:
        dict: A dictionary containing key metrics
    """
    metrics = {
        "solver_status": "UNKNOWN",
        "makespan": 0,
        "total_cost": 0,
        "total_production_cost": 0,
        "total_setup_cost": 0,
        "setup_scrap_cost": 0,
        "total_tardiness": 0,
        "weighted_tardiness": 0,
        "total_straddling_reward": 0
    }

    # Function to safely extract float values
    def extract_float(text, pattern):
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1).strip())
            except ValueError:
                return 0
        return 0

    # Function to safely extract string values
    def extract_string(text, pattern):
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        return ""

    # Extract solver status
    if "Solver Status:" in output_text:
        metrics["solver_status"] = extract_string(output_text, r"Solver Status:\s+(.*)")
    elif "StatusName\(\)" in output_text:
        metrics["solver_status"] = extract_string(output_text, r"StatusName\(\)\s+in\s+\(\"(.*?)\"")

    # Extract makespan
    metrics["makespan"] = extract_float(output_text, r"Makespan:\s+([\d\.]+)")

    # Extract cost components
    metrics["total_cost"] = extract_float(output_text, r"Total Cost:\s+([\d\.]+)")
    metrics["total_setup_cost"] = extract_float(output_text, r"Total Setup Cost:\s+([\d\.]+)")
    metrics["setup_scrap_cost"] = extract_float(output_text, r"Total Setup Scrap Cost:\s+([\d\.]+)")
    metrics["total_production_cost"] = extract_float(output_text, r"Total Production Cost:\s+([\d\.]+)")

    # Extract tardiness
    metrics["total_tardiness"] = extract_float(output_text, r"Total Tardiness(?!\s+\(Weighted):\s+([\d\.]+)")
    metrics["weighted_tardiness"] = extract_float(output_text,
                                                  r"Total Tardiness \(Weighted(?:, scaled)?.*?\):\s+([\d\.]+)")

    # Extract straddling reward
    metrics["total_straddling_reward"] = extract_float(output_text, r"Total Straddling Reward:\s+([\d\.]+)")

    # Extract machine utilization
    machine_util_pattern = r"Machine (\d+).*?utilization: ([\d\.]+)%"
    machine_util_matches = re.findall(machine_util_pattern, output_text)

    machine_utilization = {}
    for machine, util in machine_util_matches:
        machine_utilization[int(machine)] = float(util)

    metrics["machine_utilization"] = machine_utilization

    return metrics


def analyze_gantt_data(gantt_file):
    """
    Analyze the Gantt data to extract additional metrics

    Args:
        gantt_file (Path): Path to the gantt_data.csv file

    Returns:
        dict: A dictionary containing additional metrics
    """
    try:
        df = pd.read_csv(gantt_file)

        # Get unique jobs and tasks
        job_ids = []
        for task in df['Task'].unique():
            if ' T' in task and task != 'Downtime':
                job_id = task.split(' T')[0]
                if job_id not in job_ids:
                    job_ids.append(job_id)

        task_count = len(df[df['Task'] != 'Downtime'])
        job_count = len(job_ids)

        # Count phases
        phases = df['Phase'].value_counts().to_dict()

        # Count machines
        machines = df['Machine'].nunique()
        machine_counts = df.groupby('Machine')['Task'].count().to_dict()

        # Calculate time ranges
        min_time = df['Start'].min()
        max_time = df['End'].max()
        total_duration = df['Duration'].sum()

        # Machine utilization
        machine_utilization = {}
        for machine, group in df.groupby('Machine'):
            # Skip downtime entries
            active_df = group[group['Task'] != 'Downtime']
            if len(active_df) > 0:
                total_active_time = active_df['Duration'].sum()
                machine_span = max_time - min_time
                if machine_span > 0:
                    utilization = total_active_time / machine_span
                    machine_utilization[int(machine)] = round(utilization * 100, 1)

        # Average task durations
        avg_durations = {}
        for phase, group in df.groupby('Phase'):
            if phase != 'Downtime':
                avg_durations[phase] = round(group['Duration'].mean(), 1)

        return {
            "job_count": job_count,
            "task_count": task_count,
            "machines_count": machines,
            "phases": phases,
            "time_range": [int(min_time), int(max_time)],
            "total_duration": int(total_duration),
            "machine_utilization": machine_utilization,
            "avg_durations": avg_durations,
            "days": round((max_time / (24 * 60)) + 0.5)  # Convert minutes to days, round up
        }
    except Exception as e:
        print(f"Error analyzing Gantt data: {e}")
        return {
            "gantt_analysis_error": str(e)
        }


def process_optimization_run(optimizer_output, gantt_file, output_dir):
    """
    Process the results of an optimization run

    Args:
        optimizer_output (str): The text output from the optimizer
        gantt_file (Path): Path to the gantt_data.csv file
        output_dir (Path): Directory to save the results

    Returns:
        dict: A dictionary containing all metrics
    """
    # Parse optimizer output
    metrics = parse_optimizer_output(optimizer_output)

    # Add execution time (placeholder since we don't have actual execution time)
    metrics["execution_time"] = 0

    # Analyze Gantt data
    if gantt_file.exists():
        gantt_metrics = analyze_gantt_data(gantt_file)
        metrics.update(gantt_metrics)

    # Save metrics to JSON file
    metrics_file = output_dir / "metrics.json"
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=4)

    return metrics


def main():
    parser = argparse.ArgumentParser(description='Process optimizer output and Gantt data')
    parser.add_argument('--log', type=str, help='Path to the optimizer log file', default=None)
    parser.add_argument('--gantt', type=str, help='Path to the Gantt data CSV file', default=None)
    parser.add_argument('--output', type=str, help='Output directory', default=None)

    args = parser.parse_args()

    # Create timestamp for output directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Determine output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = OUTPUT_DIR / f"run_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    # Determine log file
    if args.log:
        log_file = Path(args.log)
        if log_file.exists():
            with open(log_file, 'r') as f:
                optimizer_output = f.read()
        else:
            print(f"Log file {log_file} not found")
            return
    else:
        # If no log file is provided, look for existing run folders
        run_dirs = list(OUTPUT_DIR.glob("run_*"))
        run_dirs.sort(reverse=True)

        if run_dirs:
            latest_run = run_dirs[0]
            log_file = latest_run / "optimizer_log.txt"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    optimizer_output = f.read()
            else:
                print(f"No optimizer log found in {latest_run}")
                return
        else:
            print("No existing run directories found and no log file provided")
            return

    # Determine Gantt file
    if args.gantt:
        gantt_file = Path(args.gantt)
    else:
        gantt_file = ROOT_DIR / "gantt_data.csv"

    if not gantt_file.exists():
        print(f"Gantt file {gantt_file} not found")
        return

    # Process the run
    metrics = process_optimization_run(optimizer_output, gantt_file, output_dir)

    # Copy Gantt file to output directory
    import shutil
    shutil.copy2(gantt_file, output_dir / "gantt_data.csv")

    # Print summary
    print("\n=== OPTIMIZATION SUMMARY ===")
    print(f"Run ID: {timestamp}")
    print(f"Solver Status: {metrics['solver_status']}")
    print(f"Makespan: {metrics['makespan']} minutes")
    print(f"Total Cost: {metrics['total_cost']}")
    print(f"Jobs: {metrics.get('job_count', 'N/A')}")
    print(f"Tasks: {metrics.get('task_count', 'N/A')}")
    print(f"Machines: {metrics.get('machines_count', 'N/A')}")
    print(f"Results saved to: {output_dir}")
    print("===========================\n")


if __name__ == "__main__":
    main()