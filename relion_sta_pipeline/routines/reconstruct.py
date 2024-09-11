from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import pipeliner.job_manager as job_manager
import json, click, starfile

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type=str,
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--particles-path",
    type=str,
    required=True,
    default="Refine3D/job001/run_data.star",
    help="Path to Particles File to Reconstruct Data"
)
@click.option(
    "--bin-factor",
    type=int,
    required=False,
    default=1,
    help="Bin Factor to Determine At Which Resolution to Reconstruct Averaged Map"
)
@click.option(
    "--mask-path",
    type=str,
    required=False,
    default=None,
    help="Path for Unique Mask for Measuring the Map Resolution"
)
def particle(
    parameter_path: str,
    particles_path: str, 
    bin_factor: int, 
    mask_path: str = None
    ): 

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # Initialize Job Classes
    utils.initialize_reconstruct_particle()
    utils.initialize_pseudo_tomos()

    # Print Input Parameters
    utils.print_pipeline_parameters('Reconstruct Particle', Parameter_Path = parameter_path, Particles_path = particles_path,
                                    Bin_Factor = bin_factor, Mask_Path = mask_path)    

    # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
    utils.update_job_binning_box_size(utils.reconstruct_particle_job,
                                      utils.pseudo_subtomo_job,
                                      None,
                                      binningFactor = bin_factor)     

    # Reconstruct Particle at New Binning and Create mask From That Resolution
    utils.reconstruct_particle_job.joboptions['in_particles'].value = particles_path
    utils.run_reconstruct_particle(rerunReconstruct=True)    
    refine_reference = utils.reconstruct_particle_job.output_dir + 'merged.mrc'

    # Create Mask for Reconstruction and Next Stages of Refinement
    if mask_path is None:
        utils.initialize_mask_create()
        utils.initialize_auto_refine()
        utils.mask_create_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'merged.mrc'
        utils.mask_create_job.joboptions['lowpass_filter'].value = utils.get_resolution(utils.tomo_refine3D_job, 'refine3D') * 1.25
        utils.run_mask_create(None, None, rerunMaskCreate=True)
    else:
        utils.initialize_post_process()
        utils.post_process_job.joboptions['fn_mask'].value = mask_path

    # Post-Process to Estimate Resolution     
    utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'half1.mrc'
    utils.run_post_process(rerunPostProcess=True)

@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type=str,
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--particles-path",
    type=str,
    required=True,
    help="Path to Particles"
)
@click.option(
    "--reference-path",
    type=str,
    required=True,
    help="Path to Reference for Classification"
)
@click.option(
    "--mask-path",
    type=str,
    required=False,
    default=None,
    help="Path of Mask for Classification",
)
@click.option(
    "--ini-high",
    type=float,
    required=False,
    default=None,
    help="Low-Pass Filter to Apply to Model"
)
@click.option(
    "--tau-fudge",
    type=float,
    required=False,
    default=3,
    help="Tau Regularization Parameter for Classification"
)
@click.option(
    "--nr-classes",
    type=int,
    required=False,
    default=3,
    help="Number of Classes for Classificaiton"
)
def class3d(
    parameter_path: str,
    particles_path: str, 
    reference_path: str,
    mask_path: str = None,     
    ini_high: float = None,
    tau_fudge: float = None,
    nr_classes: int = None,
    ):   

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # Get Binning
    particlesdata = starfile.read( particles_path )
    currentBinning = int(particlesdata['optics']['rlnTomoSubtomogramBinning'].values[0])
    binIndex = utils.binningList.index(currentBinning)    

    utils.initialize_pseudo_tomos()
    utils.initialize_reconstruct_particle()
    
    # Do I want to Scale My Classification Sampling Based on Resolution?
    utils.update_resolution(binIndex)    

    # 3D Refinement Job and Update Input Parameters 
    utils.initialize_tomo_class3D() 

    # Low Pass Filter If Provided
    if ini_high is not None:  utils.tomo_class3D_job.joboptions['ini_high'].value = ini_high
    else:                     ini_high = utils.tomo_class3D_job.joboptions['ini_high'].value   

    # Apply Mask, Tau-Fudge or Number of Classes If Provided
    if tau_fudge is not None:   utils.tomo_class3D_job.joboptions['tau_fudge'].value = tau_fudge
    else:                       tau_fudge = utils.tomo_class3D_job.joboptions['tau_fudge'].value

    if nr_classes is not None:  utils.tomo_class3D_job.joboptions['nr_classes'].value = nr_classes
    else:                       nr_classes = utils.tomo_class3D_job.joboptions['nr_classes'].value

    if mask_path is not None:   utils.tomo_class3D_job.joboptions['fn_mask'].value = mask_path
    
    # Specify Particles and 
    utils.tomo_class3D_job.joboptions['fn_img'].value = particles_path
    utils.tomo_class3D_job.joboptions['fn_ref'].value = reference_path

    # Print Input Parameters
    utils.print_pipeline_parameters('Class 3D', Parameter_Path=parameter_path, Reference_Path=reference_path,
                                    Particles_path=particles_path, Mask_path=mask_path, tau_fudge=tau_fudge, 
                                    nr_classes=nr_classes, ini_high=ini_high)     

    # Run
    utils.run_tomo_class3D(rerunClassify=True)


# Refine3D
@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type=str,
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--particles-path",
    type=str,
    required=True,
    default="Refine3D/job001/run_data.star",
    help="Path to Particles File to Reconstruct Data"
)
@click.option(
    "--reference-path",
    type=str,
    required=True,
    default="Refine3D/job001/class001.mrc",
    help="Path to Reference MRC for Refinement"
)
@click.option(
    "--mask-path",
    type=str,
    required=False,
    default=None,
    help="Path for Unique Mask for Measuring the Map Resolution, If Not Specified will Use Previous Mask from Pipeline"
)
@click.option(
    "--low-pass",
    type=str,
    required=False,
    default=15,
    help="User Input Low Pass Filter"
)
def refine3d(
    parameter_path: str,
    particles_path: str, 
    reference_path: str,
    mask_path: str = None,
    low_pass: float = None
    ): 

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # Print Input Parameters
    utils.print_pipeline_parameters('Refine3D', Parameter_Path=parameter_path,Particles_Path=particles_path,
                                    Mask_path=mask_path, low_pass_filter=low_pass)    

    # Update the Resolution with Given Binning Factor
    particlesdata = starfile.read(particles_path)
    currentBinning = int(particlesdata['optics']['rlnTomoSubtomogramBinning'].values[0])
    binIndex = utils.binningList.index(currentBinning)    

    # Do I want to Scale My Classification Sampling Based on Resolution?
    utils.initialize_pseudo_tomos()
    utils.initialize_auto_refine()
    utils.update_resolution(binIndex)     

    # Primary 3D Refinement Job and Update Input Parameters
    utils.tomo_refine3D_job.joboptions['fn_img'].value = particles_path
    utils.tomo_refine3D_job.joboptions['fn_ref'].value = reference_path

    # If Mask Path is Not Provided, Query the Last Ran Mask
    if mask_path is not None: 
        utils.tomo_refine3D_job.joboptions['fn_mask'].value = mask_path
    else:
        utils.initialize_mask_create()
        utils.tomo_refine3D_job.joboptions['fn_mask'].value = utils.mask_create_job.output_dir + 'mask.mrc' 

    # Low Pass Filter
    utils.tomo_refine3D_job.joboptions['ini_high'].value = low_pass

    # Run 3D-Refinement
    utils.run_auto_refine(rerunRefine=True)

# Mask Create + Post-Process
@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type=str,
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--reconstruction-path",
    type=str,
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--low-pass",
    type=str,
    required=False,
    default=15,
    help="User Input Low Pass Filter"
)
@click.option(
    "--extend",
    type=int,
    required=False,
    default=3,
    help="The initial binary mask is extended this number of pixels in all directions."
)
@click.option(
    "--soft-edge",
    type=int,
    required=False,
    default=5,
    help="Add a soft-edge of this many pixels."
)
def mask_post_process(
    parameter_path: str,
    reconstruction_path: str, 
    low_pass: float,
    extend: int,
    soft_edge: int
    ):

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # Initialize Job Classes
    utils.initialize_reconstruct_particle()
    utils.initialize_pseudo_tomos()

    # Print Input Parameters
    utils.print_pipeline_parameters('Mask Create - Post Process', Parameter_Path = parameter_path, 
                                    Reconstruction_Path = reconstruction_path,
                                    Low_Pass = low_pass, Extend = extend, Soft_Edge=soft_edge)    

    # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
    utils.update_job_binning_box_size(utils.reconstruct_particle_job,
                                      utils.pseudo_subtomo_job,
                                      None,
                                      binningFactor = bin_factor)

    # Create Mask for Reconstruction and Next Stages of Refinement
    utils.initialize_post_process()
    if mask_path is None:
        utils.initialize_mask_create()
        utils.initialize_auto_refine()
        utils.mask_create_job.joboptions['fn_in'].value = reconstruction_path
        utils.mask_create_job.joboptions['lowpass_filter'].value = low_pass
        utils.mask_create_job.joboptions['extend_inimask'].value = extend
        utils.mask_create_job.joboptions['width_mask_edge'].value = soft_edge
        utils.run_mask_create(None, None, rerunMaskCreate=True)
    else:
        utils.post_process_job.joboptions['fn_mask'].value = mask_path

    # Post-Process to Estimate Resolution     
    utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'half1.mrc'
    utils.run_post_process(rerunPostProcess=True)