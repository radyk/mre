
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
        for line in result.stdout.split("\n"):
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
