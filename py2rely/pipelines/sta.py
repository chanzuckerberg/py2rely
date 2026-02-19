from py2rely.utils import common
from py2rely import cli_context
import rich_click as click

@click.command(context_settings=cli_context, name='sta', no_args_is_help=True)
@common.add_sta_options
@common.add_submitit_options
def average(
    parameter: str,
    reference_template: str,
    run_denovo_generation: bool, 
    run_class3d: bool, 
    extract3d: bool,
    manual_masking: bool,
    submitit: bool,
    cpu_constraint: str,
    timeout: int
    ):
    """
    Run the Sub-Tomogram Averaging Pipeline with py2rely.
    """

    run_average(
        parameter, reference_template,
        run_denovo_generation, run_class3d, 
        extract3d,manual_masking,
        submitit, cpu_constraint, timeout
    )

def run_average(
    parameter: str,
    reference_template: str,
    run_denovo_generation: bool, 
    run_class3d: bool, 
    extract3d: bool,
    manual_masking: bool,
    submitit: bool,
    cpu_constraint: str,
    timeout: int
    ):
    from py2rely.pipelines.bin1 import HighResolutionRefinement as HRrefine
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.pipelines.classify import TheClassifier
    from py2rely.pipelines.polishing import ThePolisher
    from py2rely.utils import relion5_tools

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
    if extract3d and run_denovo_generation: # We only want to extract 3D particles if we are generating the initial model de novo
        utils.pseudo_subtomo_job.joboptions['do_output_2dstacks'].value = False
    utils.run_pseudo_subtomo()

    #############################################################################################    

    # Generate Initial Reference Model for Sub-sequent Refinement
    utils.initialize_auto_refine()
    utils.initialize_tomo_class3D()
    utils.initialize_reconstruct_particle()

    # Initial Model Generation
    particles = utils.pseudo_subtomo_job.output_dir + 'particles.star'
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
        particles = utils.tomo_class3D_job.output_dir + 'run_it010_data.star'
    else: 
        # Reconstruct with Template Matching Parameters
        print(f'\nGenerating Initial Model with "Reconstruct Particle"\n')
        utils.run_reconstruct_particle()  
        refine_reference = utils.reconstruct_particle_job.output_dir + 'merged.mrc'

    #############################################################################################        

    # Extract at 2D if original extraction is in 3D.
    # We only want to extract 3D particles if we are generating the initial model de novo    
    if extract3d and run_denovo_generation: 
        utils.run_pseudo_subtomo(rerunPseudoSubtomo=True)
        particles = utils.pseudo_subtomo_job.output_dir + 'particles.star'

    # Main Loop 
    utils.initialize_mask_create()
    for binFactor in range(len(utils.binningList)):

        ########################################################################################

        # Primary 3D Refinement Job and Update Input Parameters
        utils.tomo_refine3D_job.joboptions['in_particles'].value = particles
        utils.tomo_refine3D_job.joboptions['fn_ref'].value = refine_reference
        utils.run_auto_refine()

        # Duplicate Particles? 
        if binFactor == 0:
            starfile = utils.tomo_refine3D_job.output_dir + 'run_data.star'            
            remove_duplicates(utils, starfile, distance_scale=0.3)
        particles = utils.tomo_refine3D_job.output_dir + 'run_data.star' 

        #########################################################################################            

        # Classification Job
        if run_class3d and binFactor == 0:
            classifier = TheClassifier.from_utils(utils)
            particles = classifier.run(particles, utils.tomo_refine3D_job.output_dir + 'run_class001.mrc')
            
        #########################################################################################

        # Only Increase Resolution when Binning is Greater than 2
        if utils.binning > 2:

            # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
            utils.update_resolution(binFactor+1)

            # Reconstruct Particle at New Binning and Create mask From That Resolution 
            utils.reconstruct_particle_job.joboptions['in_particles'].value = particles
            utils.run_reconstruct_particle()    
            refine_reference = utils.reconstruct_particle_job.output_dir + 'half1.mrc'

            # Create Mask for Reconstruction and Next Stages of Refinement
            utils.mask_create_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'merged.mrc'
            utils.mask_create_job.joboptions['lowpass_filter'].value = utils.get_resolution(utils.tomo_refine3D_job, 'refine3D') * 1.25
            utils.run_mask_create(utils.tomo_refine3D_job, utils.tomo_class3D_job)

            if manual_masking and binFactor == 0:
                print('[UPDATE] Manual masking requested. Exiting for user intervention.')
                exit()

            # Post-Process to Estimate Resolution     
            utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'half1.mrc'
            utils.run_post_process()

            # Update the Refinement Low Pass Filter with Previous Reconstruction Resolution 
            currResolution = utils.get_resolution(utils.post_process_job, 'post_process')
            utils.tomo_refine3D_job.joboptions['ini_high'].value = currResolution * 1.5

            #########################################################################################

            # Create PseudoTomogram Generation Job and Update Input Parameters
            utils.pseudo_subtomo_job.joboptions['in_particles'].value = particles
            utils.run_pseudo_subtomo()
            particles = utils.pseudo_subtomo_job.output_dir + 'particles.star'
        else: 
            # Lets Upsample to bin1 with bin1 pipeline
            print('Completed the Main Refinement, Now Processing to Bin=1 Pipeline')
            break

    # High-resolution refinement should only run if final binning is 1 and we're at 2 or lower
    bin1 = HRrefine.from_utils(utils)
    if utils.binning <= 2 and 1 in utils.binningList:

        # Run the High Resolution Pipeline (e.g., bin 2 -> bin 1 refinement)
        print('Running Full-Resolution Refinement Pipeline')
        bin1.run(particles)
        particles = utils.tomo_refine3D_job.output_dir + 'run_data.star'

        # Run the Polisher (Ctf refine and bayesian polish)
        mask = utils.mask_create_job.output_dir + 'mask.mrc'
        
        # Initialize and Run the Polisher
        print(f'Bin=1 Pipeline Complete!!\nRunning the Polisher...')
        polish = ThePolisher.from_utils(utils)
        polish.run(particles, mask)

    # Otherwise, just estimate resolution (e.g., bin 2 is the final)
    else:     
        # Estimate the Resolution of the Final Reconstruction
        print(f'Exiting the STA Pipeline @ Bin = {utils.binning}, Estimating the Current Resolution...')        
        bin1.run_resolution_estimate()

def remove_duplicates(utils, starfile, distance_scale):
    import subprocess

    distance_angstroms = float(utils.tomo_refine3D_job.joboptions['particle_diameter'].value) * distance_scale
    cmd = f"relion_star_handler --i {starfile} --remove_duplicates {distance_angstroms} --o {starfile}"
    print(f"Removing duplicate particles with a distance of {distance_angstroms} A")
    subprocess.run(cmd, shell=True, check=True)
