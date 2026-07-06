import os
import sys
import argparse
import webbrowser
import subprocess
import threading
import time
import json
import shutil
from pathlib import Path

# Define paths
ROOT_DIR = Path(__file__).parent
STATIC_DIR = ROOT_DIR / "static"


def ensure_dirs():
    """Ensure required directories exist"""
    os.makedirs(ROOT_DIR / "data", exist_ok=True)
    os.makedirs(ROOT_DIR / "output", exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)


def ensure_config():
    """Ensure config file exists with default values"""
    config_path = ROOT_DIR / "scheduler_config.json"
    if not config_path.exists():
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
                "machines_count": 11,
                "machine_cost_per_unit": {
                    "0": 5, "1": 3, "2": 3, "3": 4, "4": 2,
                    "5": 6, "6": 3, "7": 4, "8": 5, "9": 2, "10": 4
                }
            },
            "tool_parameters": {
                "max_tools": {
                    "0": 1, "1": 4, "2": 2
                }
            },
            "feature_flags": {
                "use_seq_dependent_setup": True,
                "use_workcenters": False
            }
        }

        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
        print(f"Created default configuration at {config_path}")


def create_frontend():
    """Create a simple HTML-based frontend"""
    # This imports the create_simple_frontend function from simple_frontend.py
    # If that file exists, use it; otherwise create a minimal HTML file
    simple_frontend_path = ROOT_DIR / "simple_frontend.py"

    if simple_frontend_path.exists():
        try:
            sys.path.insert(0, str(ROOT_DIR))
            from simple_frontend import create_simple_frontend
            create_simple_frontend()
            return
        except Exception as e:
            print(f"Error creating frontend using simple_frontend.py: {e}")

    # Fallback to a minimal HTML file
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Production Scheduler</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; }
        h1 { color: #2563eb; }
        .btn { display: inline-block; background: #2563eb; color: white; padding: 10px 15px; 
               text-decoration: none; border-radius: 4px; border: none; cursor: pointer; }
        .btn:hover { background: #1d4ed8; }
    </style>
</head>
<body>
    <h1>Production Scheduler</h1>
    <p>Welcome to the Production Scheduler interface.</p>
    <p>This simple interface allows you to run the optimizer and view results.</p>
    <button id="runBtn" class="btn">Run Optimizer</button>
    <div id="results" style="margin-top: 20px;"></div>

    <script>
        document.getElementById('runBtn').addEventListener('click', function() {
            this.disabled = true;
            this.textContent = 'Running...';

            fetch('/api/run_optimizer', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    this.disabled = false;
                    this.textContent = 'Run Optimizer';

                    if (data.status === 'success') {
                        document.getElementById('results').innerHTML = 
                            `<h2>Optimization Complete</h2>
                            <p>Status: ${data.metrics.solver_status || 'Unknown'}</p>
                            <p>Makespan: ${data.metrics.makespan || 0} minutes</p>
                            <p>Total Cost: ${data.metrics.total_cost || 0}</p>
                            <p><a href="/api/visualization/latest" target="_blank" class="btn">View Gantt Chart</a></p>`;
                    } else {
                        document.getElementById('results').innerHTML = 
                            `<h2>Optimization Failed</h2>
                            <p>Error: ${data.message}</p>`;
                    }
                })
                .catch(error => {
                    this.disabled = false;
                    this.textContent = 'Run Optimizer';
                    document.getElementById('results').innerHTML = 
                        `<h2>Error</h2>
                        <p>${error.message}</p>`;
                });
        });
    </script>
</body>
</html>"""

    with open(STATIC_DIR / "index.html", 'w') as f:
        f.write(html_content)

    print(f"Created frontend files in {STATIC_DIR}")


def start_backend():
    """Start the Flask backend server"""
    try:
        print("Starting backend server...")
        # Create the backend.py file from the imported content
        backend_path = ROOT_DIR / "backend.py"
        with open(backend_path, 'w') as f:
            f.write(BACKEND_CONTENT)

        # Start the backend server
        subprocess.Popen([sys.executable, str(backend_path)])
        print("Backend server started at http://localhost:5000")
        return True
    except Exception as e:
        print(f"Error starting backend server: {str(e)}")
        return False


def launch_browser():
    """Launch the browser to open the frontend"""
    time.sleep(2)  # Give the server a moment to start
    url = "http://localhost:5000"
    print(f"Opening browser at {url}")
    webbrowser.open(url)


def check_dependencies():
    """Check if required packages are installed"""
    required_packages = ['flask', 'flask_cors', 'pandas', 'numpy', 'ortools']
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print("WARNING: The following required packages are missing:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nPlease install these packages using:")
        print(f"pip install {' '.join(missing_packages)}")
        return False

    return True


def copy_simple_frontend():
    """Create the simple_frontend.py file"""
    simple_frontend_path = ROOT_DIR / "simple_frontend.py"

    with open(simple_frontend_path, 'w') as f:
        f.write(SIMPLE_FRONTEND_CONTENT)

    print(f"Created simple frontend script at {simple_frontend_path}")


def main():
    parser = argparse.ArgumentParser(description='Production Scheduler Launcher')
    parser.add_argument('--port', type=int, default=5000, help='Port for the backend server')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    args = parser.parse_args()

    print("Initializing Production Scheduler...")

    # Check for required packages
    if not check_dependencies():
        print("Missing required packages. Please install them before continuing.")
        sys.exit(1)

    ensure_dirs()
    ensure_config()
    copy_simple_frontend()
    create_frontend()

    # Check if Python files exist in the current directory
    profunct_path = ROOT_DIR / "ProFunctv2.7.py"
    plotly_path = ROOT_DIR / "Plotly2.py"

    if not profunct_path.exists():
        print(f"Warning: ProFunctv2.7.py not found at {profunct_path}")
        print("Please make sure the optimizer script is in the current directory.")
    else:
        print(f"Found optimizer script: {profunct_path}")

    if not plotly_path.exists():
        print(f"Warning: Plotly2.py not found at {plotly_path}")
        print("Please make sure the visualization script is in the current directory.")
    else:
        print(f"Found visualization script: {plotly_path}")

    if start_backend():
        if not args.no_browser:
            threading.Thread(target=launch_browser).start()

        print("\nProduction Scheduler is now running.")
        print("Press Ctrl+C to exit.")

        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down Production Scheduler...")
            sys.exit(0)


# Backend script content (to be written to backend.py)
BACKEND_CONTENT = '''
import json
import os
import shutil
import pandas as pd
import sys
import time
import datetime
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for all routes

# Define paths
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
CONFIG_FILE = ROOT_DIR / "scheduler_config.json"
STATIC_DIR = ROOT_DIR / "static"

# Create directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

def ensure_default_config():
    """Create default configuration file if it doesn't exist"""
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
            "machines_count": 11,
            "machine_cost_per_unit": {
                "0": 5, "1": 3, "2": 3, "3": 4, "4": 2,
                "5": 6, "6": 3, "7": 4, "8": 5, "9": 2, "10": 4
            }
        },
        "tool_parameters": {
            "max_tools": {
                "0": 1, "1": 4, "2": 2
            }
        },
        "feature_flags": {
            "use_seq_dependent_setup": True,
            "use_workcenters": False
        }
    }

    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)

    return default_config

@app.route('/')
def index():
    """Serve the main application page"""
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """Get or update configuration"""
    if request.method == 'GET':
        # Return current configuration
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return jsonify(json.load(f))
        else:
            # Create and return default configuration
            return jsonify(ensure_default_config())
    else:
        # Update configuration
        config_data = request.json
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
        return jsonify({"status": "success", "message": "Configuration updated"})

@app.route('/api/upload/<file_type>', methods=['POST'])
def upload_file(file_type):
    """Handle file uploads"""
    # Map file_type to expected filename
    file_mapping = {
        'jobs': 'new_jobs.csv',
        'fixed': 'fixed_jobs.csv',
        'capacity': 'machine_capacity.csv',
        'transitions': 'setup_transitions.csv',
        'workcenters': 'workcenters.csv'
    }

    if file_type not in file_mapping:
        return jsonify({"status": "error", "message": f"Invalid file type: {file_type}"}), 400

    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400

    filename = file_mapping[file_type]
    file_path = DATA_DIR / filename
    file.save(file_path)

    # For the jobs file, read and return some stats
    if file_type == 'jobs':
        try:
            df = pd.read_csv(file_path)
            job_count = df['JobNumber'].nunique()
            task_count = len(df)
            return jsonify({
                "status": "success", 
                "message": f"File uploaded successfully",
                "stats": {
                    "job_count": job_count,
                    "task_count": task_count
                }
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error parsing CSV: {str(e)}"}), 400

    return jsonify({"status": "success", "message": f"File uploaded successfully"})

@app.route('/api/run_optimizer', methods=['POST'])
def run_optimizer():
    """Run the production scheduler optimizer"""
    # Prepare input files
    try:
        # Check if we have the necessary input file
        if not (DATA_DIR / 'new_jobs.csv').exists():
            # See if it's in the root directory
            if (ROOT_DIR / 'new_jobs.csv').exists():
                # Copy it to the data directory
                shutil.copy2(ROOT_DIR / 'new_jobs.csv', DATA_DIR / 'new_jobs.csv')
            else:
                return jsonify({"status": "error", "message": "new_jobs.csv is required to run the optimizer"}), 400

        # Copy all input files to the root directory
        for file in DATA_DIR.glob('*.csv'):
            target_path = ROOT_DIR / file.name
            if target_path.exists():
                os.remove(target_path)
            shutil.copy2(file, ROOT_DIR)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error preparing input files: {str(e)}"}), 500

    # Ensure config file exists
    ensure_default_config()

    # Create a timestamped output directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"run_{timestamp}"
    os.makedirs(run_dir, exist_ok=True)

    # Run the optimizer in a separate process
    try:
        start_time = time.time()

        # Execute ProFunctv2.7.py
        result = subprocess.run(
            [sys.executable, "ProFunctv2.7.py"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes timeout
        )

        end_time = time.time()
        execution_time = end_time - start_time

        # Check if the gantt_data.csv file was created
        gantt_file = ROOT_DIR / "gantt_data.csv"
        if not gantt_file.exists():
            return jsonify({
                "status": "error", 
                "message": "Optimization failed to produce gantt_data.csv",
                "stdout": result.stdout,
                "stderr": result.stderr
            }), 500

        # Save the log files
        with open(run_dir / "optimizer_log.txt", "w") as f:
            f.write(result.stdout)

        if result.stderr:
            with open(run_dir / "optimizer_errors.txt", "w") as f:
                f.write(result.stderr)

        # Copy gantt_data.csv to the output directory
        shutil.copy2(gantt_file, run_dir)

        # Parse the optimizer output
        metrics = parse_optimizer_output(result.stdout)
        metrics["execution_time"] = execution_time

        # Run the Plotly visualization
        try:
            plot_result = subprocess.run(
                [sys.executable, "Plotly2.py"],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )

            # Copy the HTML file to the output directory
            html_file = ROOT_DIR / "gantt_chart_production_schedule.html"
            if html_file.exists():
                shutil.copy2(html_file, run_dir)
                metrics["gantt_chart_path"] = str(run_dir / "gantt_chart_production_schedule.html")

            # Save the Plotly log
            with open(run_dir / "plotly_log.txt", "w") as f:
                f.write(plot_result.stdout)

            if plot_result.stderr:
                with open(run_dir / "plotly_errors.txt", "w") as f:
                    f.write(plot_result.stderr)

        except Exception as e:
            # If visualization fails, continue anyway but log the error
            metrics["visualization_error"] = str(e)

        # Analyze Gantt data
        gantt_analysis = analyze_gantt_data(gantt_file)
        metrics.update(gantt_analysis)

        # Save metrics to JSON file
        with open(run_dir / "metrics.json", "w") as f:
            json.dump(metrics, f, indent=4)

        # Return the results
        return jsonify({
            "status": "success", 
            "message": "Optimization completed successfully",
            "run_id": timestamp,
            "metrics": metrics
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "error", 
            "message": "Optimization timed out after 30 minutes"
        }), 500
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Error running optimizer: {str(e)}"
        }), 500

def parse_optimizer_output(output):
    """Parse the optimizer output to extract key metrics"""
    metrics = {
        "solver_status": "UNKNOWN",
        "makespan": 0,
        "total_cost": 0,
        "total_production_cost": 0,
        "total_setup_cost": 0,
        "setup_scrap_cost": 0,
        "total_tardiness": 0,
        "weighted_tardiness": 0
    }

    # Extract key metrics using string parsing
    lines = output.split('\\n')
    for line in lines:
        line = line.strip()

        if "Solver Status:" in line:
            metrics["solver_status"] = line.split("Solver Status:")[1].strip()

        elif "Makespan:" in line:
            try:
                metrics["makespan"] = int(line.split("Makespan:")[1].strip())
            except:
                pass

        elif "Total Cost:" in line:
            try:
                metrics["total_cost"] = float(line.split("Total Cost:")[1].strip())
            except:
                pass

        elif "Total Setup Cost:" in line:
            try:
                metrics["total_setup_cost"] = float(line.split("Total Setup Cost:")[1].strip())
            except:
                pass

        elif "Total Setup Scrap Cost:" in line:
            try:
                metrics["setup_scrap_cost"] = float(line.split("Total Setup Scrap Cost:")[1].strip())
            except:
                pass

        elif "Total Production Cost:" in line:
            try:
                metrics["total_production_cost"] = float(line.split("Total Production Cost:")[1].strip())
            except:
                pass

        elif "Total Tardiness (Weighted, scaled):" in line:
            try:
                metrics["weighted_tardiness"] = float(line.split("Total Tardiness (Weighted, scaled):")[1].strip())
            except:
                pass

        elif "Total Tardiness:" in line and "Weighted" not in line:
            try:
                metrics["total_tardiness"] = float(line.split("Total Tardiness:")[1].strip())
            except:
                pass

    return metrics

def analyze_gantt_data(gantt_file):
    """Analyze the Gantt data to extract additional metrics"""
    try:
        df = pd.read_csv(gantt_file)

        # Count unique jobs and tasks
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

        return {
            "job_count": job_count,
            "task_count": task_count,
            "machines_count": machines,
            "phases": phases,
            "time_range": [min_time, max_time],
            "total_duration": total_duration,
            "machine_utilization": machine_utilization,
            "days": (max_time / (24 * 60)) + 1  # Convert minutes to days, round up
        }
    except Exception as e:
        return {
            "gantt_analysis_error": str(e)
        }

@app.route('/api/visualization/<run_id>', methods=['GET'])
def get_visualization(run_id):
    """Get the HTML visualization for a specific run"""
    if run_id == "latest":
        # Find the most recent run
        run_dirs = list(OUTPUT_DIR.glob("run_*"))
        run_dirs.sort(reverse=True)

        if not run_dirs:
            # Try to serve from the root directory
            html_file = ROOT_DIR / "gantt_chart_production_schedule.html"
            if not html_file.exists():
                return jsonify({"status": "error", "message": "No visualizations found"}), 404

            with open(html_file, 'r') as f:
                html_content = f.read()

            return html_content, 200, {'Content-Type': 'text/html'}

        run_id = run_dirs[0].name.replace("run_", "")

    run_dir = OUTPUT_DIR / f"run_{run_id}"

    if not run_dir.exists() or not run_dir.is_dir():
        return jsonify({"status": "error", "message": f"Run ID {run_id} not found"}), 404

    html_file = run_dir / "gantt_chart_production_schedule.html"
    if not html_file.exists():
        return jsonify({"status": "error", "message": f"Visualization not found for run ID {run_id}"}), 404

    with open(html_file, 'r') as f:
        html_content = f.read()

    return html_content, 200, {'Content-Type': 'text/html'}

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory(STATIC_DIR, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
'''

# Simple Frontend content
SIMPLE_FRONTEND_CONTENT = """
\"\"\"
This script creates a simple HTML-based frontend that doesn't rely on React or complex JavaScript features.
It's designed to replace the static/index.html file in the production scheduler application.
\"\"\"

import os
from pathlib import Path

def create_simple_frontend():
    \"\"\"Creates a simple HTML frontend for the production scheduler\"\"\"

    html_content = \"\"\"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Production Scheduler</title>
    <!-- Simple stylesheet instead of Tailwind -->
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 15px;
        }
        header {
            background-color: #2563eb;
            color: white;
            padding: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .header-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .main-title {
            font-size: 1.5rem;
            margin: 0;
        }
        .btn {
            display: inline-block;
            font-weight: 400;
            text-align: center;
            white-space: nowrap;
            vertical-align: middle;
            user-select: none;
            border: 1px solid transparent;
            padding: 0.375rem 0.75rem;
            font-size: 1rem;
            line-height: 1.5;
            border-radius: 0.25rem;
            transition: all 0.15s ease-in-out;
            text-decoration: none;
            cursor: pointer;
        }
        .btn-primary {
            color: #fff;
            background-color: #3b82f6;
            border-color: #3b82f6;
        }
        .btn-primary:hover {
            background-color: #2563eb;
            border-color: #2563eb;
        }
        .content {
            display: flex;
            min-height: calc(100vh - 60px);
        }
        .sidebar {
            width: 280px;
            background-color: #fff;
            border-right: 1px solid #e5e5e5;
            box-shadow: 2px 0 5px rgba(0,0,0,0.05);
            padding: 1rem;
            overflow-y: auto;
        }
        .main-content {
            flex: 1;
            padding: 1.5rem;
            overflow-y: auto;
        }
        .card {
            background-color: #fff;
            border-radius: 0.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 1.5rem;
            overflow: hidden;
        }
        .card-header {
            background-color: #f0f5ff;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #dae8fe;
        }
        .card-header h2 {
            margin: 0;
            font-size: 1.25rem;
            color: #2563eb;
        }
        .card-body {
            padding: 1rem;
        }
        .form-group {
            margin-bottom: 1rem;
        }
        label {
            display: block;
            margin-bottom: 0.25rem;
            font-weight: 500;
        }
        input[type="text"],
        input[type="number"],
        select {
            display: block;
            width: 100%;
            padding: 0.375rem 0.75rem;
            font-size: 1rem;
            line-height: 1.5;
            color: #495057;
            background-color: #fff;
            background-clip: padding-box;
            border: 1px solid #ced4da;
            border-radius: 0.25rem;
            transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
        }
        input[type="checkbox"] {
            margin-right: 0.5rem;
        }
        .checkbox-label {
            display: flex;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        .alert {
            padding: 0.75rem 1.25rem;
            margin-bottom: 1rem;
            border: 1px solid transparent;
            border-radius: 0.25rem;
        }
        .alert-primary {
            color: #004085;
            background-color: #cce5ff;
            border-color: #b8daff;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1rem;
        }
        .stat-card {
            background-color: #f0f5ff;
            border: 1px solid #dae8fe;
            border-radius: 0.25rem;
            padding: 1rem;
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #2563eb;
        }
        .stat-label {
            font-size: 0.875rem;
            color: #6b7280;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 0.5rem;
            text-align: left;
            border-bottom: 1px solid #e5e5e5;
        }
        th {
            background-color: #f3f4f6;
            font-weight: 600;
        }
        .tabs {
            display: flex;
            border-bottom: 1px solid #e5e5e5;
            margin-bottom: 1rem;
        }
        .tab {
            padding: 0.5rem 1rem;
            cursor: pointer;
            border-bottom: 2px solid transparent;
        }
        .tab.active {
            border-bottom-color: #2563eb;
            color: #2563eb;
            font-weight: 500;
        }
        .loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            padding: 2rem;
        }
        .loading-spinner {
            border: 4px solid rgba(0, 0, 0, 0.1);
            border-left-color: #2563eb;
            border-radius: 50%;
            width: 36px;
            height: 36px;
            animation: spin 1s linear infinite;
            margin-bottom: 1rem;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .visualization-placeholder {
            height: 400px;
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #f9fafb;
            border: 1px dashed #d1d5db;
            border-radius: 0.25rem;
        }
        .hidden {
            display: none;
        }
        .accordion-header {
            background-color: #f3f4f6;
            padding: 0.5rem 1rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-radius: 0.25rem;
            margin-bottom: 0.5rem;
        }
        .accordion-header:hover {
            background-color: #e5e7eb;
        }
        .accordion-content {
            padding: 1rem;
            border: 1px solid #e5e7eb;
            border-radius: 0.25rem;
            margin-bottom: 1rem;
        }
        .file-upload {
            display: flex;
            flex-direction: column;
            margin-bottom: 0.5rem;
        }
        .file-upload-label {
            margin-bottom: 0.25rem;
            font-weight: 500;
        }
        .file-upload-input {
            margin-bottom: 0.25rem;
        }
        .file-status {
            font-size: 0.875rem;
            color: #6b7280;
        }
    </style>
</head>
<body>
    <header>
        <div class="header-container container">
            <h1 class="main-title">Production Scheduler</h1>
            <div>
                <button id="runOptimizer" class="btn btn-primary">Run Optimizer</button>
            </div>
        </div>
    </header>

    <div class="content">
        <!-- Sidebar -->
        <div class="sidebar">
            <h2>Configuration</h2>

            <div class="accordion">
                <div class="accordion-header" onclick="toggleAccordion('solverParams')">
                    Solver Parameters
                    <span class="toggle-icon">▾</span>
                </div>
                <div id="solverParams" class="accordion-content hidden">
                    <div class="form-group">
                        <label for="maxTime">Max Time (seconds)</label>
                        <input type="number" id="maxTime" value="1800" min="1" step="1">
                    </div>
                    <div class="form-group">
                        <div class="checkbox-label">
                            <input type="checkbox" id="usePenalties" checked>
                            <label for="usePenalties">Use Penalties</label>
                        </div>
                    </div>
                </div>
            </div>

            <div class="accordion">
                <div class="accordion-header" onclick="toggleAccordion('costParams')">
                    Cost Parameters
                    <span class="toggle-icon">▾</span>
                </div>
                <div id="costParams" class="accordion-content hidden">
                    <div class="form-group">
                        <label for="setupCost">Setup Cost</label>
                        <input type="number" id="setupCost" value="10" min="0" step="1">
                    </div>
                    <div class="form-group">
                        <label for="weightTardiness">Tardiness Weight</label>
                        <input type="number" id="weightTardiness" value="5.0" min="0" step="0.1">
                    </div>
                    <div class="form-group">
                        <label for="mustDoPenalty">Must-Do Penalty</label>
                        <input type="number" id="mustDoPenalty" value="10.0" min="0" step="0.1">
                    </div>
                    <div class="form-group">
                        <label for="setupScrapCost">Setup Scrap Cost</label>
                        <input type="number" id="setupScrapCost" value="5" min="0" step="1">
                    </div>
                </div>
            </div>

            <div class="accordion">
                <div class="accordion-header" onclick="toggleAccordion('featureFlags')">
                    Feature Flags
                    <span class="toggle-icon">▾</span>
                </div>
                <div id="featureFlags" class="accordion-content hidden">
                    <div class="form-group">
                        <div class="checkbox-label">
                            <input type="checkbox" id="useSeqDependentSetup" checked>
                            <label for="useSeqDependentSetup">Use Sequence-Dependent Setup</label>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="checkbox-label">
                            <input type="checkbox" id="useWorkcenters">
                            <label for="useWorkcenters">Use Workcenters</label>
                        </div>
                    </div>
                </div>
            </div>

            <div class="accordion">
                <div class="accordion-header" onclick="toggleAccordion('inputFiles')">
                    Input Files
                    <span class="toggle-icon">▾</span>
                </div>
                <div id="inputFiles" class="accordion-content hidden">
                    <div class="file-upload">
                        <div class="file-upload-label">new_jobs.csv</div>
                        <input type="file" id="newJobsFile" class="file-upload-input" accept=".csv">
                        <div class="file-status" id="newJobsStatus">No file uploaded</div>
                    </div>
                    <div class="file-upload">
                        <div class="file-upload-label">fixed_jobs.csv</div>
                        <input type="file" id="fixedJobsFile" class="file-upload-input" accept=".csv">
                        <div class="file-status" id="fixedJobsStatus">No file uploaded</div>
                    </div>
                    <div class="file-upload">
                        <div class="file-upload-label">machine_capacity.csv</div>
                        <input type="file" id="capacityFile" class="file-upload-input" accept=".csv">
                        <div class="file-status" id="capacityStatus">No file uploaded</div>
                    </div>
                    <div class="file-upload">
                        <div class="file-upload-label">setup_transitions.csv</div>
                        <input type="file" id="transitionsFile" class="file-upload-input" accept=".csv">
                        <div class="file-status" id="transitionsStatus">No file uploaded</div>
                    </div>
                    <div class="file-upload">
                        <div class="file-upload-label">workcenters.csv</div>
                        <input type="file" id="workcentersFile" class="file-upload-input" accept=".csv">
                        <div class="file-status" id="workcentersStatus">No file uploaded</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div id="loadingSection" class="loading hidden">
                <div class="loading-spinner"></div>
                <h3>Running optimization...</h3>
                <p>This may take a few minutes</p>
            </div>

            <div id="welcomeSection">
                <div class="card">
                    <div class="card-header">
                        <h2>Welcome to Production Scheduler</h2>
                    </div>
                    <div class="card-body">
                        <p>This application helps you optimize production schedules using advanced algorithms.</p>
                        <p>To get started:</p>
                        <ol>
                            <li>Configure optimization parameters in the sidebar</li>
                            <li>Upload your input files (at minimum, new_jobs.csv is required)</li>
                            <li>Click "Run Optimizer" to generate a schedule</li>
                        </ol>
                        <div class="alert alert-primary">
                            <strong>Note:</strong> Make sure ProFunctv2.7.py and Plotly2.py are in the same directory as the launcher script.
                        </div>
                        <button id="startOptimizationBtn" class="btn btn-primary">Run Optimizer</button>
                    </div>
                </div>
            </div>

            <div id="resultsSection" class="hidden">
                <div class="card">
                    <div class="card-header">
                        <h2>Optimization Results</h2>
                    </div>
                    <div class="card-body">
                        <div class="grid">
                            <div class="stat-card">
                                <div class="stat-label">Solver Status</div>
                                <div id="solverStatus" class="stat-value">OPTIMAL</div>
                                <div id="executionTime" class="stat-label">Execution Time: 32.5 seconds</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-label">Makespan</div>
                                <div id="makespan" class="stat-value">13796 minutes</div>
                                <div id="makespanDays" class="stat-label">9 days, 13 hours</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-label">Total Cost</div>
                                <div id="totalCost" class="stat-value">287,563</div>
                            </div>
                        </div>

                        <h3>Cost Breakdown</h3>
                        <table>
                            <thead>
                                <tr>
                                    <th>Component</th>
                                    <th>Value</th>
                                    <th>Weight</th>
                                    <th>Weighted Value</th>
                                    <th>% of Total</th>
                                </tr>
                            </thead>
                            <tbody id="costBreakdownBody">
                                <!-- Cost breakdown will be inserted here -->
                            </tbody>
                        </table>

                        <div class="grid" style="margin-top: 1.5rem">
                            <div>
                                <h3>Job Summary</h3>
                                <div class="stat-card">
                                    <div class="form-group">
                                        <div class="stat-label">Total Jobs</div>
                                        <div id="totalJobs" class="stat-value">16</div>
                                    </div>
                                    <div class="form-group">
                                        <div class="stat-label">Total Tasks</div>
                                        <div id="totalTasks" class="stat-value">112</div>
                                    </div>
                                    <div class="form-group">
                                        <div class="stat-label">Avg Tasks per Job</div>
                                        <div id="avgTasksPerJob" class="stat-value">7.0</div>
                                    </div>
                                </div>
                            </div>
                            <div>
                                <h3>Machine Summary</h3>
                                <div class="stat-card">
                                    <div class="form-group">
                                        <div class="stat-label">Machines Used</div>
                                        <div id="machinesUsed" class="stat-value">11</div>
                                    </div>
                                    <div class="form-group">
                                        <div class="stat-label">Avg Tasks per Machine</div>
                                        <div id="avgTasksPerMachine" class="stat-value">10.2</div>
                                    </div>
                                    <div class="form-group">
                                        <div class="stat-label">Avg Production Cost per Task</div>
                                        <div id="avgProductionCost" class="stat-value">1,655.6</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h2>Production Schedule Gantt Chart</h2>
                    </div>
                    <div class="card-body">
                        <div class="visualization-placeholder" id="ganttChartPlaceholder">
                            <div class="text-center">
                                <div style="font-size: 3rem; color: #d1d5db; margin-bottom: 1rem;">📊</div>
                                <p>Gantt Chart Visualization</p>
                                <p style="font-size: 0.875rem; color: #6b7280;">Time Range: <span id="timeRange">0 - 14000</span> minutes</p>
                                <a href="/api/visualization/latest" target="_blank" class="btn btn-primary" style="margin-top: 1rem;">View Interactive Chart</a>
                            </div>
                        </div>

                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-top: 1.5rem;">
                            <div>
                                <h3>Machines</h3>
                                <div style="max-height: 300px; overflow-y: auto; border: 1px solid #e5e5e5; border-radius: 0.25rem;">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Machine</th>
                                                <th>Utilization</th>
                                            </tr>
                                        </thead>
                                        <tbody id="machinesTableBody">
                                            <!-- Machines will be inserted here -->
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            <div>
                                <h3>Jobs</h3>
                                <div style="max-height: 300px; overflow-y: auto; border: 1px solid #e5e5e5; border-radius: 0.25rem;">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Job</th>
                                                <th>Tasks</th>
                                            </tr>
                                        </thead>
                                        <tbody id="jobsTableBody">
                                            <!-- Jobs will be inserted here -->
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            <div>
                                <h3>Phases</h3>
                                <div style="max-height: 300px; overflow-y: auto; border: 1px solid #e5e5e5; border-radius: 0.25rem;">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Phase</th>
                                                <th>Count</th>
                                            </tr>
                                        </thead>
                                        <tbody id="phasesTableBody">
                                            <!-- Phases will be inserted here -->
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Utility functions
        function toggleAccordion(id) {
            const content = document.getElementById(id);
            content.classList.toggle('hidden');
        }

        function showSection(sectionId) {
            // Hide all sections
            document.getElementById('welcomeSection').classList.add('hidden');
            document.getElementById('loadingSection').classList.add('hidden');
            document.getElementById('resultsSection').classList.add('hidden');

            // Show the selected section
            document.getElementById(sectionId).classList.remove('hidden');
        }

        function formatNumber(num) {
            return new Intl.NumberFormat().format(num);
        }

        // Handle file uploads
        function setupFileUpload(fileId, statusId, fileType) {
            const fileInput = document.getElementById(fileId);
            const statusElement = document.getElementById(statusId);

            fileInput.addEventListener('change', function() {
                if (this.files.length > 0) {
                    const file = this.files[0];
                    statusElement.textContent = `Selected: ${file.name}`;

                    // Create form data
                    const formData = new FormData();
                    formData.append('file', file);

                    // Upload file
                    fetch(`/api/upload/${fileType}`, {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            statusElement.textContent = `Uploaded: ${file.name}`;
                            if (data.stats) {
                                statusElement.textContent += ` (${data.stats.job_count} jobs, ${data.stats.task_count} tasks)`;
                            }
                        } else {
                            statusElement.textContent = `Error: ${data.message}`;
                        }
                    })
                    .catch(error => {
                        statusElement.textContent = `Error: ${error.message}`;
                    });
                } else {
                    statusElement.textContent = 'No file selected';
                }
            });
        }

        // Get configuration
        function getConfiguration() {
            return {
                solver_parameters: {
                    max_time_in_seconds: parseFloat(document.getElementById('maxTime').value),
                    use_penalties: document.getElementById('usePenalties').checked
                },
                cost_parameters: {
                    setup_cost: parseInt(document.getElementById('setupCost').value),
                    weight_tardiness: parseFloat(document.getElementById('weightTardiness').value),
                    must_do_penalty: parseFloat(document.getElementById('mustDoPenalty').value),
                    setup_scrap_cost_per_unit: parseInt(document.getElementById('setupScrapCost').value)
                },
                feature_flags: {
                    use_seq_dependent_setup: document.getElementById('useSeqDependentSetup').checked,
                    use_workcenters: document.getElementById('useWorkcenters').checked
                }
            };
        }

        // Run optimizer
        function runOptimizer() {
            showSection('loadingSection');

            // Get configuration
            const config = getConfiguration();

            // Update configuration
            fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(config)
            })
            .then(response => response.json())
            .then(data => {
                // Run optimizer
                return fetch('/api/run_optimizer', {
                    method: 'POST'
                });
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Update results
                    updateResults(data.metrics);
                    showSection('resultsSection');
                } else {
                    alert(`Optimization failed: ${data.message}`);
                    showSection('welcomeSection');
                }
            })
            .catch(error => {
                console.error('Error running optimizer:', error);
                alert('Error running optimizer. See console for details.');
                showSection('welcomeSection');
            });
        }

        // Update results display
        function updateResults(metrics) {
            // Update summary stats
            document.getElementById('solverStatus').textContent = metrics.solver_status || 'UNKNOWN';
            document.getElementById('executionTime').textContent = `Execution Time: ${metrics.execution_time?.toFixed(1) || 'N/A'} seconds`;
            document.getElementById('makespan').textContent = `${formatNumber(metrics.makespan || 0)} minutes`;

            // Calculate days and hours
            const days = Math.floor((metrics.makespan || 0) / (24 * 60));
            const hours = Math.floor(((metrics.makespan || 0) % (24 * 60)) / 60);
            document.getElementById('makespanDays').textContent = `${days} days, ${hours} hours`;

            document.getElementById('totalCost').textContent = formatNumber(metrics.total_cost || 0);

            // Update cost breakdown
            const costBreakdownBody = document.getElementById('costBreakdownBody');
            costBreakdownBody.innerHTML = '';

            const totalCost = metrics.total_cost || 1;  // Avoid division by zero

            // Production Cost
            const prodCost = metrics.total_production_cost || 0;
            const prodCostRow = document.createElement('tr');
            prodCostRow.innerHTML = `
                <td>Production Cost</td>
                <td>${formatNumber(prodCost)}</td>
                <td>1</td>
                <td>${formatNumber(prodCost)}</td>
                <td>${((prodCost / totalCost) * 100).toFixed(1)}%</td>
            `;
            costBreakdownBody.appendChild(prodCostRow);

            // Setup Cost
            const setupCost = metrics.total_setup_cost || 0;
            const setupCostRow = document.createElement('tr');
            setupCostRow.innerHTML = `
                <td>Setup Cost</td>
                <td>${formatNumber(setupCost)}</td>
                <td>1</td>
                <td>${formatNumber(setupCost)}</td>
                <td>${((setupCost / totalCost) * 100).toFixed(1)}%</td>
            `;
            costBreakdownBody.appendChild(setupCostRow);

            // Setup Scrap Cost
            const scrapCost = metrics.setup_scrap_cost || 0;
            const scrapCostRow = document.createElement('tr');
            scrapCostRow.innerHTML = `
                <td>Setup Scrap Cost</td>
                <td>${formatNumber(scrapCost)}</td>
                <td>1</td>
                <td>${formatNumber(scrapCost)}</td>
                <td>${((scrapCost / totalCost) * 100).toFixed(1)}%</td>
            `;
            costBreakdownBody.appendChild(scrapCostRow);

            // Tardiness
            const tardiness = metrics.total_tardiness || 0;
            const weightedTardiness = metrics.weighted_tardiness || 0;
            const tardinessWeight = tardiness ? (weightedTardiness / tardiness).toFixed(1) : 0;
            const tardinessRow = document.createElement('tr');
            tardinessRow.innerHTML = `
                <td>Tardiness</td>
                <td>${formatNumber(tardiness)}</td>
                <td>${tardinessWeight}</td>
                <td>${formatNumber(weightedTardiness)}</td>
                <td>${((weightedTardiness / totalCost) * 100).toFixed(1)}%</td>
            `;
            costBreakdownBody.appendChild(tardinessRow);

            // Total
            const totalRow = document.createElement('tr');
            totalRow.style.fontWeight = 'bold';
            totalRow.style.backgroundColor = '#f3f4f6';
            totalRow.innerHTML = `
                <td>TOTAL</td>
                <td></td>
                <td></td>
                <td>${formatNumber(totalCost)}</td>
                <td>100%</td>
            `;
            costBreakdownBody.appendChild(totalRow);

            // Update job and machine summaries
            document.getElementById('totalJobs').textContent = metrics.job_count || 'N/A';
            document.getElementById('totalTasks').textContent = metrics.task_count || 'N/A';

            const avgTasksPerJob = metrics.job_count ? (metrics.task_count / metrics.job_count).toFixed(1) : 'N/A';
            document.getElementById('avgTasksPerJob').textContent = avgTasksPerJob;

            document.getElementById('machinesUsed').textContent = metrics.machines_count || 'N/A';

            const avgTasksPerMachine = metrics.machines_count ? (metrics.task_count / metrics.machines_count).toFixed(1) : 'N/A';
            document.getElementById('avgTasksPerMachine').textContent = avgTasksPerMachine;

            const avgProductionCost = metrics.task_count ? (metrics.total_production_cost / metrics.task_count).toFixed(1) : 'N/A';
            document.getElementById('avgProductionCost').textContent = formatNumber(avgProductionCost);

            // Update Gantt chart info
            if (metrics.time_range) {
                document.getElementById('timeRange').textContent = `${formatNumber(metrics.time_range[0])} - ${formatNumber(metrics.time_range[1])}`;
            }

            // Update machine utilization table
            const machinesTableBody = document.getElementById('machinesTableBody');
            machinesTableBody.innerHTML = '';

            if (metrics.machine_utilization) {
                Object.entries(metrics.machine_utilization).forEach(([machineId, utilization]) => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>Machine-${machineId}</td>
                        <td>${utilization}%</td>
                    `;
                    machinesTableBody.appendChild(row);
                });
            }

            // Create mock job data
            const jobsTableBody = document.getElementById('jobsTableBody');
            jobsTableBody.innerHTML = '';

            if (metrics.job_count) {
                // Create mock job data since we don't have actual job IDs
                const avgTasks = Math.round(metrics.task_count / metrics.job_count);
                for (let i = 0; i < metrics.job_count; i++) {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>Job-${i+1}</td>
                        <td>${avgTasks}</td>
                    `;
                    jobsTableBody.appendChild(row);
                }
            }

            // Update phases table
            const phasesTableBody = document.getElementById('phasesTableBody');
            phasesTableBody.innerHTML = '';

            if (metrics.phases) {
                let totalPhases = 0;
                Object.entries(metrics.phases).forEach(([phase, count]) => {
                    totalPhases += count;
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${phase}</td>
                        <td>${count}</td>
                    `;
                    phasesTableBody.appendChild(row);
                });

                // Add total row
                const totalRow = document.createElement('tr');
                totalRow.style.fontWeight = 'bold';
                totalRow.style.backgroundColor = '#f3f4f6';
                totalRow.innerHTML = `
                    <td>Total</td>
                    <td>${totalPhases}</td>
                `;
                phasesTableBody.appendChild(totalRow);
            }
        }

        // Load configuration
        function loadConfiguration() {
            fetch('/api/config')
                .then(response => response.json())
                .then(config => {
                    // Solver parameters
                    if (config.solver_parameters) {
                        document.getElementById('maxTime').value = config.solver_parameters.max_time_in_seconds || 1800;
                        document.getElementById('usePenalties').checked = config.solver_parameters.use_penalties !== false;
                    }

                    // Cost parameters
                    if (config.cost_parameters) {
                        document.getElementById('setupCost').value = config.cost_parameters.setup_cost || 10;
                        document.getElementById('weightTardiness').value = config.cost_parameters.weight_tardiness || 5.0;
                        document.getElementById('mustDoPenalty').value = config.cost_parameters.must_do_penalty || 10.0;
                        document.getElementById('setupScrapCost').value = config.cost_parameters.setup_scrap_cost_per_unit || 5;
                    }

                    // Feature flags
                    if (config.feature_flags) {
                        document.getElementById('useSeqDependentSetup').checked = config.feature_flags.use_seq_dependent_setup !== false;
                        document.getElementById('useWorkcenters').checked = config.feature_flags.use_workcenters === true;
                    }
                })
                .catch(error => {
                    console.error('Error loading configuration:', error);
                });
        }

        // Initialize the application
        document.addEventListener('DOMContentLoaded', function() {
            // Set up file uploads
            setupFileUpload('newJobsFile', 'newJobsStatus', 'jobs');
            setupFileUpload('fixedJobsFile', 'fixedJobsStatus', 'fixed');
            setupFileUpload('capacityFile', 'capacityStatus', 'capacity');
            setupFileUpload('transitionsFile', 'transitionsStatus', 'transitions');
            setupFileUpload('workcentersFile', 'workcentersStatus', 'workcenters');

            // Set up run buttons
            document.getElementById('runOptimizer').addEventListener('click', runOptimizer);
            document.getElementById('startOptimizationBtn').addEventListener('click', runOptimizer);

            // Load configuration
            loadConfiguration();

            // Show welcome section by default
            showSection('welcomeSection');
        });
    </script>
</body>
</html>
    \"\"\"

    # Create directory for static files
    static_dir = Path("static")
    static_dir.mkdir(exist_ok=True)

    # Write the HTML file
    with open(static_dir / "index.html", "w") as f:
        f.write(html_content)

    print(f"Created simple frontend at {static_dir / 'index.html'}")

if __name__ == "__main__":
    create_simple_frontend()
"""

if __name__ == "__main__":
    main()