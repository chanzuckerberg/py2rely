import py2rely.routines.submit_slurm as my_slurm 
from py2rely import cli_context
import click

@click.group()
@click.pass_context
def cli(ctx):
    pass

def refine3d_options(func):
    """Decorator to add shared options for refine3d commands."""
    options = [
        click.option("--parameter",type=str,required=True,default="sta_parameters.json",
                      help="Sub-Tomogram Refinement Parameter Path",),
        click.option("--particles",type=str,required=True,default="Refine3D/job001/run_data.star",
                      help="Path to Particles File to Reconstruct Data"),
        click.option("-r", "--reference",type=str,required=True,default="Refine3D/job001/class001.mrc",
                      help="Path to Reference MRC for Refinement"),
        click.option("-m", "--mask",type=str,required=False,default=None,
                      help="(Optional) Path for Mask."),
        click.option("-lp", "--low-pass",type=float,required=False,default=15,
                      help="User Input Low Pass Filter"),
        click.option("-rcg", "--ref-correct-greyscale",type=bool,required=False, default=True,
                      help="Reference Map is on Absolute Greyscale?"),
        click.option("--continue-iter",type=str,required=False,default=None,
                      help="(Optional) Continue from this iteration? (e.g., Refine3D/job009/run_it008_optimiser.star)"),
        click.option("--tomogram",type=str, required=False,default=None,
                      help="(Optional) Path to CtfRefine or Polish tomograms StarFile (e.g., CtfRefine/job010)" )
    ]  
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  

# Refine3D
@cli.command(context_settings=cli_context)
@refine3d_options
def refine3d(
    parameter: str,
    particles: str, 
    reference: str,
    mask: str = None,
    symmetry: str = None,
    low_pass: float = None,
    ref_correct_greyscale: bool = True,    
    continue_iter: str = None,
    tomogram: str = None
    ): 
    """3D Refinement from sub-tomograms."""

    run_refine3d(
        parameter, particles, reference, mask, 
        symmetry, low_pass, ref_correct_greyscale, 
        continue_iter, tomogram
    )


def run_refine3d(
    parameter: str,
    particles: str, 
    reference: str,
    mask: str = None,
    symmetry: str = None,
    low_pass: float = None,
    ref_correct_greyscale: bool = True,    
    continue_iter: str = None,
    tomogram: str = None
    ):
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.utils import relion5_tools
    import starfile

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
    utils.read_json_directories_file('output_directories.json')

    # If a Path for Refined Tomograms is Provided, Assign it  
    if tomogram is not None:
        utils.set_new_tomograms_starfile(tomogram)

    # Print Input Parameters
    utils.print_pipeline_parameters('Refine3D', Parameter=parameter,Particles=particles,
                                    Mask=mask, low_pass_filter=low_pass)    

    # Update the Resolution with Given Binning Factor
    particlesdata = starfile.read(particles)
    currentBinning = int(particlesdata['optics']['rlnTomoSubtomogramBinning'].values[0])
    binIndex = utils.binningList.index(currentBinning)    

    # Do I want to Scale My Classification Sampling Based on Resolution?
    utils.initialize_pseudo_tomos()
    utils.initialize_auto_refine()
    utils.update_resolution(binIndex)     

    # Primary 3D Refinement Job and Update Input Parameters
    utils.tomo_refine3D_job.joboptions['in_particles'].value = particles
    utils.tomo_refine3D_job.joboptions['fn_ref'].value = reference

    # If Mask Path is Not Provided, Query the Last Ran Mask
    if mask is not None: 
        utils.tomo_refine3D_job.joboptions['fn_mask'].value = mask
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

@cli.command(context_settings=cli_context, name='refine3d')
@refine3d_options
@my_slurm.add_compute_options
def refine3d_slurm(
    parameter: str,
    particles: str, 
    reference: str,
    mask: str,
    low_pass: float,
    ref_correct_greyscale: bool,    
    continue_iter: str,
    tomogram: str,
    num_gpus: int,
    gpu_constraint: str
    ):

    # If Low Pass Filter is Negative, Take Absolute Value
    if low_pass < 0:
        low_pass = abs(low_pass)

    # Create Refine3D Command
    command = f"""
py2rely routines refine3d \\
    --parameter {parameter} \\
    --particles {particles} \\
    --reference {reference} \\
    --low-pass {low_pass} --ref-correct-greyscale {ref_correct_greyscale} \\
    """

    if mask is not None:
        command += f" --mask {mask}"
    if tomogram is not None:
        command += f" --tomogram {tomogram}"
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