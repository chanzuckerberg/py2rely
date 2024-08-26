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
    "--best-class",
    type=int,
    required=True,
    default="1",
    help="Best 3D Class for Sub-Sequent Refinement"
)
@click.option(
    "--run-refinement",
    type=bool,
    required=False,
    default=True,
    help="Run Another Refinement After Selecting Best Classes"
)
def classes(
    parameter_path: str,
    best_class: int, 
    keep_classes: List[int],
    run_refinement: bool,
)

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file('sta_parameter.json')
    utils.read_json_directories_file('output_directories.json')

    # TODO: How Do I make sure I reach the correct binning factor? And Process the Data After? 

    # Print Input Parameters
    print(f'Pipeline Parameters: \nRun-Denovo: {run_denovo_generation}\nRun-Class-3D: {run_class3D}')

    # Custom Manual Selection with Pre-Defined Best Tomo Class for Subsequent Refinement 
    utils.initialize_selection()
    utils.tomo_select_job.joboptions['fn_data'].value = utils.find_final_iteration()
    utils.tomo_select_job.joboptions['select_minval'].value = bestTomoClass
    utils.tomo_select_job.joboptions['select_maxval'].value = bestTomoClass
    utils.run_subset_select(keepClasses=myKeepClasses)

    # 3D Refinement Job and Update Input Parameters 
    if run_refinement:
        utils.initialize_auto_refine()

        # I need to make sure I reference the correct pseudo_subtomo, and associated refinement parameters.
        utils.tomo_refine3D_job.joboptions['fn_img'].value = utils.pseudo_subtomo_job.output_dir + 'particles.star'
        
        # 
        utils.tomo_refine3D_job.joboptions['fn_ref'].value = utils.tomo_class3D_job.output_dir + f'run_it025_class{best_class:03d}.mrc'
        utils.run_auto_refine(refineStep='post_class')
