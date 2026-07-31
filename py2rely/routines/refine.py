import py2rely.routines.submit_slurm as my_slurm 
from py2rely import cli_context, SAMPLING_ANGLES
import rich_click as click

@click.group()
@click.pass_context
def cli(ctx):
    pass

def refine3d_options(func):
    """Decorator to add shared options for refine3d commands."""
    options = [
        click.option("-param","--parameter",type=str,required=False,default=None,
                      help="Sub-Tomogram Refinement Parameter Path",),
        click.option("-p","--particles",type=str,required=True,default="Refine3D/job001/run_data.star",
                      help="Particles File to Reconstruct Data"),
        click.option("-t","--tomogram",type=str, required=True,default='tomograms.star',
                      help="CtfRefine or Polish tomograms StarFile (e.g., CtfRefine/job010)"),
        click.option("-mo","--motion",type=str, required=False,default=None,
                      help="Motion File (e.g., CtfRefine/job001/motion.star)"),
        click.option("-r","--reference",type=str,required=True,default="Reconstruct/job001/half1.mrc",
                      help="Reference MRC for Refinement"),
        click.option("-ma", "--mask",type=str,required=True,default="path/to/mask.mrc",
                      help="Mask for the Reference."),
        click.option("-lp", "--low-pass",type=float,required=True,default=15,
                      help="User Input Low Pass Filter"),
        click.option('-d', '--diameter',type=int,required=False,default=280,
                      help="Diameter of the Tomogram (default: 280)"),
        click.option("-sym","--symmetry",type=str,required=False,default='C1',
                      help="Symmetry of the Tomogram"),
        click.option('-ang', '--sampling-angle',type=click.Choice(SAMPLING_ANGLES),required=False,default='7.5 degrees',
                      help="Sampling Angle for Refinement"),
        click.option('-lan', '--local-sampling-angle',type=click.Choice(SAMPLING_ANGLES),required=False,default='1.8 degrees',
                      help="Local Sampling Angle for Refinement"),
        click.option("-rcg", "--ref-correct-greyscale",type=bool,required=False, default=True,
                      help="Reference Map is on Absolute Greyscale?"),
        click.option("--continue-iter",type=str,required=False,default=None,
                      help="Continue from this iteration? (e.g., Refine3D/job009/run_it008_optimiser.star)"),
        click.option('-j','--nthreads',type=int,required=False,default=8,
                      help="Number of Threads to Use"),
        click.option('-np','--nprocesses',type=int,required=False,default=1,
                      help="Number of Processes to Use"),
        click.option('-npool', '--nr-pool', type=int, required=False, default=16, 
                      help="Number of Pool Threads to Use"),
        click.option('-g', '--use-gpu', type=bool, required=False, default=True, 
                      help="Use GPU for Refinement"),
    ]  
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  

# Refine3D
@cli.command(context_settings=cli_context, no_args_is_help=True)
@refine3d_options
def refine3d(
    parameter: str,
    particles: str, 
    tomogram: str ,
    motion: str ,
    diameter: int,
    symmetry: str,
    sampling_angle: str,
    local_sampling_angle: str,
    low_pass: float ,
    ref_correct_greyscale: bool,    
    continue_iter: str ,
    reference: str,
    mask: str ,
    nthreads: int,
    nprocesses: int,
    nr_pool: int,
    use_gpu: bool,
    ): 
    """Run RELION gold-standard 3D auto-refinement on sub-tomograms.

    If a parameter file is provided, all the other options are ignored.

    Pass --continue-iter to resume from a previous optimiser checkpoint.
    """

    run_refine3d(
        parameter, particles, tomogram, motion, diameter, symmetry,
        sampling_angle, local_sampling_angle, low_pass, ref_correct_greyscale,
        continue_iter, reference, mask, nthreads, nprocesses, nr_pool, use_gpu
    )

def run_refine3d(
    parameter: str,
    particles: str,
    tomogram: str,
    motion: str,
    diameter: int,
    symmetry: str,
    sampling_angle: str,
    local_sampling_angle: str,
    low_pass: float,
    ref_correct_greyscale: bool,
    continue_iter: str,
    reference: str,
    mask: str,
    nthreads: int,
    nprocesses: int,
    nr_pool: int,
    use_gpu: bool,
    ):
    """Run RELION 3D auto-refinement on extracted pseudo sub-tomograms.

    Sets up and executes a RELION AutoRefine job via the Pipeliner API.
    Angular sampling starts at ``sampling_angle`` (global search) and
    narrows to ``local_sampling_angle`` once the orientations converge.
    Box size is read from the parameter file when provided.

    Args:
        parameter: Path to a py2rely JSON parameter file used to derive the
                   extraction box size and pipeline directories.
        particles: RELION STAR file containing particle orientations and CTF data.
        reference: Starting reference MRC map for the refinement.
        mask: Optional soft mask MRC applied around the particle density to
              suppress solvent noise during FSC and refinement.
        motion: Optional STAR file of beam-induced motion trajectories from a
                Polish job.
        diameter: Particle diameter in Ångströms, used to set the integration
                  radius for the auto-refine algorithm.
        symmetry: Symmetry string applied to the reference (e.g. 'C1', 'D2').
        sampling_angle: Initial angular sampling interval for the global search
                        (choose from RELION's allowed values).
        local_sampling_angle: Fine angular sampling used once the search
                              localises around the correct orientation.
        low_pass: Initial low-pass filter (Å) applied to the reference before
                  the first iteration to prevent reference bias.
        ref_correct_greyscale: If True, RELION corrects the reference map to
                               absolute greyscale before the first iteration.
        continue_iter: Path to a previous optimiser STAR file to resume
                       refinement from a specific iteration checkpoint.
        tomogram: Optional tomogram STAR file (e.g. from CtfRefine / Polish)
                  to override the default tomogram paths.
        nthreads: Number of CPU threads per MPI process (--j).
        nprocesses: Number of MPI processes (--np).
        use_gpu: If True, enables GPU acceleration for the refinement.
    """
    from pipeliner.jobs.tomography.relion_tomo import tomo_refine3D_job
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.utils import relion5_tools
    from py2rely.routines import helper
    import starfile

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_directories_file('output_directories.json')
    utils.tomo_refine3D_job = tomo_refine3D_job.TomoRelionRefine3D()

    # Set Required Parameters
    required_parameters = {
        'fn_mask': mask, 'fn_ref': reference,
        'in_particles': particles, 'in_tomograms': tomogram, 
        'in_trajectories': motion, 'use_direct_entries': 'yes',
        'nr_threads': nthreads, 'nr_mpi': nprocesses, 'nr_pool': nr_pool,
    }
    required_parameters['use_gpu'] = 'yes' if use_gpu else 'no'
    required_parameters['ref_correct_greyscale'] = 'yes' if ref_correct_greyscale else 'no'
    helper.set_parameters(utils.tomo_refine3D_job, required_parameters)

    # Set Parameters
    parameters = {
        'particle_diameter': diameter, 'sym_name': symmetry,
        'ini_high': low_pass, 'sampling': sampling_angle, 
        'auto_local_sampling': local_sampling_angle
    }
    if parameter:
        df = starfile.read(particles)
        utils.binning = int(df['optics']['rlnTomoSubtomogramBinning'])
        utils.read_json_params_file(parameter)
        # read_json_params_file() only loads self.params + the binning list; it does
        # not set any joboptions. Apply the refine3D block to the job so that ini_high,
        # particle_diameter, offset_*, sampling and other_args (e.g. "--firstiter_cc")
        # from the JSON actually reach relion_refine (mirrors initialize_auto_refine()).
        utils.tomo_refine3D_job = utils.parse_params(utils.tomo_refine3D_job, 'refine3D')
        utils.get_new_sampling(utils.tomo_refine3D_job)
        # Re-assert the CLI-provided required inputs so they take precedence over the JSON
        # (particles / tomograms / ref / mask / mpi / threads / pool / gpu / greyscale).
        helper.set_parameters(utils.tomo_refine3D_job, required_parameters)
    else:
        # Set Parameters
        helper.set_parameters(utils.tomo_refine3D_job, parameters)

    # Add required parameters to parameters
    parameters.update(required_parameters) 
    # Print Input Parameters
    helper.print_params('Refine3D', params=parameters)

    # Run 3D-Refinement
    utils.run_auto_refine(rerunRefine=True)

    # Return the Output Directory
    return utils.tomo_refine3D_job.output_dir

@cli.command(context_settings=cli_context, name='refine3d')
@refine3d_options
@my_slurm.add_compute_options
def refine3d_slurm(
    parameter: str,
    particles: str,
    reference: str,
    mask: str,
    low_pass: float,
    ref_correct_greyscale: bool,
    continue_iter: str,
    tomogram: str,
    motion: str,
    diameter: int,
    symmetry: str,
    sampling_angle: str,
    local_sampling_angle: str,
    nthreads: int,
    nprocesses: int,
    use_gpu: bool,
    num_gpus: int,
    gpu_constraint: str,
    ):

    command = my_slurm.build_command("py2rely routines refine3d", {
        "parameter": parameter,
        "particles": particles,
        "reference": reference,
        "low-pass": abs(low_pass),
        "ref-correct-greyscale": ref_correct_greyscale,
        "diameter": diameter,
        "symmetry": symmetry,
        "sampling-angle": sampling_angle,
        "local-sampling-angle": local_sampling_angle,
        "nthreads": nthreads,
        "nprocesses": nprocesses,
        "use-gpu": use_gpu,
        "mask": mask,
        "tomogram": tomogram,
        "motion": motion,
        "continue-iter": continue_iter,
    })

    my_slurm.create_shellsubmit(
        job_name="refine3d",
        output_file="refine3d.out",
        shell_name="refine3d.sh",
        command=command,
        num_gpus=num_gpus,
        gpu_constraint=gpu_constraint
    )