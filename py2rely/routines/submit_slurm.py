from py2rely.config import get_load_commands
from typing import Optional
import rich_click as click

def create_shellsubmit(
    job_name, 
    output_file,
    shell_name,
    command,
    total_time = '12:00:00',
    num_gpus = 1, gpu_constraint = None, 
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

    # Determine the SLURM directives for the GPU constraint.
    if num_gpus > 0 and gpu_constraint is not None:
        slurm_gpus = f'#SBATCH --partition=gpu\n#SBATCH --gpus={gpu_constraint}:{num_gpus}\n#SBATCH --ntasks={num_gpus+1}'
    elif num_gpus > 0 and gpu_constraint is None:
        slurm_gpus = f'#SBATCH --partition=gpu\n#SBATCH --gpus={num_gpus}\n#SBATCH --ntasks={num_gpus+1}'
    else:
        slurm_gpus = f'#SBATCH --partition=cpu'

    python_load, relion_load = get_load_commands(prompt_if_missing=True)

    shell_script_content = f"""#!/bin/bash

{slurm_gpus}
#SBATCH --nodes=1
#SBATCH --time={total_time}
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=8G
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
    """Validate the GPU constraint, entry for click callback."""
    return check_gpus(value)

import subprocess
import warnings
from typing import Optional, Tuple, List, Set


def _slurm_gpu_features(partition: str = "gpu") -> Set[str]:
    """
    Return the set of Slurm node feature flags available in the given partition.
    Uses `sinfo -o %f` which prints the feature string for nodes/partitions.
    """
    cmd = ["sinfo", "-p", partition, "-o", "%f", "-h"]
    out = subprocess.check_output(cmd, text=True)

    features: Set[str] = set()
    for line in out.splitlines():
        for feat in line.split(","):
            feat = feat.strip()
            if feat:
                features.add(feat)
    return features


def _parse_constraint(expr: str) -> Tuple[List[str], Optional[str]]:
    """
    Parse a constraint expression.
    - If it contains '|', treat that as the joiner (OR-style).
    - Else if it contains ',', treat that as the joiner.
    - Else single token.
    Returns (tokens, joiner) where joiner is '|' or ',' or None.
    """
    expr = (expr or "").strip()
    if not expr:
        return ([], None)

    if "|" in expr:
        joiner = "|"
        tokens = [t.strip() for t in expr.split("|")]
    elif "," in expr:
        joiner = ","
        tokens = [t.strip() for t in expr.split(",")]
    else:
        joiner = None
        tokens = [expr]

    # normalize: drop empties, preserve order, de-dupe while preserving order
    seen = set()
    cleaned = []
    for t in tokens:
        if not t:
            continue
        if t not in seen:
            seen.add(t)
            cleaned.append(t)

    return cleaned, joiner


def check_gpus(
    gpu_constraint: Optional[str],
    *,
    partition: str = "gpu",
    warn: bool = True,
) -> Optional[str]:
    """
    Validate / filter a GPU constraint expression against Slurm feature flags.

    Examples:
      - None                    -> None
      - "a100"                  -> "a100" (if valid)
      - "h100|a100|h200"        -> "h100|a100" (filters invalid)
      - "h100,a100,h200"        -> "h100,a100" (filters invalid)

    Behavior:
      - If at least one token is valid: returns filtered expression.
      - If zero tokens are valid: raises ValueError.
      - Warns (optional) about invalid tokens that were dropped.
    """
    # Ignore if no constraint is provided.
    if gpu_constraint is None:
        return None

    tokens, joiner = _parse_constraint(gpu_constraint)
    if not tokens:
        return None  # treat empty/whitespace like None

    available = _slurm_gpu_features(partition=partition)

    valid = [t for t in tokens if t in available]
    invalid = [t for t in tokens if t not in available]

    if invalid and warn:
        warnings.warn(
            f"\nIgnoring unknown GPU constraint(s): {invalid}.\n"
            f"Available feature flags include: {sorted(available)}",
            stacklevel=2,
        )

    if not valid:
        raise ValueError(
            f"\nNo valid GPU constraints found in '{gpu_constraint}'\n. "
            f"Available feature flags include: {sorted(available)}"
        )

    # Recompose with the same joiner style the user provided
    if joiner is None:
        return valid[0]  # single entry
    return joiner.join(valid)

