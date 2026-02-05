import py2rely.routines.submit_slurm as my_slurm 
from py2rely import cli_context
import rich_click as click

@click.group()
@click.pass_context
def cli(ctx):
    pass

def extract_subtomo_options(func):
    """Decorator to add shared options for extract-subtomo commands."""
    options = [
        click.option("-p", "--parameter",type=str,required=True,
                      help="Path to Pipeline Parameter JSON File."),
        click.option("--particles", type=str,required=True, default='particles.star',
                      help="Path to Particles STAR File."),
        click.option("-bf", "--binfactor",type=int,required=False, default=None,
                      help="(Optional) Binning Factor, if not provided, will use the starting binning factor from the parameter pipeline file."),
        click.option("-t", "--tomogram",type=str,required=False, default=None,
                      help="(Optional) Path to Tomogram, if not provided, will use the tomograms from the parameter pipeline file."),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  

@cli.command(context_settings=cli_context)
@extract_subtomo_options
def extract_subtomo(
    parameter: str,
    particles: str,
    tomogram: str,
    binfactor: int,
    ): 
    """Extract pseudo sub-tomograms from tilt series"""

    run_extract_subtomo(
        parameter, particles, tomogram, binfactor,
    )  


def run_extract_subtomo(
    parameter: str,
    particles: str,
    tomogram: str,
    binfactor: int = None,
    ):
    """Extract pseudo sub-tomograms from cryo-ET tomograms using RELION.
    
    This command extracts 3D sub-volumes (sub-tomograms) from full tomogram
    reconstructions at particle coordinates. It creates pseudo sub-tomograms
    that can be used for subsequent sub-tomogram averaging and classification
    workflows in RELION.
    
    Args:
        parameter: Path to the JSON file containing pipeline parameters. This file
                  specifies the tomogram locations, particle coordinates, and
                  extraction settings.
        tomogram: Optional path to a STAR file containing tomogram information.
                 If provided, overrides the tomogram paths in the parameter file.
                 Useful for using refined tomograms from CtfRefine or Polish jobs.
        binfactor: Optional binning factor for extraction. If not provided, uses
                  the starting binning factor specified in the parameter pipeline file.
                  Higher values result in smaller, faster-to-process sub-tomograms.
    """    
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.utils import relion5_tools

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
    utils.read_json_directories_file('output_directories.json')

    # If a Path for Refined Tomograms is Provided, Assign it 
    if tomogram is not None:
        utils.set_new_tomograms_star_file(tomogram)    

    # Get Binning
    if binfactor is not None:
        utils.binning = binfactor

    # Initialize Pseudo Subtomo Extraction
    utils.initialize_reconstruct_particle()    
    utils.initialize_pseudo_tomos()  

    # Print Input Parameters
    utils.print_pipeline_parameters('Pseudo Subtomo Extraction', Parameter=parameter, 
                                     Tomogram_Path=tomogram, Binning_Factor=binfactor,
                                     Particles=particles)    

    # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
    utils.update_job_binning_box_size(
        utils.reconstruct_particle_job, utils.pseudo_subtomo_job,
        binningFactor = binfactor
    )              

    utils.pseudo_subtomo_job.joboptions['in_particles'].value = particles

    # Run
    utils.run_pseudo_subtomo(rerunPseudoSubtomo=True)

@cli.command(context_settings=cli_context, name='extract-subtomo')
@extract_subtomo_options
def extract_subtomo_slurm(
    parameter: str,
    tomogram: str,
    binfactor: int,
    ):

    # Create Class3D Command
    command = f"""
py2rely routines extract-subtomo \\
    --parameter {parameter} \\
    """

    if tomogram is not None:
        command += f" --tomogram {tomogram}"

    if binfactor is not None:
        command += f" --binfactor {binfactor}"

    # Create Slurm Submit Script
    my_slurm.create_shellsubmit(
        job_name="extract-subtomo",
        output_file="extract-subtomo.out",
        shell_name="extract-subtomo.sh",
        command=command,
        num_gpus=0
    )