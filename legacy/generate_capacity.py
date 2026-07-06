import pandas as pd

# Params
machines = ["CNC-1", "Lathe-2", "Miller-3", "Drill-4", "Grinder-5", "Saw-6", "Press-7", "Lathe-8", "Mill-9", "Polish-10"]
horizon = 10000
shift_length = 480  # 8 hours
gap_length = 120    # 2 hours
cycle_length = shift_length + gap_length
shifts_per_machine = horizon // cycle_length

# Build capacity
capacity_data = []
for machine in machines:
    for shift in range(shifts_per_machine):
        start = shift * cycle_length
        end = start + shift_length
        if end <= horizon:
            capacity_data.append({
                'Machine': machine,
                'StartTime': start,
                'EndTime': end
            })

df_capacity = pd.DataFrame(capacity_data)
df_capacity.to_csv("machine_capacity.csv", index=False)
print(f"Generated machine_capacity.csv: {len(df_capacity)} slots")