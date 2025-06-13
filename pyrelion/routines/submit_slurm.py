import click

def create_shellsubmit(
    job_name, 
    output_file,
    shell_name,
    command,
    total_time = '12:00:00',
    num_gpus = 1, 
    gpu_constraint = 'h100', 
    additional_commands = ''):

    # Convert GPU constraint to lowercase
    available_gpus = {'H200': 'h200', 'H100': 'h100', 'A100': 'a100', 'A6000': 'a6000'}
    all_gpus = ['h200', 'h100', 'a100', 'a6000', 'H200', 'H100', 'A100', 'A6000']
    if gpu_constraint in available_gpus:
        gpu_constraint = available_gpus[gpu_constraint]
    elif gpu_constraint not in all_gpus:
        raise ValueError(f"Invalid GPU constraint: {gpu_constraint}. Available constraints are: {all_gpus}")

    if num_gpus > 0 and gpu_constraint is not None:
        slurm_gpus = f'#SBATCH --partition=gpu\n#SBATCH --gpus={gpu_constraint}:{num_gpus}\n#SBATCH --ntasks={num_gpus+1}'
    elif num_gpus > 0 and gpu_constraint is None:
        gpu_constraint = 'a100'
        print('Setting GPU constraint to default of A100')
        slurm_gpus = f'#SBATCH --partition=gpu\n#SBATCH --gpus={gpu_constraint}:{num_gpus}\n#SBATCH --ntasks={num_gpus+1}'
    else:
        slurm_gpus = f'#SBATCH --partition=cpu'

    
    # {log_compute_utilization()}
    shell_script_content = f"""#!/bin/bash

{slurm_gpus}
#SBATCH --time={total_time}
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=16G
#SBATCH --job-name={job_name}
#SBATCH --output={output_file}
{additional_commands}

# Read the GPU names into an array
IFS=$'\\n' read -r -d '' -a gpu_names <<< "$(nvidia-smi --query-gpu=name --format=csv,noheader)"

# Access the first GPU name
first_gpu_name="${{gpu_names[0]}}"

# Figure Out which Relion Module to Load
echo "Detected GPU: $first_gpu_name"
if [ "$first_gpu_name" = "NVIDIA A100-SXM4-80GB" ]; then
    echo "Loading relion/CU80"
    module load relion/ver5.0-12cf15de-CU80    
elif [ "$first_gpu_name" = "NVIDIA A100-SXM4-40GB" ]; then
    echo "Loading relion/CU80"
    module load relion/ver5.0-12cf15de-CU80
elif [ "$first_gpu_name" = "NVIDIA RTX A6000" ]; then
    echo "Loading relion/CU86"
    module load relion/ver5.0-12cf15de-CU86
else
    echo "Loading relion/CU90"
    module load relion/ver5.0-12cf15de-CU90 
fi

ml anaconda 
conda activate /hpc/projects/group.czii/conda_environments/pyRelion
{command}

"""
# {complete_log_compute_utilization()}

    with open(shell_name, 'w') as file:
        file.write(shell_script_content)

    print(f"\nShell script {shell_name} created successfully.\n")

def validate_even_gpus(ctx, param, value):
    if value % 2 != 0:
        raise click.BadParameter(f"{value} is not an invalid input. Please specify an even number of GPUs.")
    return value

def parse_int_list(ctx, param, value):
    """Parse a comma-separated string into a list of integers."""
    try:
        # Remove brackets if included in the input
        value = value.strip("[]")
        # Split the string and convert to integers
        return [int(x.strip()) for x in value.split(",")]
    except ValueError:
        raise click.BadParameter("Binning list must be a comma-separated list of integers, e.g., '4,2,1'.")

def add_compute_options(func):
    """Decorator to add common compute options to a Click command."""
    options = [
        click.option("--num-gpus",type=int,required=False,default=2,
                    help="Number of GPUs to Use for Refinement",
                    callback=validate_even_gpus),
        click.option("--gpu-constraint",required=False,default="h100",
                    help="GPU Constraint for Slurm Job",
                    type=click.Choice(["h200", "h100", "a100", "a6000"], case_sensitive=False))
    ]
    for option in reversed(options):  # Add options in reverse order to preserve correct order
        func = option(func)
    return func

def log_compute_utilization():

    command = f"""# Set up logging file
LOGFILE="relion_utilization.log"
echo "Timestamp, CPU Usage (%), Memory Usage (MB), GPU Utilization (%), GPU Memory Usage (MB)" > $LOGFILE

# Start resource monitoring in the background
{{
    while true; do
        TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

        # CPU Usage (already averaged across all cores)
        CPU_USAGE=$(mpstat 1 1 | awk '/Average:/ {{print 100 - $NF}}')
        
        # Memory Usage (total system memory used)
        MEM_USAGE=$(free -m | awk '/Mem:/ {{print $3}}')

        # Get GPU Utilization and GPU Memory Usage (report averages instead of sum)
        GPU_STATS=$(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits | awk -F ', ' '{{g_util+=$1; g_mem+=$2; count+=1}} END {{print g_util/count", "g_mem/count}}')

        # Ensure that if no GPU data is returned, default to 0 values
        if [[ -z "$GPU_STATS" ]]; then
            GPU_STATS="0, 0"
        fi

        # Write to log file
        echo "$TIMESTAMP, $CPU_USAGE, $MEM_USAGE, $GPU_STATS" >> $LOGFILE
        
        sleep 60  # Wait (in seconds)
    done
}} &  # Run in the background
"""

    return command

def complete_log_compute_utilization():
    return """# Stop logging after job completion
pkill -P $$  # Kills the background logging process
"""