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
@click.option(
    "--reference-path",
    type=str,
    required=False,
    default=None,
    help="Path to Reference for Classification (Default is Refined Map from Refinement Job is Ignored)"
)
@click.option(
    "--mask-path",
    type=str,
    required=False,
    default=None,
    help="Path of Mask for Classification",
)
@click.option(
    "--tau-fudge",
    type=float,
    required=False,
    default=None,
    help="Tau Regularization Parameter for Classification"
)
@click.option(
    "--nr_classes",
    type=int,
    required=False,
    default=None,
    help="Number of Classes for Classificaiton"
)
def run(
    parameter_path: str,
    refine_path: str, 
    reference_path: str = None,
    mask_path: str = None, 
    tau_fudge: float = None,
    nr_classes: int = None,
    ):   

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file('sta_parameter.json')
    utils.read_json_directories_file('output_directories.json')

    # Print Input Parameters
    utils.print_pipeline_parameters(Parameter_Path=parameter_path, Refine_Path=refine_path,
                                    tau_fudge=tau_fudge, nr_classes=nr_classes)

    # Define Rules For Classify Iteration:
    # (1) - Grab Last Iteration For Specified Binning Factor  

    # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
    utils.update_resolution(binFactor+1)        

    # 3D Refinement Job and Update Input Parameters 
    utils.initialize_tomo_class3D()

    # I need to make sure I reference the correct pseudo_subtomo, and associated refinement parameters.
    utils.tomo_class3D_job.joboptions['tomograms_star'].value = utils.tomo_reconstruct_job.output_dir + 'tomograms.star'      
    utils.tomo_class3D_job.joboptions['fn_img'].value = os.path.join('Refine', refine_path, 'run_data.star')     
    
    # Apply Pre-Specified Reference If Provided
    if reference_path is None:  utils.tomo_class3D_job.joboptions['fn_ref'].value = os.path.join('Refine', refine_path, 'run_class001.mrc')
    else:                       utils.tomo_class3D_job.joboptions['fn_ref'].value = reference_path

    # Apply Mask, Tau-Fudge or Number of Classes If Provided
    if mask_path is not None:
        utils.tomo_class3D_job.joboptions['fn_mask'].value = mask_path

    if tau_fudge is not None:
        utils.tomo_class3D_job.joboptions['tau_fudge'].value = tau_fudge

    if nr_classes is not None:
        utils.tomo_class3D_job.joboptions['nr_classes'].value = nr_classes
    
    # Run
    utils.run_tomo_class3D(rerunClassify=True)