from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import pipeliner.job_manager as job_manager
import json, click

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type="str",
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--refine-path",
    type=int,
    required=True,
    default="1",
    help="Best 3D Class for Sub-Sequent Refinement"
)
def run(
    parameter_path: str,
    refine_path: str, 

    ):

    # Define Rules For Classify Iteration:
    # (1) - Grab Last Iteration For Specified Binning Factor     

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file('sta_parameter.json')
    utils.read_json_directories_file('output_directories.json')

    # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
    utils.update_resolution(binFactor)

    # Reconstruct Particle at New Binning and Create mask From That Resolution
    utils.reconstruct_job.joboptions['in_particles'].value = utils.tomo_select_job.output_dir + 'particles.star'  
    utils.reconstruct_job.joboptions['fn_mask'].value = ''
    utils.run_reconstruct()    
    refine_reference = utils.reconstruct_job.output_dir + 'merged.mrc'

    # Create Mask for Reconstruction and Next Stages of Refinement
    utils.mask_create_job.joboptions['fn_in'].value = utils.reconstruct_job.output_dir + 'merged.mrc'
    utils.mask_create_job.joboptions['lowpass_filter'].value = utils.get_resolution(utils.tomo_refine3D_job, 'refine3D') * 1.25
    utils.run_mask_create()

    # Post-Process to Estimate Resolution     
    utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_job.output_dir + 'half1.mrc'
    utils.run_post_process()