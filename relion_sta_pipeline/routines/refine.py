import relion_sta_pipeline.routines.submit_slurm as my_slurm 
from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import pipeliner.job_manager as job_manager
import json, click, starfile

@click.group()
@click.pass_context
def cli(ctx):
    pass

def refine3d_options(func):
    """Decorator to add shared options for refine3d commands."""
    options = [
        click.option("--parameter-path",type=str,required=True,default="sta_parameters.json",
                      help="Sub-Tomogram Refinement Parameter Path",),
        click.option("--particles-path",type=str,required=True,default="Refine3D/job001/run_data.star",
                      help="Path to Particles File to Reconstruct Data"),
        click.option("--reference-path",type=str,required=True,default="Refine3D/job001/class001.mrc",
                      help="Path to Reference MRC for Refinement"),
        click.option("--mask-path",type=str,required=False,default=None,
                      help="(Optional) Path for Mask."),
        click.option("--low-pass",type=float,required=False,default=15,
                      help="User Input Low Pass Filter"),
        click.option("--ref-correct-greyscale",type=bool,required=False, default=True,
                      help="Reference Map is on Absolute Greyscale?"),
        click.option("--continue-iter",type=str,required=False,default=None,
                      help="(Optional) Continue from this iteration? (e.g., Refine3D/job009/run_it008_optimiser.star)"),
        click.option("--tomogram-path",type=str, required=False,default=None,
                      help="(Optional) Path to CtfRefine or Polish tomograms StarFile (e.g., CtfRefine/job010)" )
    ]  
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  

# Refine3D
@cli.command(context_settings={"show_default": True})
@refine3d_options
def refine3d(
    parameter_path: str,
    particles_path: str, 
    reference_path: str,
    mask_path: str = None,
    symmetry: str = None,
    low_pass: float = None,
    ref_correct_greyscale: bool = True,    
    continue_iter: str = None,
    tomogram_path: str = None
    ): 

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # If a Path for Refined Tomograms is Provided, Assign it  
    if tomogram_path is not None:
        utils.set_new_tomograms_star_file(tomogram_path)

    # Print Input Parameters
    utils.print_pipeline_parameters('Refine3D', Parameter_Path=parameter_path,Particles_Path=particles_path,
                                    Mask_path=mask_path, low_pass_filter=low_pass)    

    # Update the Resolution with Given Binning Factor
    particlesdata = starfile.read(particles_path)
    currentBinning = int(particlesdata['optics']['rlnTomoSubtomogramBinning'].values[0])
    binIndex = utils.binningList.index(currentBinning)    

    # Do I want to Scale My Classification Sampling Based on Resolution?
    utils.initialize_pseudo_tomos()
    utils.initialize_auto_refine()
    utils.update_resolution(binIndex)     

    # Primary 3D Refinement Job and Update Input Parameters
    utils.tomo_refine3D_job.joboptions['fn_img'].value = particles_path
    utils.tomo_refine3D_job.joboptions['fn_ref'].value = reference_path

    # If Mask Path is Not Provided, Query the Last Ran Mask
    if mask_path is not None: 
        utils.tomo_refine3D_job.joboptions['fn_mask'].value = mask_path
    # else:
    #     utils.initialize_mask_create()
    #     utils.tomo_refine3D_job.joboptions['fn_mask'].value = utils.mask_create_job.output_dir + 'mask.mrc' 

    # Is the Reference Map Created by Relion?
    utils.tomo_refine3D_job.joboptions['ref_correct_greyscale'].value = ref_correct_greyscale

    # If this is a continue job, specify the provided path. 
    if continue_iter is not None:
        utils.tomo_refine3D_job.joboptions['fn_cont'].value = continue_iter

    # Low Pass Filter
    utils.tomo_refine3D_job.joboptions['ini_high'].value = low_pass

    # Run 3D-Refinement
    utils.run_auto_refine(rerunRefine=True)

@cli.command(context_settings={"show_default": True})
@refine3d_options
@my_slurm.add_compute_options
def refine3d_slurm(
    parameter_path: str,
    particles_path: str, 
    reference_path: str,
    mask_path: str,
    low_pass: float,
    ref_correct_greyscale: bool,    
    continue_iter: str,
    tomogram_path: str,
    num_gpus: int,
    gpu_constraint: str
    ):

    # If Low Pass Filter is Negative, Take Absolute Value
    if low_pass < 0:
        low_pass = abs(low_pass)

    # Create Refine3D Command
    command = f"""
pyrelion routines refine3d \\
    --parameter-path {parameter_path} \\
    --particles-path {particles_path} \\
    --reference-path {reference_path} \\
    --low-pass {low_pass} --ref-correct-greyscale {ref_correct_greyscale} \\
    """

    if mask_path is not None:
        command += f" --mask-path {mask_path}"
    if tomogram_path is not None:
        command += f" --tomogram-path {tomogram_path}"
    if continue_iter is not None:
        command += f" --continue-iter {continue_iter}"

    # Create Slurm Submit Script
    my_slurm.create_shellsubmit(
        job_name="refine3d",
        output_file="refine3d.out",
        shell_name="refine3d.sh",
        command=command,
        num_gpus=num_gpus,
        gpu_constraint=gpu_constraint
    )