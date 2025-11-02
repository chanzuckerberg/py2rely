from pipeliner.api.manage_project import PipelinerProject
import py2rely.routines.submit_slurm as my_slurm 
import pipeliner.job_manager as job_manager
import json, click, starfile, os, mrcfile
from py2rely.utils import relion5_tools

@click.group()
@click.pass_context
def cli(ctx):
    pass

# Post Process Command
@cli.command(context_settings={"show_default": True})
@click.option("--parameter", type=str, required=True, default="sta_parameters.json", 
              help="Sub-Tomogram Refinement Parameter Path")
@click.option('--mask', type=str, required=True, 
              help="Path to Mask to Measure the Map Resolution")
@click.option('--half-map', type=str, required=True, 
              help="Path to Half Map to Post Process")
@click.option('--low-pass', type=float, required=False, default=None, 
              help='Low Pass Filter to Use for Post Processing')
def post_process(
    parameter: str,
    mask: str,
    half_map: str,
    low_pass: float,
    ):
    """
    Post Process a Half Map through the CLI.
    """

    fresh_run(parameter, mask, half_map, low_pass)

def fresh_run( 
    parameter: str,
    mask: str,
    half_map: str,
    low_pass: float,
    ):
    """
    Post Process a Half Map from a fresh new run .
    """

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
    utils.read_json_directories_file('output_directories.json')

    # Initialize the Processes Job
    utils.initialize_post_process()

    # Update the Post Process Job with the Mask and Half Map
    utils.post_process_job.joboptions['fn_in'].value = half_map
    utils.post_process_job.joboptions['fn_mask'].value = mask

    if low_pass is not None:
        utils.post_process_job.joboptions['low_pass'].value = low_pass  

    # Run the Post Process Job
    utils.run_post_process(rerunPostProcess=True)

def run(utils, mask, half_map, low_pass):
    """
    Continue a Pipeline with a Post Process Job.
    """

    # Update the Post Process Job with the Mask and Half Map
    utils.post_process_job.joboptions['fn_in'].value = half_map
    utils.post_process_job.joboptions['fn_mask'].value = mask

    if low_pass is not None:
        utils.post_process_job.joboptions['low_pass'].value = low_pass  

    # Run the Post Process Job
    utils.run_post_process(rerunPostProcess=True)
    