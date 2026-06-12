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
    """
    Reconstruct map from sub-tomograms.
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

    if parameter: 
        helper.compute_boxsize_from_project(parameter, utils, bin_factor)
    elif box_size is None and crop_size is None: 
        raise ValueError("Either parameter, boxsize, or both (cropsize and boxsize) must be provided.")
    elif box_size is not None and crop_size is None:
        utils.reconstruct_particle_job = tomo_reconstructparticle_job.RelionReconstructParticleJob()
        parameters['crop_size'] = box_size
        parameters['box_size'] = box_size 
    else: # boxsize and cropsize are provided
        utils.reconstruct_particle_job = tomo_reconstructparticle_job.RelionReconstructParticleJob()   
        parameters['crop_size'] = crop_size
        parameters['box_size'] = box_size

    # Set the Remaining Parameters
    helper.set_parameters(utils.reconstruct_particle_job, parameters)

    # Print Input Parameters
    helper.print_params('Reconstruct Particle', params=parameters)

    # Run Reconstruct Particle
    utils.run_reconstruct_particle(rerunReconstruct=True)    

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

    # # Create Reconstruct Particle Command
    # command = f"""
    # py2rely routines reconstruct-particle \\
    #     --parameter {parameter} \\
    #     --particles {particles} \\
    #     --bin-factor {bin_factor} --low-pass {low_pass} \\
    # """

    # if mask is not None:
    #     command += f" --mask {mask}"

    # if extend is not None:
    #     command += f" --extend {extend}"

    # if soft_edge is not None:
    #     command += f" --soft-edge {soft_edge}"

    # if tomogram is not None:
    #     command += f" --tomogram {tomogram}"

    # Create Slurm Submit Script
    my_slurm.create_shellsubmit(
        job_name="reconstruct-particle",
        output_file="reconstruct-particle.out",
        shell_name="reconstruct-particle.sh",
        command=command,
        num_gpus=0
    )


# # Mask Create + Post-Process
# @cli.command(context_settings=cli_context)
# @click.option("-p", "--parameter", type=str, required=True, default="sta_parameters.json", 
#               help="Sub-Tomogram Refinement Parameter Path")
# @click.option("-r", "--reconstruction", type=str, required=True, 
#               help="Path to Reconstruction Job")
# @add_masking_options
# def mask_post_process(
#     parameter: str,
#     reconstruction: str, 
#     mask: str, 
#     low_pass: float,
#     extend: int,
#     soft_edge: int,
#     tomogram: str = None
#     ):
#     """Create mask and perform post-processing on an existing reconstruction.
    
#     This command creates a soft-edged mask from a reconstruction and performs
#     post-processing to estimate resolution via Fourier Shell Correlation (FSC).
#     Use this when you already have a reconstruction and want to regenerate masks
#     with different parameters or recalculate resolution estimates.
#     """

#     create_mask_and_post_process(parameter, reconstruction, mask, 
#                                  low_pass, extend, soft_edge, tomogram)

# def create_mask_and_post_process(
#     parameter: str,
#     reconstruction: str, 
#     mask: str = None,
#     low_pass: float = 10,
#     extend: int = 0,
#     soft_edge: int = 5,
#     tomogram: str = None
#     ):
#     from pipeliner.api.manage_project import PipelinerProject
#     from py2rely.utils import relion5_tools
#     import starfile, os

#     # Create Pipeliner Project
#     my_project = PipelinerProject(make_new_project=True)
#     utils = relion5_tools.Relion5Pipeline(my_project)
#     utils.read_json_params_file(parameter)
#     utils.read_json_directories_file('output_directories.json')

#     # If a Path for Refined Tomograms is Provided, Assign it 
#     if tomogram is not None:
#         utils.set_new_tomograms_star_file(tomogram)    

#     # Initialize Job Classes
#     utils.initialize_reconstruct_particle()
#     utils.initialize_pseudo_tomos()

#     # Print Input Parameters
#     utils.print_pipeline_parameters('Mask Create - Post Process', Parameter = parameter, 
#                                     Reconstruction = reconstruction,
#                                     Low_Pass = low_pass, Extend = extend, Soft_Edge=soft_edge)    

#     # Get Binning
#     recon_params = starfile.read( os.path.join(reconstruction, 'job.star') )
#     index = recon_params['joboptions_values'].index[ recon_params['joboptions_values']['rlnJobOptionVariable'] == 'binfactor' ][0]
#     currentBinning = int(recon_params['joboptions_values']['rlnJobOptionValue'][index])
#     binIndex = utils.binningList.index(currentBinning)    

#     print(f'\n[Mask Create - Post Process]\nRunning Mask Creation and Post-Processing at Bin Factor: {currentBinning}')

#     utils.initialize_pseudo_tomos()
#     utils.initialize_reconstruct_particle()
    
#     # Do I want to Scale My Classification Sampling Based on Resolution?
#     utils.update_resolution(binIndex)    

#     # Create Mask for Reconstruction and Next Stages of Refinement
#     utils.initialize_post_process()
#     if mask is None:
#         utils.initialize_mask_create()
#         utils.initialize_auto_refine()
#         utils.mask_create_job.joboptions['fn_in'].value = os.path.join(reconstruction, 'merged.mrc')
#         utils.mask_create_job.joboptions['lowpass_filter'].value = low_pass
#         utils.mask_create_job.joboptions['extend_inimask'].value = extend
#         utils.mask_create_job.joboptions['width_mask_edge'].value = soft_edge
        
#         # We don't need to pass a refine and classification job here
#         utils.run_mask_create(None, None, rerunMaskCreate=True)
#     else:
#         utils.post_process_job.joboptions['fn_mask'].value = mask

#     # Post-Process to Estimate Resolution     
#     utils.post_process_job.joboptions['fn_in'].value = os.path.join(reconstruction, 'half1.mrc')
#     utils.post_process_job.joboptions['low_pass'].value = low_pass
#     utils.run_post_process(rerunPostProcess=True)
    
