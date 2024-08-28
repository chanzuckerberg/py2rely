from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import pipeliner.job_manager as job_manager
import json, click, starfile, os

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type=str,
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--best-class",
    type=int,
    required=True,
    default="1",
    help="Best 3D Class for Sub-Sequent Refinement"
)
@click.option(
    "--keep-classes",
    type=str,
    required=True,
    help="List of Classes to Keep for Further Refinement",
)
@click.option(
    "--class-job",
    type=str,
    required=True,
    default="job001",
    help="Job that Classes will Be Extracted",
)
@click.option(
    "--run-refinement",
    type=bool,
    required=False,
    default=True,
    help="Run Another Refinement After Selecting Best Classes"
)
def select(
    parameter_path: str,
    best_class: int, 
    keep_classes: str,
    class_job: str, 
    run_refinement: bool,
    ):

    # Define Rules For Select Iteration:
    # (1) - New Iteration if Last Job is The Provided Class3D
    # (2) - Grab Last Iteration if Select is the Last Job 

    # Split the comma-separated string into a list of integers
    keep_classes = [int(x) for x in keep_classes.split(',')]

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # Print Input Parameters
    print(f'\n[Class Select] Parameters: \nParameter-Path: {parameter_path}\nClass-Path: Class3D/{class_job}\nBest-Class: {best_class}\nKeep-Classes: {keep_classes}\nRun-Refinement: {run_refinement}\n')

    # Custom Manual Selection with Pre-Defined Best Tomo Class for Subsequent Refinement 
    utils.initialize_selection()
    utils.initialize_tomo_class3D()
    utils.tomo_class3D_job.output_dir = f'Class3D/{class_job}/'      
    utils.tomo_select_job.joboptions['fn_data'].value = utils.find_final_iteration(utils.tomo_class3D_job)
    utils.tomo_select_job.joboptions['select_minval'].value = best_class
    utils.tomo_select_job.joboptions['select_maxval'].value = best_class
    utils.run_subset_select(keepClasses=keep_classes)

    # 3D Refinement Job and Update Input Parameters 
    if run_refinement:

        # Assign Best Class and Output Particle Selection for Sub-Sequent Job 
        utils.initialize_auto_refine()        
        utils.tomo_refine3D_job.joboptions['fn_img'].value = utils.tomo_select_job.output_dir + 'particles.star'
        utils.tomo_refine3D_job.joboptions['fn_ref'].value = utils.tomo_class3D_job.output_dir + f'run_it025_class{best_class:03d}.mrc'    
        utils.run_auto_refine(refineStep='post_class')


@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type=str,
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--export-classes",
    type=str,
    required=True,
    help="Best 3D Classes for Sub-Sequent Refinement"
)
@click.option(
    "--class-job",
    type=str,
    required=True,
    default="job001",
    help="Job that Classes will Be Extracted",
)
@click.option(
    "--export-path",
    type=str,
    required=True,
    help="Path to Export New Classes",
)
def export(
    parameter_path: str, 
    export_class: str,
    class_job: str,     
    export_path: str,
    ):

    # Split the comma-separated string into a list of integers
    keep_classes = [int(x) for x in keep_classes.split(',')]

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')    

    print(f'\n[Export Class] Exporting Classes {export_class} from Class3D/{class_job} to {export_path}\n')

    utils.custom_select()

    # TODO:

    return True