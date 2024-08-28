from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import json, click

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type=str,
    required=True,
    default='sta_parameters.json',
    help="The Saved Parameter Path",
)
@click.option(
    "--reference-template",
    type=str,
    required=False,
    default=None,
    help="Provided Template for Preliminary Refinment (Optional)",
)
@click.option(
    "--run-denovo-generation",
    type=bool,
    required=False, 
    default=False,
    help="Generate Initial Reconstruction with Denovo"
)
@click.option(
    "--run-class3D",
    type=bool,
    required=False,
    default=False, 
    help="Test"
)
def sta_pipeline(
    parameter_path: str,
    reference_template: str,
    run_denovo_generation: bool, 
    run_class3d: bool, 
    ):

    # Print Input Parameters
    print(f'\nPipeline Parameters: \nParameter-Path: {parameter_path}\nRun-Denovo: {run_denovo_generation}\nRun-Class-3D: {run_class3d}\nReference Template: {reference_template}\n')

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    ############################################################################################

    # Recontruct Tomograms 
    utils.initialize_reconstruct_tomograms()
    utils.run_reconstruct_tomograms()

    #############################################################################################

    # Generate Pseudo Sub-Tomograms 
    utils.initialize_pseudo_tomos()
    utils.run_pseudo_subtomo()

    # Generate Initial Reference Model for Sub-sequent Refinement
    utils.initialize_auto_refine()
    if run_denovo_generation:
        # Initialize and I/O for Denovo Initial Model Generation
        utils.initialize_initial_model()
        utils.initial_model_job.joboptions['fn_img'].value = utils.pseudo_subtomo_job.output_dir + 'particles.star'        
        utils.run_initial_model()
        refine_reference = utils.initial_model_job.output_dir + 'initial_model.mrc'
    elif reference_template is not None:
        # I/O and In this Case Reference isn't On Correct GrayScale
        utils.tomo_refine3D_job.joboptions['fn_img'].value = utils.pseudo_subtomo_job.output_dir + 'particles.star'
        utils.tomo_refine3D_job.joboptions['fn_ref'].value = reference_template
        utils.tomo_refine3D_job.joboptions['ref_correct_greyscale'].value = "no"
        utils.run_auto_refine()

        refine_reference = None # Reset Refinement Parameters 
        utils.tomo_refine3D_job.joboptions['ref_correct_greyscale'].value = "yes"        
    else: 
        # Reconstruct with Template Matching Parameters
        utils.run_reconstruct_particle()
        refine_reference = utils.reconstruct_job.output_dir + 'merged.mrc'

    #############################################################################################        

    # Main Loop 
    utils.initialize_reconstruct_particle()
    utils.initialize_mask_create()
    for binFactor in range(len(utils.binningList)):

        ########################################################################################

        # Primary 3D Refinement Job and Update Input Parameters
        if refine_reference is not None:
            utils.tomo_refine3D_job.joboptions['fn_img'].value = utils.pseudo_subtomo_job.output_dir + 'particles.star'
            utils.tomo_refine3D_job.joboptions['fn_ref'].value = refine_reference
            utils.run_auto_refine()

        #########################################################################################            

        # Primary 3D Refinement Job and Update Input Parameters
        if run_class3d:        
            utils.initialize_tomo_class3D()
            utils.tomo_class3D_job.joboptions['fn_img'].value = utils.tomo_refine3D_job.output_dir + 'run_data.star'
            utils.tomo_class3D_job.joboptions['fn_ref'].value = utils.tomo_refine3D_job.output_dir + 'run_class001.mrc'           
            utils.run_tomo_class3D()

        #########################################################################################

        # Only Increase Resolution with the Non-Last Steps
        if binFactor < len(utils.binningList) - 1:

            # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
            utils.update_resolution(binFactor+1)

            # TODO: Get Last Refinement Iteration 
            # Reconstruct Particle at New Binning and Create mask From That Resolution
            utils.reconstruct_particle_job.joboptions['in_particles'].value = utils.tomo_refine3D_job.output_dir + 'run_data.star'  
            utils.run_reconstruct_particle()    
            refine_reference = utils.reconstruct_particle_job.output_dir + 'merged.mrc'

            # Create Mask for Reconstruction and Next Stages of Refinement
            utils.mask_create_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'merged.mrc'
            utils.mask_create_job.joboptions['lowpass_filter'].value = utils.get_resolution(utils.tomo_refine3D_job, 'refine3D') * 1.25
            utils.run_mask_create(utils.tomo_refine3D_job, utils.tomo_class3D_job)

            # Post-Process to Estimate Resolution     
            utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'half1.mrc'
            utils.run_post_process()

            # Update the Refinement Low Pass Filter with Previous Reconstruction Resolution 
            currResolution = utils.get_resolution(utils.post_process_job, 'post_process')
            utils.tomo_refine3D_job.joboptions['ini_high'].value = currResolution * 1.5

            #########################################################################################

            # Create PseudoTomogram Generation Job and Update Input Parameters
            utils.pseudo_subtomo_job.joboptions['in_particles'].value = utils.tomo_select_job.output_dir + 'particles.star' 
            utils.run_pseudo_subtomo()

