from pipeliner.api.manage_project import PipelinerProject
import pyrelion.routines.submit_slurm as my_slurm 
from pyrelion.utils import relion5_tools
import click, starfile, os

@click.group()
@click.pass_context
def cli(ctx):
    pass

def select_options(func):
    """Decorator to add shared options for select commands."""
    options = [
        click.option("--parameter",type=str,required=True,default='sta_parameters.json',
                    help="The Saved Parameter Path"),
        click.option("--best-class",type=int,required=True,default="1",
                    help="Best 3D Class for Sub-Sequent Refinement"),
        click.option("--keep-classes",type=str,required=True,
                    help="List of Classes to Keep for Further Refinement"),
        click.option("--class-job",type=str,required=True,default="job001",
                    help="Job that Classes will Be Extracted"),
        click.option("--run-refinement",type=click.BOOL,required=False,default=True,
                    help="Run 3D-Refinement After Selecting Best Classes"),
        click.option("--mask-path", type=str,required=False,default=None,
                    help="(Optional) Path to Mask for 3D-Refinement")
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func

@cli.command(context_settings={"show_default": True})
@select_options
def select(
    parameter: str,
    best_class: int, 
    keep_classes: str,
    class_job: str, 
    run_refinement: bool,
    mask_path: str
    ):
    
    # Split the comma-separated string into a list of integers
    keep_classes = [int(x) for x in keep_classes.split(',')]

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
    utils.read_json_directories_file('output_directories.json')

    # Print Input Parameters
    utils.print_pipeline_parameters('Class Select', Parameter=parameter, Class_Path=f'Class3D/{class_job}',
                                    Best_Class=best_class, Keep_Classes=keep_classes, Run_Refinement=run_refinement, 
                                    Mask_path=mask_path)

    # Get Binning
    particlesdata = starfile.read( os.path.join('Class3D', class_job, 'run_it001_data.star') )
    currentBinning = int(particlesdata['optics']['rlnTomoSubtomogramBinning'].values[0])
    binIndex = utils.binningList.index(currentBinning)

    utils.initialize_pseudo_tomos()
    utils.initialize_reconstruct_particle()
    utils.initialize_auto_refine()       
    utils.update_resolution(binIndex)

    # Custom Manual Selection with Pre-Defined Best Tomo Class for Subsequent Refinement 
    utils.initialize_selection()
    utils.initialize_tomo_class3D()

    utils.tomo_class3D_job.output_dir = f'Class3D/{class_job}/'      
    utils.tomo_select_job.joboptions['fn_data'].value = utils.find_final_iteration()
    utils.tomo_select_job.joboptions['select_minval'].value = best_class
    utils.tomo_select_job.joboptions['select_maxval'].value = best_class
    utils.run_subset_select(keepClasses=keep_classes, rerunSelect = True)

    print('[Class Select] Particles Saved to: ', utils.tomo_select_job.output_dir + 'particles.star')

    # 3D Refinement Job and Update Input Parameters 
    if run_refinement:

        # Assign Best Class and Output Particle Selection for Sub-Sequent Job      
        utils.tomo_refine3D_job.joboptions['fn_img'].value = utils.tomo_select_job.output_dir + 'particles.star'
        utils.tomo_refine3D_job.joboptions['fn_ref'].value = utils.tomo_class3D_job.output_dir + f'run_it025_class{best_class:03d}.mrc'    
        
        # Estimate Resolution for Low-Pass Filtering
        models = starfile.read(utils.tomo_select_job.joboptions['fn_data'].value[:-9] + 'model.star')
        utils.tomo_refine3D_job.joboptions['ini_high'].value = round(models['model_classes']['rlnEstimatedResolution'].min() * 1.5, 2)

        if mask_path is not None:   utils.tomo_refine3D_job.joboptions['fn_mask'].value = mask_path

        # Run Refinement Job
        rerunBool = utils.check_if_job_already_completed( utils.post_process_job, 'refine3D')
        utils.run_auto_refine(rerunRefine=True)


@cli.command(context_settings={"show_default": True}, name='select')
@select_options
@my_slurm.add_compute_options
def select_slurm(
    parameter: str,
    best_class: int, 
    keep_classes: str,
    class_job: str, 
    run_refinement: bool,
    mask_path: str,
    num_gpus: int,
    gpu_constraint: str
    ):

    # Create Refine3D Command
    command = f"""
pyrelion routines select \\
    --parameter {parameter} \\
    --class-job {class_job} \\
    --best-class {best_class} --keep-classes {keep_classes} \\
    --run-refinement {run_refinement} \\
    """

    if mask_path is not None:
        command += f" --mask-path {mask_path}"

    # Create Slurm Submit Script
    my_slurm.create_shellsubmit(
        job_name="select",
        output_file="select.out",
        shell_name="select_classes.sh",
        command=command,
        num_gpus=num_gpus,
        gpu_constraint=gpu_constraint
    )


# TODO: Allow Users to Assign the Best Iteration For Main Pipeline Path
#click.option(
# "--job-path",
# type=str
# required=True,
# help=
# )
# def best_job(

#     ):