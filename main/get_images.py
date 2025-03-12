import os
import time
import subprocess

# Define the working directory
working_directory = r"D:\MusicProject"

# Number of times to run the command
num_runs = 200

for i in range(num_runs):
    print(f"Running iteration {i+1}/{num_runs} in {working_directory}...")
    
    # Run the command in the specified directory
    subprocess.run("flask images update-all --limit 1000 --batch-size 100 --delay 0.2", 
                   shell=True, cwd=working_directory)
    
    time.sleep(0.2)  # Optional delay
