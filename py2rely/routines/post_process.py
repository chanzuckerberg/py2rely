from py2rely import cli_context
import rich_click as click

@click.group()
@click.pass_context
def cli(ctx):
    pass

# Post Process Command
@cli.command(context_settings=cli_context, no_args_is_help=True)
@click.option("-hm", "--half-map", type=str, required=True, 
              help="Path to Half Map to Post Process")
@click.option("-m", "--mask", type=str, required=True, 
              help="Path to Mask to Measure the Map Resolution")
@click.option("-lp", "--low-pass", type=float, required=False, default=None, 
              help='Low Pass Filter to Use for Post Processing')
def post_process(
    mask: str,
    half_map: str,
    low_pass: float,
    ):
    """Apply FSC-based post-processing to a pair of half-maps.

    The --half-map path should point to the first half-map (*half1*); RELION automatically
    locates the matching second half-map alongside it.
    """

    fresh_run(mask, half_map, low_pass)

def fresh_run( 
    mask: str,
    half_map: str,
    low_pass: float,
    ):
    """Set up and run a PostProcess job from scratch via the Pipeliner API.

    Initialises a new Pipeliner project, configures the PostProcess job with
    the supplied half-map and mask, then executes it.  Use this function when
    no existing pipeline context is available.

    Args:
        mask: Path to the soft-mask MRC used to compute the FSC and suppress
              solvent noise during B-factor estimation.
        half_map: Path to the first half-map MRC (*half1*).  RELION resolves
                  the second half-map from the same directory automatically.
        low_pass: Optional low-pass filter (Å) applied to the sharpened map.
                  If None, RELION applies automatic B-factor sharpening only.
    """
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.utils import relion5_tools

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
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
    """Attach and run a PostProcess job inside an existing Pipeliner pipeline.

    Unlike ``fresh_run``, this function expects a ``utils`` object with the
    PostProcess job already initialised (e.g. via ``utils.initialize_post_process``),
    allowing it to be chained after upstream jobs such as Refine3D or Class3D.

    Args:
        utils: Relion5Pipeline instance with an active Pipeliner project.
        mask: Path to the soft-mask MRC for FSC computation.
        half_map: Path to the first half-map MRC (*half1*).
        low_pass: Optional low-pass filter (Å).  If None, only automatic
                  B-factor sharpening is applied.
    """

    # Update the Post Process Job with the Mask and Half Map
    utils.post_process_job.joboptions['fn_in'].value = half_map
    utils.post_process_job.joboptions['fn_mask'].value = mask

    if low_pass is not None:
        utils.post_process_job.joboptions['low_pass'].value = low_pass  

    # Run the Post Process Job
    utils.run_post_process(rerunPostProcess=True)
    