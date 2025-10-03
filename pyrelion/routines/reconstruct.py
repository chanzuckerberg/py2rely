from pipeliner.api.manage_project import PipelinerProject
import pyrelion.routines.submit_slurm as my_slurm 
import pipeliner.job_manager as job_manager
import json, click, starfile, os, mrcfile
from pyrelion.utils import relion5_tools

@click.group()
@click.pass_context
def cli(ctx):
    pass

def add_masking_options(func):
    options = [
        click.option("--mask", type=str, required=False, default=None, 
                    help="(Optional) Path for Mask to Measure the Map Resolution. If none provide, a new mask will be created."),
        click.option("--low-pass", type=str, required=False, default=15, 
                     help="User Input Low Pass Filter"),
        click.option("--extend", type=int, required=False, default=None, 
                     help="The initial binary mask is extended this number of pixels in all directions."),
        click.option("--soft-edge", type=int, required=False, default=None, 
                     help="Add a soft-edge of this many pixels."),
        click.option("--tomogram", type=str, required=False, default=None, 
                     help="(Optional) Path to CtfRefine or Polish tomograms StarFile (e.g., CtfRefine/job010)") 
    ]
    for option in reversed(options):
        func = option(func)
    return func

@cli.command(context_settings={"show_default": True})
@click.option("--parameter", type=str, required=True, default="sta_parameters.json", 
              help="Sub-Tomogram Refinement Parameter Path")
@click.option("--particles", type=str, required=True, 
              help="Path to Particles File to Reconstruct Data (e.g., Refine3D/job001/run_data.star)")
@click.option("--bin-factor", type=int, required=False, default=1, 
              help="Bin Factor to Determine At Which Resolution to Reconstruct Averaged Map")
@add_masking_options
def reconstruct_particle(
    parameter: str,
    particles: str, 
    bin_factor: int, 
    mask: str = None,
    low_pass: float = None,
    extend: int = None, 
    soft_edge: int = None,
    tomogram: str = None
    ): 

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
    utils.read_json_directories_file('output_directories.json')

    # If a Path for Refined Tomograms is Provided, Assign it 
    if tomogram is not None:
        utils.set_new_tomograms_star_file(tomogram)    

    # Initialize Job Classes
    utils.initialize_reconstruct_particle()
    utils.initialize_pseudo_tomos()

    # Print Input Parameters
    utils.print_pipeline_parameters('Reconstruct Particle', Parameter = parameter, Particles = particles,
                                    Bin_Factor = bin_factor, Mask = mask, Low_Pass_Filter = low_pass, 
                                    Mask_extend = extend, Mask_Soft_Edge = soft_edge)    

    # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
    utils.update_job_binning_box_size(utils.reconstruct_particle_job,
                                      utils.pseudo_subtomo_job,
                                      None,
                                      binningFactor = bin_factor)     

    # Reconstruct Particle at New Binning and Create mask From That Resolution
    utils.reconstruct_particle_job.joboptions['in_particles'].value = particles
    utils.run_reconstruct_particle(rerunReconstruct=True)    

    # Pass the Reconstruction to Mask Creation and Post Processing
    create_mask_and_post_process(parameter, utils.reconstruct_particle_job.output_dir, 
                                 mask, low_pass, extend, soft_edge, tomogram)



@cli.command(context_settings={"show_default": True}, name='reconstruct-particle')
@click.option("--parameter", type=str, required=True, default="sta_parameters.json", 
              help="Sub-Tomogram Refinement Parameter Path")
@click.option("--particles", type=str, required=True, 
              help="Path to Particles File to Reconstruct Data (e.g., Refine3D/job001/run_data.star)")
@click.option("--bin-factor", type=int, required=False, default=1, 
              help="Bin Factor to Determine At Which Resolution to Reconstruct Averaged Map")
@add_masking_options
def reconstruct_particle_slurm(
    parameter: str,
    particles: str, 
    bin_factor: int, 
    mask: str = None,
    low_pass: float = None,
    extend: int = None, 
    soft_edge: int = None,
    tomogram: str = None
    ):

    # Create Reconstruct Particle Command
    command = f"""
    pyrelion routines reconstruct-particle \\
        --parameter {parameter} \\
        --particles {particles} \\
        --bin-factor {bin_factor} --low-pass {low_pass} \\
    """

    if mask is not None:
        command += f" --mask {mask}"

    if extend is not None:
        command += f" --extend {extend}"

    if soft_edge is not None:
        command += f" --soft-edge {soft_edge}"

    if tomogram is not None:
        command += f" --tomogram {tomogram}"

    # Create Slurm Submit Script
    my_slurm.create_shellsubmit(
        job_name="reconstruct-particle",
        output_file="reconstruct-particle.out",
        shell_name="reconstruct-particle.sh",
        command=command,
        num_gpus=0
    )


# Mask Create + Post-Process
@cli.command(context_settings={"show_default": True})
@click.option("--parameter", type=str, required=True, default="sta_parameters.json", 
              help="Sub-Tomogram Refinement Parameter Path")
@add_masking_options
def mask_post_process(
    parameter: str,
    reconstruction: str, 
    mask: str, 
    low_pass: float,
    extend: int,
    soft_edge: int,
    tomogram: str = None
    ):

    create_mask_and_post_process(parameter, reconstruction, mask, 
                                 low_pass, extend, soft_edge, tomogram)

def create_mask_and_post_process(
    parameter: str,
    reconstruction: str, 
    mask: str = None,
    low_pass: float = 10,
    extend: int = 0,
    soft_edge: int = 5,
    tomogram: str = None
    ):

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
    utils.read_json_directories_file('output_directories.json')

    # If a Path for Refined Tomograms is Provided, Assign it 
    if tomogram is not None:
        utils.set_new_tomograms_star_file(tomogram)    

    # Initialize Job Classes
    utils.initialize_reconstruct_particle()
    utils.initialize_pseudo_tomos()

    # Print Input Parameters
    utils.print_pipeline_parameters('Mask Create - Post Process', Parameter = parameter, 
                                    Reconstruction = reconstruction,
                                    Low_Pass = low_pass, Extend = extend, Soft_Edge=soft_edge)    

    # Get Binning
    recon_params = starfile.read( os.path.join(reconstruction, 'job.star') )
    currentBinning = int(recon_params['joboptions_values']['rlnJobOptionValue'][21])
    binIndex = utils.binningList.index(currentBinning)    

    print(f'\n[Mask Create - Post Process]\nRunning Mask Creation and Post-Processing at Bin Factor: {currentBinning}')

    utils.initialize_pseudo_tomos()
    utils.initialize_reconstruct_particle()
    
    # Do I want to Scale My Classification Sampling Based on Resolution?
    utils.update_resolution(binIndex)    

    # Create Mask for Reconstruction and Next Stages of Refinement
    utils.initialize_post_process()
    if mask is None:
        utils.initialize_mask_create()
        utils.initialize_auto_refine()
        utils.mask_create_job.joboptions['fn_in'].value = os.path.join(reconstruction, 'merged.mrc')
        utils.mask_create_job.joboptions['lowpass_filter'].value = low_pass
        utils.mask_create_job.joboptions['extend_inimask'].value = extend
        utils.mask_create_job.joboptions['width_mask_edge'].value = soft_edge
        
        # We don't need to pass a refine and classification job here
        utils.run_mask_create(None, None, rerunMaskCreate=True)
    else:
        utils.post_process_job.joboptions['fn_mask'].value = mask

    # Post-Process to Estimate Resolution     
    utils.post_process_job.joboptions['fn_in'].value = os.path.join(reconstruction, 'half1.mrc')
    utils.post_process_job.joboptions['low_pass'].value = low_pass
    utils.run_post_process(rerunPostProcess=True)
    
# Post Process Command
@cli.command(context_settings={"show_default": True})
@click.option("--parameter", type=str, required=True, default="sta_parameters.json", 
              help="Sub-Tomogram Refinement Parameter Path")
@click.option('--mask', type=str, required=True, 
              help="Path to Mask to Measure the Map Resolution")
@click.option('--half-map', type=str, required=True, 
              help="Path to Half Map to Post Process")
@click.option('--low-pass', type=float, required=False, default=None, 
              help='Low Pass Filter to Use for Post Processing')
def post_process(
    parameter: str,
    mask: str,
    half_map: str,
    low_pass: float,
    ):

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
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

