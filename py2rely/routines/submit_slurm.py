from typing import Optional

import rich_click as click

from py2rely.config import get_load_commands

def get_env_setup_script(prompt_if_missing: bool = True, include_relion: bool = True) -> str:
    """
    Build env setup block from saved config (python_load, relion_load).
    Prompts and creates envs/ if missing. Empty values are omitted (no line).
    """
    python_load, relion_load = get_load_commands(prompt_if_missing=prompt_if_missing)
    lines = []
    if python_load:
        lines.append(python_load)
    if include_relion:
        lines.append(relion_load)
    return "\n".join(lines) if lines else ""


def create_shellsubmit(
    job_name, 
    output_file,
    shell_name,
    command,
    total_time = '12:00:00',
    num_gpus = 1, 
    gpu_constraint = 'h100', 
    additional_commands = ''):
    """
    Create a shell script to submit a SLURM job.
    Args:
        job_name: The name of the job.
        output_file: The output file for the job.
        shell_name: The name of the shell script to create.
        command: The command to run in the job.
        total_time: The total time for the job.
        num_gpus: The number of GPUs to use for the job.
        gpu_constraint: The GPU constraint for the job.
        additional_commands: Additional commands to add to the shell script.
    """

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

    python_load, relion_load = get_load_commands(prompt_if_missing=True)
    
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
{python_load}

{relion_load}
{command}
"""

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
    try:
        out = subprocess.check_output(cmd, text=True)
        features = set()
        for line in out.splitlines():
            for feat in line.split(","):
                feat = feat.strip()
                if feat:
                    features.add(feat)

        if gpu_constraint not in features:
            raise ValueError(f"GPU constraint '{gpu_constraint}' not found in available options: {features}")

    except Exception as e:
        print(f"Warning: Invalid GPU constraint. Using default of h100. Error: {e}")
        return 'h100'

    return gpu_constraint
