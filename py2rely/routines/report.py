from py2rely import cli_context
import rich_click as click

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings=cli_context)
@click.option(
    "-p","--parameter",
    type=str,
    required=True,
    default='sta_parameters.json',
    help="The Saved Parameter Path",
)
def box_sizes(
    parameter: str,
    ):
    """
    Report the binning factors and box sizes for the py2rely pipeline.
    
    Parameters:
        parameter (str): Path to the JSON file containing pipeline parameters.
    """   
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.utils import sta_tools

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = sta_tools.PipelineHelper(my_project, requireRelion=False)
    utils.read_json_params_file(parameter)  
