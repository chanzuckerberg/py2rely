import py2rely.routines.submit_slurm as my_slurm 
from py2rely import cli_context
import rich_click as click

@click.group()
@click.pass_context
def cli(ctx):
    pass

def extract_subtomo_options(func):
    """Decorator to add shared options for extract-subtomo commands."""
    options = [
        click.option("-param", "--parameter", type=str, required=False, default=None,
                      help="Py2rely Parameter file to determine the crop and box size at the requested resolution (e.g., 'sta_parameters.json')."),
        click.option("-p", "--particles", type=str,required=True, default='particles.star',
                      help="Path to Particles STAR File."),
        click.option("-bf", "--binfactor",type=int,required=False, default=1,
                      help="Binning Factor, if not provided, will use the starting binning factor from the parameter pipeline file."),
        click.option("-t", "--tomogram",type=str,required=False, default=None,
                      help="Path to Tomogram, if not provided, will use the tomograms from the parameter pipeline file."),
        click.option("-m", "--motion", type=str,required=False, default=None,
                      help="Path to Motion Correction STAR File."),
        click.option("-bs", "--boxsize", type=int,required=False, default=None,
                      help="Box Size, if not provided, will use the box size from the parameter pipeline file."),
        click.option("-cs", "--cropsize", type=int,required=False, default=None,
                      help="Crop Size, if not provided, will use the crop size from the parameter pipeline file."),
        click.option("-apex", "--apex", type=bool, required=False, default=False,
                      help="Apply APEX Flags for extraction."),\
        click.option("-j", "--nthreads", type=int, required=False, default=8,
                      help="Number of threads to use for extraction."),
        click.option("-np", "--nprocesses", type=int, required=False, default=1,
                      help="Number of processes to use for extraction."),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  

@cli.command(context_settings=cli_context, no_args_is_help=True)
@extract_subtomo_options
def extract(
    parameter: str,
    particles: str,
    tomogram: str,
    binfactor: int,
    motion: str,
    boxsize: int,
    cropsize: int,
    apex: bool,
    nthreads: int,
    nprocesses: int,
    ): 
    """Extract pseudo sub-tomograms from tilt-series data.

    Box and crop sizes are read from a parameter file
    or supplied directly via --boxsize / --cropsize. Use --apex to disable
    CTF pre-multiplication for APEX-corrected data.
    """

    run_extract_subtomo(
        particles, tomogram, binfactor,
        nthreads, nprocesses, motion, 
        boxsize, cropsize, 
        apex, parameter, 
    )  


def run_extract_subtomo(
    particles: str,
    tomogram: str,
    binfactor: int = 1,
    nthreads: int = 8,
    nprocesses: int = 1,
    motion: str = None,
    boxsize: int = None,
    cropsize: int = None,
    apex: bool = False,
    parameter: str = None,
    ):
    """Extract pseudo sub-tomograms from cryo-ET tilt-series data using RELION.

    Cuts 3D boxes around particle coordinates from full tomogram reconstructions,
    producing pseudo sub-tomograms ready for classification or refinement.  Box
    and crop sizes are derived from a parameter file or passed explicitly; at
    least one of (parameter, boxsize) must be provided.

    Args:
        particles: Path to the RELION particles STAR file containing particle
                   coordinates and CTF information.
        tomogram: Optional STAR file of tomograms (e.g. from a CtfRefine or
                  Polish job).  Overrides tomogram paths from the parameter file.
        binfactor: Binning factor applied during extraction.  Higher values yield
                   smaller, faster sub-tomograms for initial rounds of refinement.
        nthreads: Number of CPU threads passed to RELION (--j).
        nprocesses: Number of MPI processes passed to RELION (--np).
        motion: Optional STAR file of per-tilt motion trajectories from a Polish
                job, used to apply beam-induced motion correction during extraction.
        boxsize: 3D box size in pixels for the extracted sub-tomograms.  If None,
                 derived from the parameter file.
        cropsize: Cropped (final) sub-tomogram size in pixels written to disk.
                  Must be ≤ boxsize.  If None, defaults to boxsize.
        apex: If True, disables CTF pre-multiplication (--no_ctf --no_comb) for
              data corrected with the APEX phase-plate algorithm.
        parameter: Path to a py2rely JSON parameter file.  When supplied, box and
                   crop sizes are computed automatically from the project settings.
    """
    from pipeliner.jobs.tomography.relion_tomo import tomo_pseudosubtomo_job
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.utils import relion5_tools
    from py2rely.routines import helper

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_directories_file('output_directories.json')
    utils.binning = binfactor

    # Set Parameters
    parameters = {
        'in_particles': particles, 'in_tomograms': tomogram, 
        'in_trajectories': motion, 'do_float16': 'yes', 
        'do_output_2dstacks': 'yes', 'do_use_direct_entries': 'yes',
        'binfactor': binfactor, 'nr_threads': nthreads, 'nr_mpi': nprocesses}
 
    # If parameter is provided, compute the boxsize from the parameter file
    if parameter: 
        helper.compute_boxsize_from_project(parameter, utils)
    # If boxsize and cropsize are not provided, raise an error
    elif boxsize is None and cropsize is None: 
        raise ValueError("Either parameter, boxsize, or both (cropsize and boxsize) must be provided.")
    # If boxsize and/or cropsize are provided, validate the sizes and set the parameters
    else: 
        utils.pseudo_subtomo_job = tomo_pseudosubtomo_job.RelionPseudoSubtomoJob()   
        boxsize, cropsize = helper.validate_crop_box_size(boxsize, cropsize)
        parameters['crop_size'] = cropsize
        parameters['box_size'] = boxsize 

    # Set Parameters
    helper.set_parameters(utils.pseudo_subtomo_job, parameters)

    # Print Input Parameters
    helper.print_params('Pseudo Subtomo Extraction', params=parameters)

    # Remove CTF Pre-multiplication for Apex 
    if apex:
        utils.pseudo_subtomo_job.joboptions['other_args'].value = "--no_ctf --no_comb"

    # Run
    utils.run_pseudo_subtomo(rerunPseudoSubtomo=True)

    # Return the Output Directory
    return utils.pseudo_subtomo_job.output_dir

@cli.command(context_settings=cli_context, name='extract-subtomo')
@extract_subtomo_options
def extract_subtomo_slurm(
    parameter: str,
    particles: str,
    tomogram: str,
    binfactor: int,
    motion: str,
    boxsize: int,
    cropsize: int,
    apex: bool,
    nthreads: int,
    nprocesses: int,
    ):

    command = my_slurm.build_command("py2rely routines extract", {
        "particles": particles,
        "binfactor": binfactor,
        "nthreads": nthreads,
        "nprocesses": nprocesses,
        "parameter": parameter,
        "tomogram": tomogram,
        "motion": motion,
        "boxsize": boxsize,
        "cropsize": cropsize,
        "apex": apex or None,
    })

    my_slurm.create_shellsubmit(
        job_name="extract-subtomo",
        output_file="extract-subtomo.out",
        shell_name="extract-subtomo.sh",
        command=command,
        num_gpus=0
    )
