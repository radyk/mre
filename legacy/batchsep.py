import pandas as pd
import os


def extract_technology(machine_option):
    """Extract the technology prefix from a machine option."""
    if not machine_option or pd.isna(machine_option):
        return "Unknown"

    machine_option = str(machine_option).strip()

    # Check if the machine option contains a slash
    if '/' in machine_option:
        return machine_option.split('/')[0]

    # If there's a dash, extract the part before it (like CNC from CNC-1)
    if '-' in machine_option:
        return machine_option.split('-')[0]

    # If no separator, return the whole code
    return machine_option


def split_jobs_by_technology(input_file, output_dir='technology_groups'):
    """
    Split the jobs CSV file into separate files by technology group.

    Args:
        input_file: Path to the input CSV file
        output_dir: Directory to store the output files

    Returns:
        A dictionary mapping technology groups to output file paths
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Read the input CSV file
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} jobs from {input_file}")

    # Add a technology column
    df['Technology'] = df['MachineOptions'].apply(extract_technology)

    # Get unique technologies
    technologies = df['Technology'].unique()
    print(f"Found {len(technologies)} unique technology groups: {', '.join(technologies)}")

    # Create a dictionary to store output file paths
    output_files = {}
    tech_counts = {}

    # Split the data by technology
    for tech in technologies:
        tech_df = df[df['Technology'] == tech].drop(columns=['Technology'])
        tech_counts[tech] = len(tech_df)

        # Create output file path
        output_file = os.path.join(output_dir, f"new_jobs_{tech}.csv")

        # Save to CSV
        tech_df.to_csv(output_file, index=False)
        output_files[tech] = output_file

        print(f"Created {output_file} with {len(tech_df)} jobs")

    # Create a summary file
    summary_file = os.path.join(output_dir, "technology_summary.csv")
    summary_df = pd.DataFrame({
        'Technology': list(tech_counts.keys()),
        'JobCount': list(tech_counts.values()),
        'Percentage': [count / len(df) * 100 for count in tech_counts.values()]
    })
    summary_df = summary_df.sort_values('JobCount', ascending=False)
    summary_df.to_csv(summary_file, index=False)
    print(f"Created summary file: {summary_file}")

    return output_files


def analyze_technology_groups(input_file):
    """
    Analyze the technology groups in the input file without creating separate files.
    Useful for a quick analysis of a new dataset.

    Args:
        input_file: Path to the input CSV file
    """
    # Read the input CSV file
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} jobs from {input_file}")

    # Add a technology column
    df['Technology'] = df['MachineOptions'].apply(extract_technology)

    # Get unique technologies
    technologies = df['Technology'].unique()
    print(f"Found {len(technologies)} unique technology groups: {', '.join(technologies)}")

    # Count jobs by technology
    tech_counts = df['Technology'].value_counts()

    print("\nJobs by technology group:")
    for tech, count in tech_counts.items():
        percentage = count / len(df) * 100
        print(f"{tech}: {count} jobs ({percentage:.1f}%)")

    # Analyze job routing across technologies
    print("\nAnalyzing job routing across technologies...")

    # Group by JobNumber and count technologies per job
    job_techs = df.groupby('JobNumber')['Technology'].nunique()

    # Count how many jobs span multiple technologies
    multi_tech_jobs = job_techs[job_techs > 1]

    if len(multi_tech_jobs) > 0:
        print(
            f"{len(multi_tech_jobs)} jobs span multiple technology groups ({len(multi_tech_jobs) / job_techs.shape[0] * 100:.1f}%)")

        # List a few examples
        print("\nExamples of jobs spanning multiple technologies:")
        examples = 0
        for job in multi_tech_jobs.index[:5]:  # Show up to 5 examples
            techs = df[df['JobNumber'] == job]['Technology'].unique()
            print(f"{job}: {', '.join(techs)}")
            examples += 1

        if examples < len(multi_tech_jobs):
            print(f"...and {len(multi_tech_jobs) - examples} more")
    else:
        print("No jobs span multiple technology groups - perfect for independent scheduling!")


def create_batch_script(output_dir='technology_groups'):
    """
    Create a batch script to run the scheduler on each technology group.

    Args:
        output_dir: Directory containing the technology group files
    """
    batch_file = os.path.join(output_dir, "run_all_schedulers.bat")

    # Get all CSV files in the output directory
    csv_files = [f for f in os.listdir(output_dir) if f.startswith("new_jobs_") and f.endswith(".csv")]

    with open(batch_file, 'w') as f:
        f.write("@echo off\n")
        f.write("echo Starting scheduling for all technology groups...\n")
        f.write("echo.\n\n")

        for csv_file in csv_files:
            tech = csv_file.replace("new_jobs_", "").replace(".csv", "")
            f.write(f"echo Processing technology group: {tech}\n")
            f.write(
                f"python scheduler.py --input \"{os.path.join(output_dir, csv_file)}\" --output \"{os.path.join(output_dir, f'schedule_{tech}.csv')}\" --log \"{os.path.join(output_dir, f'log_{tech}.txt')}\"\n")
            f.write("if %ERRORLEVEL% NEQ 0 (\n")
            f.write(f"    echo Error processing {tech}\n")
            f.write("    pause\n")
            f.write(")\n")
            f.write("echo.\n\n")

        f.write("echo All technology groups processed.\n")
        f.write("pause\n")

    print(f"Created batch script: {batch_file}")


if __name__ == "__main__":
    # If you have modified the path to your input file, change it here
    input_file = "new_jobstg.csv"
    output_dir = "technology_groups"

    # First analyze the data
    print("Analyzing technology groups...")
    analyze_technology_groups(input_file)

    # Then split the data
    print("\nSplitting jobs by technology group...")
    output_files = split_jobs_by_technology(input_file, output_dir)

    # Create a batch script to run the scheduler on each group
    create_batch_script(output_dir)

    print("\nDone!")
    print("\nTo run independent scheduling for each technology group:")
    print(f"1. Navigate to the {output_dir} directory")
    print("2. Run run_all_schedulers.bat")
    print("   This will process each technology group independently")
    print("\nAlternatively, process each group manually with your scheduling tool.")