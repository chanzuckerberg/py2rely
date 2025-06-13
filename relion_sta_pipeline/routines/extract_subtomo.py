import relion_sta_pipeline.routines.submit_slurm as my_slurm 
from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import pipeliner.job_manager as job_manager
import json, click, starfile, os, mrcfile

@click.group()
@click.pass_context
def cli(ctx):
    pass

def extract_subtomo_options(func):
    """Decorator to add shared options for class3d commands."""
    options = [
        click.option("--parameter",type=str,required=True,
                      help="Path to Parameters"),
        click.option("--binfactor",type=int,required=False, default=None,
                      help="(Optional) Binning Factor, if not provided, will use the starting binning factor from the parameter pipeline file."),
        click.option("--tomogram-path",type=str,required=False, default=None,
                      help="(Optional) Path to Tomogram, if not provided, will use the tomograms from the parameter pipeline file."),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  

@cli.command(context_settings={"show_default": True})
@extract_subtomo_options
def extract_subtomo(
    parameter: str,
    tomogram_path: str,
    binfactor: int = None,
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
    if binfactor is not None:
        utils.binning = binfactor

    # Initialize Pseudo Subtomo Extraction
    utils.initialize_pseudo_tomos()  

    # Print Input Parameters
    utils.print_pipeline_parameters('Pseudo Subtomo Extraction', Parameter=parameter, 
                                     Tomogram_Path=tomogram_path, Binning_Factor=binfactor)                                

    # Run
    utils.run_pseudo_subtomo()

@cli.command(context_settings={"show_default": True}, name='extract-subtomo')
@extract_subtomo_options
def extract_subtomo_slurm(
    parameter: str,
    tomogram_path: str,
    binfactor: int,
    ):

    # Create Class3D Command
    command = f"""
pyrelion routines extract-subtomo \\
    --parameter {parameter} \\
    """

    if tomogram_path is not None:
        command += f" --tomogram-path {tomogram_path}"

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