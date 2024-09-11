from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import pipeliner.job_manager as job_manager
import json, click, starfile

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
    "--particles-path",
    type=int,
    required=True,
    default="Refine3D/job001/run_data.star",
    help="Path to Particles File to Reconstruct Data"
)
@click.option(
    "--bin-factor",
    type=int,
    required=False,
    default=1,
    help="Bin Factor to Determine At Which Resolution to Reconstruct Averaged Map"
)
@click.option(
    "--mask-path",
    type=int,
    required=False,
    default=None,
    help="Path for Unique Mask for Measuring the Map Resolution"
)
def run(
    parameter_path: str,
    particles_path: str, 
    bin_factor: int, 
    mask_path: str = None
    ): 

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file('sta_parameter.json')
    utils.read_json_directories_file('output_directories.json')

    # Print Input Parameters
    utils.print_pipeline_parameters('Reconstruct Particle', Parameter_Path=parameter_path,Refine_Path=refine_path)    

    # Define Rules For Classify Iteration:
    # (1) - Grab Last Iteration For Specified Binning Factor
    run_data = starfile.read(refine_path + 'run_data.star')
    myBinFactor = run_data['optics']['rlnTomoSubtomogramBinning']

    # TODO: Add Logic To Determine If These Scripts is a Rerun

    # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
    utils.update_resolution(binFactor)

    # Reconstruct Particle at New Binning and Create mask From That Resolution
    utils.reconstruct_job.joboptions['in_particles'].value = particles_path
    utils.reconstruct_job.joboptions['fn_mask'].value = ''
    utils.run_reconstruct(rerunReconstruct=True)    
    refine_reference = utils.reconstruct_job.output_dir + 'merged.mrc'

    # Create Mask for Reconstruction and Next Stages of Refinement
    if mask_path is None:
        utils.mask_create_job.joboptions['fn_in'].value = utils.reconstruct_job.output_dir + 'merged.mrc'
        utils.mask_create_job.joboptions['lowpass_filter'].value = utils.get_resolution(utils.tomo_refine3D_job, 'refine3D') * 1.25
        utils.run_mask_create(rerunMaskCreate=True)
    else:
        utils.post_process_job.joboptions['fn_mask'].value = mask_path

    # Post-Process to Estimate Resolution     
    utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_job.output_dir + 'half1.mrc'
    utils.run_post_process(rerunPostProcess=True)