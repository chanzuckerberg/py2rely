from pyrelion.pipelines.bin1 import HighResolutionRefinement as HRrefine
from pipeliner.api.manage_project import PipelinerProject
from pyrelion.utils import relion5_tools
import json, click

@click.command(context_settings={"show_default": True}, name='sta')
@click.option(
    "--parameter",
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
    help="Run 3D-Classification Job After Refinement"
)
def average(
    parameter: str,
    reference_template: str,
    run_denovo_generation: bool, 
    run_class3d: bool, 
    ):
    """
    Run the Sub-Tomogram Averaging Pipeline with pyRelion.
    """

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
    utils.read_json_directories_file('output_directories.json')

    # Print Input Parameters
    utils.print_pipeline_parameters('STA Pipeline', Parameter = parameter,
                                    Run_Denovo = run_denovo_generation, Run_Class3D = run_class3d,
                                    Reference_Template = reference_template)

    #############################################################################################

    # Generate Pseudo Sub-Tomograms 
    utils.initialize_pseudo_tomos()
    utils.run_pseudo_subtomo()

    #############################################################################################    

    # Generate Initial Reference Model for Sub-sequent Refinement
    utils.initialize_auto_refine()
    utils.initialize_tomo_class3D()
    utils.initialize_reconstruct_particle()

    if run_denovo_generation:
        # Initialize and I/O for Denovo Initial Model Generation
        utils.initialize_initial_model()       
        utils.run_initial_model()
        print(f'\nGenerating Initial Model with "Denovo Reconstruction"\n')        
        refine_reference = utils.initial_model_job.output_dir + 'initial_model.mrc'
    elif reference_template is not None:
        # Use Classification to Generate Initial Reference 
        print(f'\nGenerating Initial Model with "Class3D"\n')
        refine_reference = utils.run_initial_model_class3D(reference_template, nClasses = 1, nr_iter = 10)
    else: 
        # Reconstruct with Template Matching Parameters
        print(f'\nGenerating Initial Model with "Reconstruct Particle"\n')
        utils.run_reconstruct_particle()  
        refine_reference = utils.reconstruct_particle_job.output_dir + 'merged.mrc'

    #############################################################################################        

    # Main Loop 
    utils.initialize_mask_create()
    for binFactor in range(len(utils.binningList)):

        ########################################################################################

        # Primary 3D Refinement Job and Update Input Parameters
        if reference_template is not None:
            utils.tomo_refine3D_job.joboptions['in_particles'].value = utils.tomo_class3D_job.output_dir + 'run_it010_data.star'
        else:
            utils.tomo_refine3D_job.joboptions['in_particles'].value = utils.pseudo_subtomo_job.output_dir + 'particles.star'
        utils.tomo_refine3D_job.joboptions['fn_ref'].value = refine_reference
        utils.run_auto_refine()

        #########################################################################################            

        # Primary 3D Refinement Job and Update Input Parameters
        if run_class3d:         
            utils.tomo_class3D_job.joboptions['in_particles'].value = utils.tomo_refine3D_job.output_dir + 'run_data.star'
            utils.tomo_class3D_job.joboptions['fn_ref'].value = utils.tomo_refine3D_job.output_dir + 'run_class001.mrc'
            utils.tomo_class3D_job.joboptions['ini_high'].value = utils.get_resolution( utils.tomo_refine3D_job ) * 1.15
            utils.run_tomo_class3D()

        #########################################################################################

        # Only Increase Resolution when Binning is Greater than 2
        if utils.binning > 2:

            # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
            utils.update_resolution(binFactor+1)

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
            utils.pseudo_subtomo_job.joboptions['in_particles'].value = utils.tomo_refine3D_job.output_dir + 'run_data.star' 
            utils.run_pseudo_subtomo()
        else: 
            # Lets Upsample to bin1 with bin1 pipeline
            print('Completed the Main Refinement, Now Processing to Bin=1 Pipeline')
            continue

    # High-resolution refinement should only run if final binning is 1 and we're at 2 or lower
    bin1 = HRrefine.from_utils(utils)
    particles = utils.tomo_refine3D_job.output_dir + 'run_data.star'
    if utils.binning <= 2 and 1 in utils.binningList:

        # Run the High Resolution Pipeline (e.g., bin 2 -> bin 1 refinement)
        bin1.run(particles)

        #TODO: Complete the Polisher

    # Otherwise, just estimate resolution (e.g., bin 2 is the final)
    else:     
        # Estimate the Resolution of the Final Reconstruction
        bin1.run_resolution_estimate(particles)


    print('Pipeline Complete!')