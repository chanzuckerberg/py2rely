import relion_sta_pipeline.routines.submit_slurm as my_slurm 
from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import pipeliner.job_manager as job_manager
import json, click, starfile, os, mrcfile

@click.group()
@click.pass_context
def cli(ctx):
    pass

def add_masking_options(func):
    options = [
        click.option("--mask-path", type=str, required=False, default=None, 
                    help="(Optional) Path for Mask to Measure the Map Resolution. If none provide, a new mask will be created."),
        click.option("--low-pass", type=str, required=False, default=15, 
                     help="User Input Low Pass Filter"),
        click.option("--extend", type=int, required=False, default=None, 
                     help="The initial binary mask is extended this number of pixels in all directions."),
        click.option("--soft-edge", type=int, required=False, default=None, 
                     help="Add a soft-edge of this many pixels."),
        click.option("--tomogram-path", type=str, required=False, default=None, 
                     help="(Optional) Path to CtfRefine or Polish tomograms StarFile (e.g., CtfRefine/job010)") 
    ]
    for option in reversed(options):
        func = option(func)
    return func

@cli.command(context_settings={"show_default": True})
@click.option("--parameter-path", type=str, required=True, default="sta_parameters.json", 
              help="Sub-Tomogram Refinement Parameter Path")
@click.option("--particles-path", type=str, required=True, 
              help="Path to Particles File to Reconstruct Data (e.g., Refine3D/job001/run_data.star)")
@click.option("--bin-factor", type=int, required=False, default=1, 
              help="Bin Factor to Determine At Which Resolution to Reconstruct Averaged Map")
@add_masking_options
def reconstruct_particle(
    parameter_path: str,
    particles_path: str, 
    bin_factor: int, 
    mask_path: str = None,
    low_pass: float = None,
    extend: int = None, 
    soft_edge: int = None,
    tomogram_path: str = None
    ): 

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # If a Path for Refined Tomograms is Provided, Assign it 
    if tomogram_path is not None:
        utils.set_new_tomograms_star_file(tomogram_path)    

    # Initialize Job Classes
    utils.initialize_reconstruct_particle()
    utils.initialize_pseudo_tomos()

    # Print Input Parameters
    utils.print_pipeline_parameters('Reconstruct Particle', Parameter_Path = parameter_path, Particles_path = particles_path,
                                    Bin_Factor = bin_factor, Mask_Path = mask_path, Low_Pass_Filter = low_pass, 
                                    Mask_extend = extend, Mask_Soft_Edge = soft_edge)    

    # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
    utils.update_job_binning_box_size(utils.reconstruct_particle_job,
                                      utils.pseudo_subtomo_job,
                                      None,
                                      binningFactor = bin_factor)     

    # Reconstruct Particle at New Binning and Create mask From That Resolution
    utils.reconstruct_particle_job.joboptions['in_particles'].value = particles_path
    utils.run_reconstruct_particle(rerunReconstruct=True)    

    # Pass the Reconstruction to Mask Creation and Post Processing
    create_mask_and_post_process(parameter_path, utils.reconstruct_particle_job.output_dir, 
                                 mask_path, low_pass, extend, soft_edge, tomogram_path)



@cli.command(context_settings={"show_default": True})
@click.option("--parameter-path", type=str, required=True, default="sta_parameters.json", 
              help="Sub-Tomogram Refinement Parameter Path")
@click.option("--particles-path", type=str, required=True, 
              help="Path to Particles File to Reconstruct Data (e.g., Refine3D/job001/run_data.star)")
@click.option("--bin-factor", type=int, required=False, default=1, 
              help="Bin Factor to Determine At Which Resolution to Reconstruct Averaged Map")
@add_masking_options
def reconstruct_particle_slurm(
    parameter_path: str,
    particles_path: str, 
    bin_factor: int, 
    mask_path: str = None,
    low_pass: float = None,
    extend: int = None, 
    soft_edge: int = None,
    tomogram_path: str = None
    ):

    # Create Reconstruct Particle Command
    command = f"""
    pyrelion routines reconstruct-particle \\
        --parameter-path {parameter_path} \\
        --particles-path {particles_path} \\
        --bin-factor {bin_factor} --low-pass {low_pass} \\
    """

    if mask_path is not None:
        command += f" --mask-path {mask_path}"

    if extend is not None:
        command += f" --extend {extend}"

    if soft_edge is not None:
        command += f" --soft-edge {soft_edge}"

    if tomogram_path is not None:
        command += f" --tomogram-path {tomogram_path}"

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
@click.option("--parameter-path", type=str, required=True, default="sta_parameters.json", 
              help="Sub-Tomogram Refinement Parameter Path")
@add_masking_options
def mask_post_process(
    parameter_path: str,
    reconstruction_path: str, 
    mask_path: str, 
    low_pass: float,
    extend: int,
    soft_edge: int,
    tomogram_path: str = None
    ):

    create_mask_and_post_process(parameter_path, reconstruction_path, mask_path, 
                                 low_pass, extend, soft_edge, tomogram_path)

def create_mask_and_post_process(
    parameter_path: str,
    reconstruction_path: str, 
    mask_path: str = None,
    low_pass: float = 10,
    extend: int = 3,
    soft_edge: int = 5,
    tomogram_path: str = None
    ):

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # If a Path for Refined Tomograms is Provided, Assign it 
    if tomogram_path is not None:
        utils.set_new_tomograms_star_file(tomogram_path)    

    # Initialize Job Classes
    utils.initialize_reconstruct_particle()
    utils.initialize_pseudo_tomos()

    # Print Input Parameters
    utils.print_pipeline_parameters('Mask Create - Post Process', Parameter_Path = parameter_path, 
                                    Reconstruction_Path = reconstruction_path,
                                    Low_Pass = low_pass, Extend = extend, Soft_Edge=soft_edge)    

    # Get Binning
    recon_params = starfile.read( os.path.join(reconstruction_path, 'job.star') )
    currentBinning = int(recon_params['joboptions_values']['rlnJobOptionValue'][21])
    binIndex = utils.binningList.index(currentBinning)    

    print(f'\n[Mask Create - Post Process]\nRunning Mask Creation and Post-Processing at Bin Factor: {currentBinning}')

    utils.initialize_pseudo_tomos()
    utils.initialize_reconstruct_particle()
    
    # Do I want to Scale My Classification Sampling Based on Resolution?
    utils.update_resolution(binIndex)    

    # Create Mask for Reconstruction and Next Stages of Refinement
    utils.initialize_post_process()
    if mask_path is None:
        utils.initialize_mask_create()
        utils.initialize_auto_refine()
        utils.mask_create_job.joboptions['fn_in'].value = os.path.join(reconstruction_path, 'merged.mrc')
        utils.mask_create_job.joboptions['lowpass_filter'].value = low_pass
        utils.mask_create_job.joboptions['extend_inimask'].value = extend
        utils.mask_create_job.joboptions['width_mask_edge'].value = soft_edge
        
        # We don't need to pass a refine and classification job here
        utils.run_mask_create(None, None, rerunMaskCreate=True)
    else:
        utils.post_process_job.joboptions['fn_mask'].value = mask_path

    # Post-Process to Estimate Resolution     
    utils.post_process_job.joboptions['fn_in'].value = os.path.join(reconstruction_path, 'half1.mrc')
    utils.post_process_job.joboptions['low_pass'].value = low_pass
    utils.run_post_process(rerunPostProcess=True)    

