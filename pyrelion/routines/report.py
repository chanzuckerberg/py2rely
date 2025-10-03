from pipeliner.api.manage_project import PipelinerProject
from pyrelion.utils import sta_tools
import click

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter",
    type=str,
    required=True,
    default='sta_parameters.json',
    help="The Saved Parameter Path",
)
def box_sizes(
    parameter: str,
    ):
    """
    Report the binning factors and box sizes for the pyrelion pipeline.
    
    Parameters:
        parameter (str): Path to the JSON file containing pipeline parameters.
    """    

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = sta_tools.PipelineHelper(my_project, requireRelion=False)
    utils.read_json_params_file(parameter)  
