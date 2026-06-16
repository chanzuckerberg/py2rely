from py2rely import cli_context
import rich_click as click

@click.group()
@click.pass_context
def cli(ctx):
    pass

def add_recon_options(func):
    options = [
        click.option("-param", "--parameter", type=str, required=False, default=None,
                     help="Py2rely Parameter file to determine the crop and box size at the requested resolution (e.g., 'sta_parameters.json')."),
        click.option("-p", "--particles", type=str, required=True, default='path/to/particles.star', 
                     help="Path to Particles File to Reconstruct Data (e.g., Refine3D/job001/run_data.star)"),
        click.option("-t", "--tomograms", type=str, required=False, default=None, 
                     help="Path to CtfRefine or Polish tomograms StarFile (e.g., CtfRefine/job010)"),
        click.option("-m", "--motion", type=str, required=False, default=None, 
                     help="Path to Motion Correction StarFile (e.g., MotionCor2/job001/run_data.star)"),
        click.option("-bf", "--binfactor", type=int, required=False, default=1, 
                     help="Bin Factor to Determine At Which Resolution to Reconstruct Averaged Map"),
        click.option("-bs", "--boxsize", type=int, required=False, default=256,
                     help="Box Size to Reconstruct Data (default: 256)"),
        click.option("-cs", "--cropsize", type=int, required=False, default=256,
                     help="Crop Size to Reconstruct Data (default: 256)"),
        click.option("-sym", "--symmetry", type=str, required=False, default='C1',
                     help="Symmetry of the Reconstruction (default: C1)"),
        click.option("-j", "--nthreads", type=int, required=False, default=8,
                     help="Number of threads to use for reconstruction."),
        click.option("-np", "--nprocesses", type=int, required=False, default=1,
                     help="Number of processes to use for reconstruction."),
    ]
    for option in reversed(options):
        func = option(func)
    return func

@cli.command(context_settings=cli_context, name='reconstruct', no_args_is_help=True)
@add_recon_options
def reconstruct_particle(
    parameter: str,
    particles: str, 
    tomograms: str,
    motion: str,
    binfactor: int, 
    boxsize: int,
    cropsize: int,
    symmetry: str,
    nthreads: int,
    nprocesses: int,
    ): 
    """Reconstruct a 3D map by back-projecting aligned sub-tomograms.

    Box and crop sizes are read from a parameter file or supplied directly via --boxsize / --cropsize.
    """
    run_reconstruct_particle(
        particles, tomograms, motion, binfactor, 
        boxsize, cropsize, symmetry, nthreads, nprocesses,
        parameter,
    )

def run_reconstruct_particle(
    particles: str,
    tomogram: str,
    motion: str,
    bin_factor: int,
    box_size: int,
    crop_size: int,
    symmetry: str,
    nthreads: int,
    nprocesses: int,
    parameter: str = None,
    ):
    """Back-project aligned sub-tomograms to produce a reconstructed 3D map.

    Sets up and runs a RELION ReconstructParticle job via the Pipeliner API.
    Box and crop sizes are derived from a parameter file when provided, or
    validated and set directly otherwise.

    Args:
        particles: RELION STAR file containing aligned particle orientations
                   and CTF parameters (e.g. from a Refine3D or Class3D job).
        tomogram: Optional STAR file of tomograms from a CtfRefine or Polish
                  job.  Overrides the default tomogram paths.
        motion: Optional STAR file of per-tilt motion trajectories used to
                apply beam-induced motion correction during reconstruction.
        bin_factor: Binning factor controlling the reconstruction resolution.
                    Higher values produce smaller, lower-resolution maps.
        box_size: 3D box size in pixels used during reconstruction.  If None,
                  derived from the parameter file.
        crop_size: Final cropped map size in pixels written to disk.  Must be
                   ≤ box_size.  If None, defaults to box_size.
        symmetry: Point-group symmetry applied during reconstruction
                  (e.g. 'C1', 'C4', 'D2').
        nthreads: Number of CPU threads per MPI process (--j).
        nprocesses: Number of MPI processes (--np).
        parameter: Path to a py2rely JSON parameter file.  When supplied, box
                   and crop sizes are computed automatically from the project
                   settings at the requested binning factor.
    """
    from pipeliner.jobs.tomography.relion_tomo import tomo_reconstructparticle_job
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.utils import relion5_tools
    from py2rely.routines import helper

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_directories_file('output_directories.json')

    # Set Parameters
    parameters = {
        'in_particles': particles,
        'in_tomograms': tomogram,
        'in_trajectories': motion,
        'binfactor': bin_factor,
        'point_group': symmetry,
        'nr_threads': nthreads,
        'nr_mpi': nprocesses,
        'do_use_direct_entries': 'yes',
    }

    # If parameter is provided, compute the boxsize from the parameter file
    if parameter: 
        helper.compute_boxsize_from_project(parameter, utils, bin_factor)
    # If boxsize and cropsize are not provided, raise an error
    elif box_size is None and crop_size is None: 
        raise ValueError("Either parameter, boxsize, or both (cropsize and boxsize) must be provided.")
    # If boxsize and/or cropsize are provided, validate the sizes and set the parameters
    else:
        utils.reconstruct_particle_job = tomo_reconstructparticle_job.RelionReconstructParticleJob()   
        box_size, crop_size = helper.validate_crop_box_size(box_size, crop_size)
        parameters['crop_size'] = crop_size
        parameters['box_size'] = box_size

    # Set the Remaining Parameters
    helper.set_parameters(utils.reconstruct_particle_job, parameters)

    # Print Input Parameters
    helper.print_params('Reconstruct Particle', params=parameters)

    # Run Reconstruct Particle
    utils.run_reconstruct_particle(rerunReconstruct=True)  

    # Return the Output Directory
    return utils.reconstruct_particle_job.output_dir   

@cli.command(context_settings=cli_context, name='reconstruct', no_args_is_help=True)
@add_recon_options
def reconstruct_particle_slurm(
    parameter: str,
    particles: str,
    tomograms: str,
    motion: str,
    binfactor: int,
    boxsize: int,
    cropsize: int,
    symmetry: str,
    nthreads: int,
    nprocesses: int,
    ):
    import py2rely.routines.submit_slurm as my_slurm

    command = my_slurm.build_command("py2rely routines reconstruct", {
        "particles": particles,
        "binfactor": binfactor,
        "symmetry": symmetry,
        "nthreads": nthreads,
        "nprocesses": nprocesses,
        "parameter": parameter,
        "tomograms": tomograms,
        "motion": motion,
        "boxsize": boxsize,
        "cropsize": cropsize,
    })

    my_slurm.create_shellsubmit(
        job_name="reconstruct-particle",
        output_file="reconstruct-particle.out",
        shell_name="reconstruct-particle.sh",
        command=command,
        num_gpus=0
    )
