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
        click.option("-param", "--parameter", type=str, required=False, default=None,
                      help="Py2rely Parameter file to determine the crop and box size at the requested resolution (e.g., 'sta_parameters.json')."),
        click.option("-p", "--particles", type=str,required=True, default='particles.star',
                      help="Path to Particles STAR File."),
        click.option("-bf", "--binfactor",type=int,required=False, default=1,
                      help="(Optional) Binning Factor, if not provided, will use the starting binning factor from the parameter pipeline file."),
        click.option("-t", "--tomogram",type=str,required=False, default=None,
                      help="(Optional) Path to Tomogram, if not provided, will use the tomograms from the parameter pipeline file."),
        click.option("-m", "--motion", type=str,required=False, default=None,
                      help="(Optional) Path to Motion Correction STAR File."),
        click.option("-bs", "--boxsize", type=int,required=False, default=None,
                      help="(Optional) Box Size, if not provided, will use the box size from the parameter pipeline file."),
        click.option("-cs", "--cropsize", type=int,required=False, default=None,
                      help="(Optional) Crop Size, if not provided, will use the crop size from the parameter pipeline file."),
        click.option("-apex", "--apex", type=bool, required=False, default=False,
                      help="Apply APEX Flags for extraction."),\
        click.option("-j", "--nthreads", type=int, required=False, default=8,
                      help="Number of threads to use for extraction."),
        click.option("-np", "--nprocesses", type=int, required=False, default=1,
                      help="Number of processes to use for extraction."),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  

@cli.command(context_settings=cli_context, no_args_is_help=True)
@extract_subtomo_options
def extract(
    parameter: str,
    particles: str,
    tomogram: str,
    binfactor: int,
    motion: str,
    boxsize: int,
    cropsize: int,
    apex: bool,
    nthreads: int,
    nprocesses: int,
    ): 
    """Extract pseudo sub-tomograms from tilt series"""

    run_extract_subtomo(
        particles, tomogram, binfactor,
        nthreads, nprocesses, motion, 
        boxsize, cropsize, 
        apex, parameter, 
    )  


def run_extract_subtomo(
    particles: str,
    tomogram: str,
    binfactor: int = 1,
    nthreads: int = 8,
    nprocesses: int = 1,
    motion: str = None,
    boxsize: int = None,
    cropsize: int = None,
    apex: bool = False,
    parameter: str = None,
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
    from pipeliner.jobs.tomography.relion_tomo import tomo_pseudosubtomo_job
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.utils import relion5_tools
    from py2rely.routines import helper

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.binning = binfactor
    utils.read_json_directories_file('output_directories.json')

    # Set Parameters
    parameters = {
        'in_particles': particles, 'in_tomograms': tomogram, 
        'in_trajectories': motion, 'do_float16': 'yes', 
        'do_output_2dstacks': 'yes', 'do_use_direct_entries': 'yes',
        'binfactor': binfactor, 'nr_threads': nthreads, 'nr_mpi': nprocesses}
    if parameter: 
        helper.compute_boxsize_from_project(parameter, utils)
    elif boxsize is None and cropsize is None: 
        raise ValueError("Either parameter, boxsize, or both (cropsize and boxsize) must be provided.")
    elif boxsize is not None and cropsize is None:
        utils.pseudo_subtomo_job = tomo_pseudosubtomo_job.RelionPseudoSubtomoJob()
        parameters['crop_size'] = boxsize
        parameters['box_size'] = boxsize 
    else: # boxsize and cropsize are provided
        utils.pseudo_subtomo_job = tomo_pseudosubtomo_job.RelionPseudoSubtomoJob()   
        parameters['crop_size'] = cropsize
        parameters['box_size'] = boxsize 

    # Set Parameters
    helper.set_parameters(utils.pseudo_subtomo_job, parameters)

    # Print Input Parameters
    helper.print_params('Pseudo Subtomo Extraction', params=parameters)

    # Remove CTF Pre-multiplication for Apex 
    if apex:
        utils.pseudo_subtomo_job.joboptions['other_args'].value = "--no_ctf --no_comb"

    # Run
    utils.run_pseudo_subtomo(rerunPseudoSubtomo=True)

    # Return the Output Directory for Apex
    return utils.pseudo_subtomo_job.output_dir

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
