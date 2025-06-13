from pipeliner.api.manage_project import PipelinerProject
import pyrelion.routines.submit_slurm as my_slurm 
import pipeliner.job_manager as job_manager
import json, click, starfile, os, mrcfile
from pyrelion.utils import relion5_tools

@click.group()
@click.pass_context
def cli(ctx):
    pass

def class3d_options(func):
    """Decorator to add shared options for class3d commands."""
    options = [
        click.option("--parameter",type=str,required=True,default="sta_parameters.json",
                      help="Sub-Tomogram Refinement Parameter Path",),
        click.option("--particles",type=str,required=True,
                      help="Path to Particles"),
        click.option("--reference",type=str,required=True,
                      help="Path to Reference for Classification"),
        click.option("--mask",type=str,required=False,default=None,
                      help="(Optional) Path of Mask for Classification"),
        click.option("--ini-high",type=float,required=False,default=None,
                      help="Low-Pass Filter to Apply to Model"),
        click.option("--tau-fudge",type=float,required=False,default=3,
                      help="Tau Regularization Parameter for Classification"),
        click.option( "--nr-classes", type=str, required=False, default='5',
                    help="Number of Classes (Can Be Provided as a Single Value, or a Range (min,max,interval))" ),
        click.option("--nr-iter",type=int,required=False,default=None,
                      help="Number of Iterations"),
        click.option("--ref-correct-greyscale",type=bool,required=False,default=True,
                      help="Reference Map is on Absolute Greyscale? As in, was the reference map created by Relion?"),
        click.option("--tomogram-path",type=str,required=False,default=None,
                      help="(Optional) Path to CtfRefine or Polish tomograms StarFile (e.g., CtfRefine/job010)"),
        click.option("--align-particles", type=bool, required=False, default=False,
                      help="(Optional) Align Particles to Reference, recommended to set as False if alignments already provided.")
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  

@cli.command(context_settings={"show_default": True})
@class3d_options
def class3d(
    parameter: str,
    particles: str, 
    reference: str,
    mask: str,     
    ini_high: float,
    tau_fudge: float,
    nr_classes: int,
    nr_iter: int,
    ref_correct_greyscale: bool,
    tomogram_path: str,
    align_particles: bool
    ):   

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
    utils.read_json_directories_file('output_directories.json')

    # If a Path for Refined Tomograms is Provided, Assign it 
    if tomogram_path is not None:
        utils.set_new_tomograms_star_file(tomogram_path)    

    # Get Binning
    particlesdata = starfile.read( particles )
    currentBinning = int(particlesdata['optics']['rlnTomoSubtomogramBinning'].values[0])
    binIndex = utils.binningList.index(currentBinning)    

    utils.initialize_pseudo_tomos()
    utils.initialize_reconstruct_particle()
    
    # Do I want to Scale My Classification Sampling Based on Resolution?
    utils.update_resolution(binIndex)    

    # 3D Refinement Job and Update Input Parameters 
    utils.initialize_tomo_class3D() 

    # Low Pass Filter If Provided
    if ini_high is not None:  utils.tomo_class3D_job.joboptions['ini_high'].value = ini_high
    else:                     ini_high = utils.tomo_class3D_job.joboptions['ini_high'].value   

    # Apply Mask, Tau-Fudge or Number of Classes If Provided
    if tau_fudge is not None:   utils.tomo_class3D_job.joboptions['tau_fudge'].value = tau_fudge
    else:                       tau_fudge = utils.tomo_class3D_job.joboptions['tau_fudge'].value

    if nr_classes is not None:  utils.tomo_class3D_job.joboptions['nr_classes'].value = nr_classes
    else:                       nr_classes = utils.tomo_class3D_job.joboptions['nr_classes'].value

    if nr_iter is not None:     utils.tomo_class3D_job.joboptions['nr_iter'].value = nr_iter
    else:                       nr_iter = utils.tomo_class3D_job.joboptions['nr_iter'].value    

    if mask_path is not None:   utils.tomo_class3D_job.joboptions['fn_mask'].value = mask_path
    
    # Is the Reference Map Created by Relion?
    utils.tomo_class3D_job.joboptions['ref_correct_greyscale'].value = ref_correct_greyscale

    # Align Particles to Reference? 
    if align_particles:
        utils.tomo_class3D_job.joboptions['dont_skip_align'].value = "yes"
        utils.tomo_class3D_job.joboptions['allow_coarser'].value = "yes"
        utils.tomo_class3D_job.joboptions['nr_iter'].value = 15
        utils.tomo_class3D_job.joboptions['use_gpu'].value = "yes"
        utils.tomo_class3D_job.joboptions['do_local_ang_searches'].value = "no"

    # Specify Particles and Reference MRC Volume
    utils.tomo_class3D_job.joboptions['fn_img'].value = particles
    utils.tomo_class3D_job.joboptions['fn_ref'].value = reference

    # Print Input Parameters
    utils.print_pipeline_parameters('Class 3D', Parameter=parameter, Reference=reference,
                                    Particles=particles, Mask=mask, tau_fudge=tau_fudge, 
                                    nr_classes=nr_classes, nr_iter=nr_iter, ini_high=ini_high)

    # Run
    utils.run_tomo_class3D(rerunClassify=True)

@cli.command(context_settings={"show_default": True}, name='class3d')
@class3d_options
def class3d_slurm(
    parameter: str, 
    particles: str, 
    reference: str, 
    mask: str, 
    ini_high: float, 
    tau_fudge: float, 
    nr_classes: int, 
    nr_iter: int, 
    ref_correct_greyscale: bool, 
    tomogram_path: str,
    align_particles: bool):

    # Determine Number of Classes Command
    num_classes_command, job_array_flag = determine_nr_classes_command(nr_classes)

    # Create Class3D Command
    command = f"""
{num_classes_command}

pyrelion routines class3d \\
    --parameter {parameter} \\
    --particles {particles} \\
    --reference {reference} \\
    --nr-classes $NUM_CLASSES \\
    --ref-correct-greyscale {ref_correct_greyscale} \\
    --tau-fudge {tau_fudge} \\
    """

    if tomogram_path is not None:
        command += f" --tomogram-path {tomogram_path}"

    if mask is not None:
        command += f" --mask {mask}"
    
    if ini_high is not None:
        command += f" --ini-high {ini_high}"

    if nr_iter is not None:
        command += f" --nr-iter {nr_iter}"

    if align_particles:
        command += f" --align-particles {align_particles}"
        num_gpus = 2
    else:
        num_gpus = 0
    gpu_type = 'a100'

    # Create Slurm Submit Script
    my_slurm.create_shellsubmit(
        job_name="class3d",
        output_file="class3d.out",
        shell_name="class3d.sh",
        command=command,
        num_gpus=num_gpus,
        gpu_constraint=gpu_type,
        additional_commands=job_array_flag
    )

def determine_nr_classes_command(nr_classes: str):
    num_classes = nr_classes.split(',')
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

    # Determine if Job Array Flag is Needed
    if isinstance(num_classes, list) and len(num_classes) > 1:
        job_array_flag = f"#SBATCH --array=0-{len(num_classes)-1}"
    else:
        job_array_flag = ""

    return num_classes_command, job_array_flag