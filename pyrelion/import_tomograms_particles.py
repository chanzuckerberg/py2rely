from pipeliner.api.manage_project import PipelinerProject
import pipeliner.job_manager as job_manager
import my_pipeline_helper
import click

@click.group()
@click.pass_context
def cli(ctx):
    pass

# Create the boilerplate JSON file with a default file path
@click.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type=str,
    required=True,
    default='class_average_parameters.json',
    help="The JSON File Containing the Pipeline Parameters",
)
def import_extract(
    parameter_path: str 
    ):

    relion4(parameter_path)

def relion4(parameter_path):

    utils = import_tomograms(parameter_path)

    # Initialize and Run Import Particles Job 
    utils.initialize_import_coordinates()
    utils.import_particles_job.joboptions['tomogram_star'].value = utils.import_tomo_job.output_dir + 'tomograms.star'
    utils.run_import_particles()

    # Initialize Class for Pseudo Sub-Tomogram and Run 
    utils.initialize_pseudo_tomos()
    utils.pseudo_subtomo_job.joboptions['in_tomograms'].value = utils.import_tomo_job.output_dir + 'tomograms.star'
    utils.pseudo_subtomo_job.joboptions['in_particles'].value = utils.import_particles_job.output_dir + 'particles.star'
    utils.run_pseudo_subtomo()

    return utils

def import_tomograms(parameter_path: str):

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = my_pipeline_helper.pipeliner_helper(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # Initialize and Run Import Tomogram Job 
    utils.initialize_import_tomograms()
    utils.run_import_tomograms()

    return utils 

if __name__ == "__main__":
    cli()