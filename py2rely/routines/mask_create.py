from py2rely import cli_context
import rich_click as click

@click.group()
@click.pass_context
def cli(ctx):
    pass

def auto_mask_create(utils, low_pass):
    """
    Iteratively increases `width_mask_edge` until the phase-randomised FSC warning disappears.
    """

    # Configure mask creation
    utils.mask_create_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'merged.mrc'
    ini_mask = utils.get_reconstruction_std(utils.reconstruct_particle_job.output_dir + 'merged.mrc', low_pass)
    utils.mask_create_job.joboptions['inimask_threshold'].value = ini_mask
    utils.mask_create_job.joboptions['lowpass_filter'].value = low_pass
    utils.mask_create_job.joboptions['extend_inimask'].value = 3
    utils.mask_create_job.joboptions['nr_threads'].value = 16

    # Iterate from 10 - > 50 with step of 10
    for width_edge in range(10, 50, 10):

        # Set the width_mask_edge and Run Mask Create
        utils.mask_create_job.joboptions['width_mask_edge'].value = width_edge
        utils.run_mask_create(utils.tomo_refine3D_job, None, False, rerunMaskCreate=True) 

        # Run post-process with the newly created mask
        utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'half1.mrc'
        utils.post_process_job.joboptions['fn_mask'].value = utils.mask_create_job.output_dir + 'mask.mrc'
        utils.post_process_job.joboptions['low_pass'].value = 0
        utils.run_post_process(rerunPostProcess=True)

        # Check if the warning is gone
        if not check_phase_randomised_fsc_warning(utils.post_process_job.output_dir + 'run.err'):
            print(f"Success at width_mask_edge={width_edge}")
            break

def check_phase_randomised_fsc_warning(filepath):
    warning_line = "WARNING: The phase-randomised FSC is larger than 0.10 at the estimated resolution!"
    with open(filepath, 'r') as f:
        for line in f:
            if warning_line in line.strip():
                return True  # Warning is present
    return False  # No warning found

def mask_options(func):
    """Decorator to add shared options for mask commands."""
    options = [
        click.option("-m","--map",type=str,required=True,default="Reconstruct/job001/half1.mrc",
                      help="Map to Create Mask From"),
        click.option("-thr","--threshold",type=str, required=False,default=0.1,
                      help="Threshold for the Mask"),
        click.option("-ext","--extend",type=int, required=False,default=3,
                      help="Extend the Mask"),
        click.option("-w", "--width", type=int, required=False,default=10,
                      help="Width of the Mask"),
        click.option("-lp","--low-pass", type=float, required=False,default=15,
                      help="Low-Pass Filter for the Mask (Angstrom)"),
        click.option("-j", "--nthreads", type=int, required=False,default=16,
                      help="Number of Threads to Use"),
    ]
    for option in reversed(options):
        func = option(func)
    return func


@cli.command(context_settings=cli_context, no_args_is_help=True)
@mask_options
def mask_create(
    map: str,
    threshold: str,
    extend: int,
    width: int,
    nthreads: int,
    low_pass: float,
    ):
    """Build a soft solvent mask from a reconstructed map.

    The map is first low-pass filtered, then thresholded into a binary core,
    dilated outward, and finally given a soft cosine-tapered edge. The resulting
    mask (``mask.mrc``) is used to suppress solvent noise during FSC-based
    post-processing of the corresponding half-maps.

    Tuning tips:
      - Lower --threshold to capture weaker density (a larger mask); raise it to
        tighten the mask around strong density.
      - Increase --extend / --width if post-processing reports a phase-randomised
        FSC warning, which indicates the soft edge is too sharp.
    """
    run_mask_create(map, threshold, extend, width, nthreads, low_pass)

def run_mask_create(map: str, threshold: str, extend: int, width: int, nthreads: int, low_pass: float):
    """Set up and run a MaskCreate job from scratch via the Pipeliner API.

    Initialises a new Pipeliner project, configures a RELION MaskCreate job with
    the supplied map and masking parameters, then executes it. Use this function
    when no existing pipeline context is available.

    Args:
        map: Path to the input MRC map the mask is built from (typically a
             half-map or reconstructed volume).
        threshold: Initial binarisation threshold applied to the low-pass
                   filtered map to define the mask core.
        extend: Number of voxels to dilate the binary core outward before the
                soft edge is added.
        width: Width (in voxels) of the soft cosine-tapered edge applied around
               the dilated core.
        nthreads: Number of CPU threads to use for the job.
        low_pass: Low-pass filter (Å) applied to the map prior to thresholding.
    """

    from pipeliner.api.manage_project import PipelinerProject
    from pipeliner.jobs.relion import maskcreate_job
    from py2rely.utils import relion5_tools
    from py2rely.routines import helper
    import mrcfile

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_directories_file('output_directories.json')
    utils.mask_create_job = maskcreate_job.RelionMaskCreate()

    # Set Required Parameters
    required_parameters = {
        'fn_in': map, 'inimask_threshold': threshold, 
        'width_mask_edge': width, 'lowpass_filter': low_pass, 
        'extend_inimask': extend,
        'nr_threads': nthreads,
    }
    helper.set_parameters(utils.mask_create_job, required_parameters)

    # Run Mask Create
    utils.run_mask_create(None, None, autoContour=False, rerunMaskCreate=True)