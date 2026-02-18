import rich_click as click

def get_load_relion_command():
    load_relion_command = """
# Read the GPU names into an array
IFS=$'\\n' read -r -d '' -a gpu_names <<< "$(nvidia-smi --query-gpu=name --format=csv,noheader)"

# Access the first GPU name
first_gpu_name="${gpu_names[0]}"

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
fi"""

    return load_relion_command

def create_shellsubmit(
    job_name, 
    output_file,
    shell_name,
    command,
    total_time = '12:00:00',
    num_gpus = 1, 
    gpu_constraint = 'h100', 
    additional_commands = ''):

    # Validate GPU constraint and set SLURM directives
    gpu_constraint = check_gpus(gpu_constraint)

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
#SBATCH --nodes=1
#SBATCH --time={total_time}
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=16G
#SBATCH --job-name={job_name}
#SBATCH --output={output_file}
{additional_commands}

ml anaconda 
conda activate /hpc/projects/group.czii/conda_environments/pyrely

{get_load_relion_command()}

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
        click.option("-ng", "--num-gpus",type=int,required=False,default=4,
                    help="Number of GPUs to Use for Processing",
                    callback=validate_even_gpus),
        click.option("-gc", "--gpu-constraint",required=False,default="h100",
                    help="GPU Constraint for Slurm Job",
                    callback=validate_gpu_constraint)
    ]
    for option in reversed(options):  # Add options in reverse order to preserve correct order
        func = option(func)
    return func

def validate_gpu_constraint(ctx, param, value):
    return check_gpus(value)

def check_gpus(gpu_constraint):
    import subprocess
    cmd = [
        "sinfo",
        "-p", "gpu",
        "-o", "%f",
        "-h",
    ]
    out = subprocess.check_output(cmd, text=True)
    features = set()
    for line in out.splitlines():
        for feat in line.split(","):
            feat = feat.strip()
            if feat:
                features.add(feat)

    if gpu_constraint not in features:
        raise ValueError(f"GPU constraint '{gpu_constraint}' not found in available options: {features}")

    return gpu_constraint
