def create_shellsubmit(
    job_name, 
    output_file,
    shell_name,
    command,
    num_gpus = 1, 
    gpu_constraint = 'H100'):

    if num_gpus > 0:
        slurm_gpus = f'#SBATCH --partition=gpu\n#SBATCH --gpus={num_gpus}\n#SBATCH --constraint="{gpu_constraint}"'
    else:
        slurm_gpus = f'#SBATCH --partition=cpu'

    shell_script_content = f"""#!/bin/bash

{slurm_gpus}
#SBATCH --time=18:00:00
#SBATCH --cpus-per-task=24
#SBATCH --mem-per-cpu=16G
#SBATCH --job-name={job_name}
#SBATCH --output={output_file}

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
