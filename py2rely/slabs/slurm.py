from py2rely.slabs.preprocess import parameters
from py2rely.routines import submit_slurm
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import json, click

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings={"show_default": True})
@click.option("--in-coords", type=str, required=True,   
              help="Input Coordinates File Path" )
@click.option( "--in-vols", type=str, required=False, default=None,
              help="Input Volumes File Path")
@click.option( "--out-dir", type=str, required=True, 
              help="Output Directory" )
@click.option( "--extract-shape", type=str, required=True, default="500 500 400",
              help="Extraction Shape for Particles Extraction (x y z) in Angstroms" )
@click.option( "--coords-scale", type=float, required=True,
              help="The scale factor that converts the input coordinates to Angstrom\n(Select 1 if Reading From Copick Format) or the voxel spacing of the tomogram that 3D template matching was run on" )
@click.option( "--voxel-spacing", type=float, required=False, default=5,
              help="Pixel size of tomograms to extract minislabs from in Angstrom" )
@click.option( "--pixel-size", type=float, required=False, default=1.54,
              help="Pixel size in Angstroms" )
@click.option( "--tomo-type", type=str, required=False, default=None,
              help="Tomogram Type if Extracting from Copick Project" )
@click.option( "--user-id", type=str, required=False, default=None,
              help="UserID for Copick Query" )
@click.option( "--particle-name", type=str, required=False, default=None,
              help="Particle Name for Copick Query" )
@click.option( "--session-id", type=str, required=False, default=None,
              help="SessionID for Copick Query" )
def submit_slabpick(
    in_coords: str,
    in_vols: str, 
    out_dir: str,
    extract_shape: str,
    coords_scale: float,
    voxel_spacing: float,
    pixel_size: float,
    tomo_type: str,
    user_id: str,
    particle_name: str,
    session_id: str
    ):
    """
    Create a Slurm Shell Script to Run Extract Minislabs

    Args:
        in_coords (str): The input coordinates file path
        in_vols (str): The input volumes file path
        out_dir (str): The output directory
        extract_shape (str): The extraction shape for particles extraction (x y z) in Angstroms
    """

    # Check to Make sure a Tomogram Algorithm is Specified if Extracting from Copick Project
    if tomo_type is None and in_coords.endswith(".json"):
        raise click.BadParameter("Tomogram Type (--tomo-type) is required when reading from a copick-config (*.json) file")

    make_minislabs_command = f"""
echo "################################################################################"
echo "Making Minislabs"
echo "################################################################################"
make_minislabs \\
    --in_coords={in_coords} \\
    --out_dir={out_dir}/stack \\
    --extract_shape {extract_shape} \\
    --coords_scale {coords_scale} --voxel_spacing {voxel_spacing} \\
    --col_name rlnMicrographName --make_stack
"""

    normalize_command = f"""
echo "################################################################################"
echo "Normalizing Particles Stack"
echo "################################################################################"    
normalize_stack \\
    --in_stack={out_dir}/stack/particles.mrcs \\
    --out_stack={out_dir}/stack/particles_relion.mrcs \\
    --apix {pixel_size}
"""

    # Collect optional commands into a list
    optional_commands = []

    if user_id is not None:
        optional_commands.append(f"--user_id {user_id}")

    if particle_name is not None:
        optional_commands.append(f"--particle_name {particle_name}")

    if session_id is not None:
        optional_commands.append(f"--session_id {session_id}")

    if in_vols is not None:
        optional_commands.append(f'--in_vol {in_vols}')   
    
    if tomo_type is not None:
        optional_commands.append(f'--tomo_type {tomo_type}')

    # Append optional commands to the last line, joined by spaces
    if optional_commands:
        make_minislabs_command = make_minislabs_command.rstrip() + " " + " ".join(optional_commands)      

    command = make_minislabs_command + "\n" + normalize_command

    create_shellsubmit(
        'minislab', 
        'minislab.out',
        'slabpick.sh',
        command,
        '18:00:00',
        num_gpus = 0,
        big_cpu_memory = True)      

###########################################################################################      

@cli.command(context_settings={"show_default": True})
@click.option( "--particle-diameter", type=float, required=False, default=300,
              help="Particle Diameter" )
@click.option( "--tau-fudge", type=float, required=False, default=2,
              help="Tau Fudge Factor" )
@click.option( "--num-classes", type=str, required=False, default='5',
              help="Number of Classes (Can Be Provided as a Single Value, or a Range (min,max,interval))" )
@click.option( "--highres-limit", type=float, required=False, default=-1,
              help="High Resolution Limit for Classification in Angstroms (-1 Means Use Nyquist Limit)" )
@click.option( "--class-algorithm",  required=False, default="2DEM",
             type=click.Choice(["2DEM", "VDAM"], case_sensitive=False),
              help="2D Classification Algorithm, choose either '2DEM' or 'VDAM'." )
@click.option( "--num-gpus", type=int, required=False, default=2,
              callback=submit_slurm.validate_num_gpus,
              help="Number of GPUs for Processing" )
@click.option( "--gpu-constraint", required=False, default="h100",
              type=click.Choice(["h200", "h100", "a100", "a6000"], case_sensitive=False),
              help="GPU Hardware to Reqest for Processing" )
@click.option( "--num-threads", type=int, required=False, default=16,
              help="Number of Threads to Use" )
@click.option( "--bootstrap-ntrials", type=int, required=False, default=0,
              help="Number of Trials to Run Bootstraping for SAD Method" )
def submit_class2d(
    particle_diameter: float,
    tau_fudge: float,
    num_classes: str,
    class_algorithm: str,
    highres_limit: float,
    num_gpus: int,
    gpu_constraint: str,
    num_threads: int,
    bootstrap_ntrials: int,
    ):
    """
    Create a Slurm Shell Script to Run Class2D

    Args:
        particle_diameter (float): The particle diameter in Angstroms
        tau_fudge (float): The tau fudge factor
        num_classes (str): The number of classes to use
        class_algorithm (str): The classification algorithm to use
        highres_limit (float): The high resolution limit in Angstroms
        num_gpus (int): The number of GPUs to use
        gpu_constraint (str): The GPU constraint
        num_threads (int): The number of threads to use
        bootstrap_ntrials (int): The number of bootstrap trials to run
    """

    # Determine number of iterations based on classification algorithm
    if class_algorithm == "2DEM":
        niters = 25
    elif class_algorithm == "VDAM":
        niters = 200

    num_classes = num_classes.split(',')
    if len(num_classes) == 1:
        num_classes = int(num_classes[0])
        print(f'\nGenerated Number of Classes:\nNclass = {num_classes}')
        num_classes_command = f"NUM_CLASSES={num_classes}"
    elif len(num_classes) == 3:
        class_min, class_max, class_step = map(int, num_classes)
        num_classes = list(range(class_min, class_max + 1, class_step))
        print(f'\nGenerated Number of Classes:\nNclass = {num_classes}')
        num_classes_command = f"""# Define num_classes values in an array
NUM_CLASSES_LIST=({" ".join(map(str, num_classes))})

# Get the num_classes value for this job
NUM_CLASSES=${{NUM_CLASSES_LIST[$SLURM_ARRAY_TASK_ID]}}"""
    else:
        raise click.BadParameter("Number of Classes must be provided as a single value or a range (min,max,interval)")

    if isinstance(num_classes, list) and len(num_classes) > 1:
        job_array_flag = f"#SBATCH --array=0-{len(num_classes)-1}"
    else:
        job_array_flag = ""
    
    class2d_command = f"""
{num_classes_command}

# Copy Particles Stack to the Current Working Directory
cp stack/particles_relion.mrcs .

py2rely slab class2d \\
    --particles stack/particles_relion.star \\
    --particle-diameter {particle_diameter} --highres-limit {highres_limit} \\
    --nr-classes $NUM_CLASSES --tau-fudge {tau_fudge} \\
    --class-algorithm {class_algorithm} --nr-iter {niters} --nr-threads {num_threads}
"""

    # if bootstrap_ntrials > 0:  bootstrap_flag = f'#SBATCH --array=0-{bootstrap_ntrials-1}'
    # else:                      bootstrap_flag = ""

    # Save Shell Script
    create_shellsubmit(
        'class2d', 
        'class2d.out',
        'class2d.sh',
        class2d_command,
        '18:00:00',
        num_gpus = num_gpus,
        gpu_constraint = gpu_constraint,
        load_relion = True,
        big_cpu_memory = False, 
        additional_commands = job_array_flag)

########################################################################################

@cli.command(context_settings={"show_default": True})
@click.option( "--shell-path", type=str, required=False, default='pipeline_class_average.sh',
              help="The Saved Parameter Path" )
@click.option( "--job-name", type=str, required=False, default="bootstrap_relion",
              help="Job Name Displayed by Slurm Scheduler" )
@click.option( "--output-file", type=str, required=False, default="bootstrap.out",
              help="Output Text File that Results" )
@click.option( "--num-gpus", type=int, required=False, default=1,
              callback=submit_slurm.validate_num_gpus,
              help="Number of GPUs for Processing" )
@click.option( "--gpu-constraint", required=False, default="h100",
              type=click.Choice(["h200", "h100", "a100", "a6000"], case_sensitive=False),
              help="GPU Hardware to Reqest for Processing" )
@click.option( "--min-class-job", type=int, required=False, default=1,
              help="The minimum class job number (starting point for bootstrapping)" )
@click.option( "--max-class-job", type=int, required=False, default=20,
              help="The maximum class job number (end point for bootstrapping)" )
def submit_classrank(
    shell_path: str,
    job_name: str,
    output_file: str,
    num_gpus: int,
    gpu_constraint: str,
    min_class_job: int,
    max_class_job: int
    ):

    class_rank_command = f"""
py2rely slab auto-class-ranker \\
    --parameters class_average_parameters.json \\
    --min-class-job {min_class_job} --max-class-job {max_class_job}
"""

    create_shellsubmit(
        'classrank', 
        'classrank.out',
        'classrank.sh',
        class_rank_command,
        '18:00:00',
        num_gpus = num_gpus,
        gpu_constraint = gpu_constraint,
        load_relion = True,
        big_cpu_memory = False)

def create_shellsubmit(
    job_name, 
    output_file,
    shell_name,
    command,
    total_time = '12:00:00',
    num_gpus = 1, 
        gpu_constraint = 'h100',
    load_relion = True,
    big_cpu_memory = False,
    additional_commands = ''):

    if num_gpus > 0:
        slurm_gpus = f'#SBATCH --ntasks=1\n#SBATCH --nodes=1\n#SBATCH --partition=gpu\n#SBATCH --gpus={gpu_constraint}:{num_gpus}'
    else:
        slurm_gpus = f'#SBATCH --partition=cpu'

    if big_cpu_memory:
        slurm_mem = f'#SBATCH --mem-per-cpu=196G'
    else:
        slurm_mem = f'#SBATCH --mem-per-cpu=16G'
        slurm_cpu = f'#SBATCH --cpus-per-task=8'

    if load_relion:
        load_relion_command = submit_slurm.get_load_relion_command()

    shell_script_content = f"""#!/bin/bash

{slurm_gpus}
#SBATCH --time={total_time}
{slurm_mem}
#SBATCH --job-name={job_name}
#SBATCH --output={output_file}
{additional_commands}

{load_relion_command}

ml anaconda 
conda activate /hpc/projects/group.czii/conda_environments/py2rely
{command}
"""

    with open(shell_name, 'w') as file:
        file.write(shell_script_content)

    print(f"\nShell script {shell_name} created successfully.\n")

if __name__ == "__main__":
    cli()
