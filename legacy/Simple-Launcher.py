import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

# Define the minimal Flask backend script
BACKEND_SCRIPT = '''
import os
import sys  # Added sys import here
import subprocess
import json
import shutil
from flask import Flask, send_from_directory, request, jsonify
from pathlib import Path

app = Flask(__name__, static_folder='static')

# Create necessary directories
ROOT_DIR = Path(__file__).parent
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route('/api/run_optimizer', methods=['POST'])
def run_optimizer():
    """Run the optimizer script"""
    try:
        # Copy input files if they exist in data directory
        for file in DATA_DIR.glob('*.csv'):
            target_path = ROOT_DIR / file.name
            if target_path.exists():
                os.remove(target_path)
            shutil.copy2(file, ROOT_DIR)
            print(f"Copied {file.name} to root directory")

        # Check if we have the required file
        if not (ROOT_DIR / 'new_jobs.csv').exists():
            return jsonify({"status": "error", "message": "Missing required file: new_jobs.csv"}), 400

        # Run the optimizer
        profunct_path = ROOT_DIR / "ProFunctv2.7.py"
        if not profunct_path.exists():
            return jsonify({"status": "error", "message": "Missing ProFunctv2.7.py script"}), 400

        print("Starting optimizer...")
        result = subprocess.run(
            [sys.executable, str(profunct_path)],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True
        )

        print("Optimizer completed with exit code:", result.returncode)

        # Check if gantt_data.csv was created
        gantt_file = ROOT_DIR / "gantt_data.csv"
        if not gantt_file.exists():
            return jsonify({
                "status": "error", 
                "message": "Optimizer failed to create gantt_data.csv file",
                "stdout": result.stdout,
                "stderr": result.stderr
            }), 500

        # Run the visualization script
        plotly_path = ROOT_DIR / "Plotly2.py"
        if plotly_path.exists():
            print("Running visualization...")
            viz_result = subprocess.run(
                [sys.executable, str(plotly_path)],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True
            )
            print("Visualization completed with exit code:", viz_result.returncode)

        # Simple parsing of the output for basic metrics
        metrics = {}

        # Extract makespan
        for line in result.stdout.split("\\n"):
            if "Makespan:" in line:
                try:
                    metrics["makespan"] = int(line.split("Makespan:")[1].strip())
                except:
                    pass
            elif "Total Cost:" in line:
                try:
                    metrics["total_cost"] = float(line.split("Total Cost:")[1].strip())
                except:
                    pass
            elif "Solver Status:" in line:
                metrics["solver_status"] = line.split("Solver Status:")[1].strip()

        return jsonify({
            "status": "success",
            "message": "Optimization completed successfully",
            "metrics": metrics,
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/visualization/latest', methods=['GET'])
def get_visualization():
    """Serve the Gantt chart visualization"""
    html_file = ROOT_DIR / "gantt_chart_production_schedule.html"
    if not html_file.exists():
        return jsonify({"status": "error", "message": "Visualization file not found"}), 404

    with open(html_file, 'r') as f:
        html_content = f.read()

    return html_content, 200, {'Content-Type': 'text/html'}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
'''

# Define a simple HTML frontend
SIMPLE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Production Scheduler</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; max-width: 800px; margin: 0 auto; }
        h1 { color: #2563eb; }
        .btn { display: inline-block; background: #2563eb; color: white; padding: 10px 15px; 
               text-decoration: none; border-radius: 4px; border: none; cursor: pointer; }
        .btn:hover { background: #1d4ed8; }
        .loading { display: none; margin-top: 20px; }
        .spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid rgba(0,0,0,0.1); 
                  border-radius: 50%; border-top-color: #2563eb; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .result-box { margin-top: 20px; padding: 15px; border: 1px solid #ccc; border-radius: 4px; }
        .success { background-color: #d1fae5; border-color: #34d399; }
        .error { background-color: #fee2e2; border-color: #f87171; }
    </style>
</head>
<body>
    <h1>Production Scheduler</h1>
    <p>Welcome to the Production Scheduler interface.</p>
    <p>This simple interface allows you to run the optimizer and view results.</p>

    <div>
        <p><strong>Required files:</strong></p>
        <ul>
            <li>ProFunctv2.7.py - Main optimizer script</li>
            <li>Plotly2.py - Visualization script</li>
            <li>new_jobs.csv - Job definitions (required)</li>
            <li>fixed_jobs.csv - Fixed job definitions (optional)</li>
            <li>machine_capacity.csv - Machine capacity data (optional)</li>
        </ul>
    </div>

    <button id="runBtn" class="btn">Run Optimizer</button>

    <div id="loading" class="loading">
        <div class="spinner"></div> Running optimization... This may take several minutes. Please wait.
    </div>

    <div id="results"></div>

    <script>
        document.getElementById('runBtn').addEventListener('click', function() {
            this.disabled = true;
            document.getElementById('loading').style.display = 'block';
            document.getElementById('results').innerHTML = '';

            fetch('/api/run_optimizer', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    this.disabled = false;
                    document.getElementById('loading').style.display = 'none';

                    if (data.status === 'success') {
                        document.getElementById('results').innerHTML = `
                            <div class="result-box success">
                                <h2>Optimization Complete</h2>
                                <p>Status: ${data.metrics.solver_status || 'Unknown'}</p>
                                <p>Makespan: ${data.metrics.makespan || 0} minutes</p>
                                <p>Total Cost: ${data.metrics.total_cost || 0}</p>
                                <p><a href="/api/visualization/latest" target="_blank" class="btn">View Gantt Chart</a></p>
                            </div>`;
                    } else {
                        document.getElementById('results').innerHTML = `
                            <div class="result-box error">
                                <h2>Optimization Failed</h2>
                                <p>Error: ${data.message}</p>
                            </div>`;
                    }
                })
                .catch(error => {
                    this.disabled = false;
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('results').innerHTML = `
                        <div class="result-box error">
                            <h2>Error</h2>
                            <p>${error.message}</p>
                        </div>`;
                });
        });
    </script>
</body>
</html>
'''


def create_backend_script():
    """Create the backend Flask script"""
    with open('backend.py', 'w') as f:
        f.write(BACKEND_SCRIPT)
    print("Created backend.py")


def create_frontend():
    """Create the frontend HTML file"""
    static_dir = Path('static')
    static_dir.mkdir(exist_ok=True)

    with open(static_dir / 'index.html', 'w') as f:
        f.write(SIMPLE_HTML)
    print("Created frontend in static/index.html")


def check_files():
    """Check for required files and provide information"""
    root_dir = Path('.')
    profunct_path = root_dir / "ProFunctv2.7.py"
    plotly_path = root_dir / "Plotly2.py"
    new_jobs_path = root_dir / "new_jobs.csv"

    print("\nChecking for required files:")

    if profunct_path.exists():
        print(f"✅ Found optimizer script: {profunct_path}")
    else:
        print(f"❌ Missing optimizer script: {profunct_path}")
        print("   Please make sure ProFunctv2.7.py is in the current directory.")

    if plotly_path.exists():
        print(f"✅ Found visualization script: {plotly_path}")
    else:
        print(f"❌ Missing visualization script: {plotly_path}")
        print("   Please make sure Plotly2.py is in the current directory.")

    if new_jobs_path.exists():
        print(f"✅ Found input data: {new_jobs_path}")
    else:
        print(f"❓ Input data file new_jobs.csv not found in root directory.")
        print("   You'll need to provide this file before running the optimizer.")

    print("\nOther optional files:")
    optional_files = ["fixed_jobs.csv", "machine_capacity.csv", "setup_transitions.csv", "workcenters.csv"]
    for file in optional_files:
        if (root_dir / file).exists():
            print(f"✅ Found: {file}")
        else:
            print(f"  Missing: {file} (optional)")


def start_server():
    """Start the Flask server"""
    server_process = subprocess.Popen([sys.executable, 'backend.py'])
    print("Started backend server at http://localhost:5000")
    return server_process


def main():
    """Main function"""
    print("=== Production Scheduler Launcher ===")

    # Create the necessary files
    create_backend_script()
    create_frontend()

    # Check for required files
    check_files()

    # Start the backend server
    server_process = start_server()

    # Open browser
    time.sleep(1)  # Give the server a moment to start
    webbrowser.open('http://localhost:5000')

    print("\nProduction Scheduler is now running.")
    print("Press Ctrl+C to exit.")

    try:
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server_process.terminate()
        print("Server stopped.")
        print("Goodbye!")


if __name__ == "__main__":
    main()