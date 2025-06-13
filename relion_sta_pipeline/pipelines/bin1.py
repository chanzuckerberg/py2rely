import relion_sta_pipeline.routines.submit_slurm as my_slurm 
from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import click, mrcfile
import numpy as np

class HighResolutionRefinement:
    """Class for high-resolution refinement with two entry points."""

    @staticmethod
    def run_new_pipeline( 
        parameter: str,
        particles: str,
        low_pass: float,
        mask: str = None,
        tomograms: str = None,
        rerun: bool = False
        ):

        # Create Pipeliner Project
        my_project = PipelinerProject(make_new_project=True)
        utils = relion5_tools.Relion5Pipeline(my_project)
        utils.read_json_params_file(parameter)
        utils.read_json_directories_file('output_directories.json')

        # If a Path for Refined Tomograms is Provided, Assign it 
        if tomograms is not None:
            utils.set_new_tomograms_starfile(tomograms)    

        # Initialize the Processes
        utils.initialize_pseudo_tomos()
        utils.initialize_reconstruct_particle() 

        # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
        utils.update_job_binning_box_size(utils.reconstruct_particle_job,
                                        utils.pseudo_subtomo_job,
                                        None,
                                        binningFactor = 1)         

        # Initialize the Mask Create and Auto Refine Jobs
        utils.initialize_mask_create()
        utils.initialize_auto_refine() 

        HighResolutionRefinement._run_high_resolution_refinement(
            utils, particles, low_pass, mask, rerun)

    @staticmethod
    def run( 
        utils,
        particles: str, 
    ):

        # Run Another Post Process to Estimate Low-Pass Filter
        utils.post_process_job.joboptions['fn_in'].value = utils.tomo_refine3D_job.output_dir + 'run_half1_class001_unfil.mrc'
        utils.post_process_job.joboptions['fn_mask'].value = utils.mask_create_job.output_dir + 'mask.mrc'
        utils.run_post_process(rerunPostProcess=True)
        low_pass = utils.get_resolution(utils.post_process_job, 'post_process')

        # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
        utils.update_job_binning_box_size(
            utils.reconstruct_particle_job,
            utils.pseudo_subtomo_job,
            None, binningFactor = 1
        )

        # Run the High Resolution Refinement Pipeline
        HighResolutionRefinement._run_high_resolution_refinement(
            utils, particles, low_pass)

    @staticmethod
    def _run_high_resolution_refinement( 
        utils, particles, low_pass, mask = None, rerun = False  ):
        
        # Generate Pseudo Sub-Tomograms at Bin = 1
        utils.pseudo_subtomo_job.joboptions['in_particles'].value = particles
        utils.run_pseudo_subtomo() 

        # Reconstruct the Particle at Bin = 1
        utils.reconstruct_particle_job.joboptions['in_particles'].value = particles
        utils.run_reconstruct_particle(rerunReconstruct=rerun)

        # Create Mask if None if Provided
        if mask is None:
            # Initialize Mask Create Job, and set the inimask to the standard deviation of the reconstruction
            utils.mask_create_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'merged.mrc'
            utils.mask_create_job.joboptions['lowpass_filter'].value = low_pass
            ini_mask = utils.get_reconstruction_std(utils.reconstruct_particle_job.output_dir + 'merged.mrc', low_pass)
            utils.mask_create_job.joboptions['inimask_threshold'].value = ini_mask
            utils.mask_create_job.joboptions['width_mask_edge'].value = 8
            utils.run_mask_create(utils.tomo_refine3D_job, None, False, rerunMaskCreate=rerun)  

        # Post Process to estimate Low-Pass Filter

        # Processing Parameters for Auto Refine
        utils.tomo_refine3D_job.joboptions['ini_high'].value = low_pass 
        utils.tomo_refine3D_job.joboptions['do_solvent_fsc'].value = "yes"
        utils.tomo_refine3D_job.joboptions['sampling'].value = utils.sampling[5]
        utils.tomo_refine3D_job.joboptions['auto_local_sampling'].value = utils.sampling[5]    
        
        # Inputs for Auto Refine
        utils.tomo_refine3D_job.joboptions['in_particles'].value = utils.pseudo_subtomo_job.output_dir + 'particles.star'
        utils.tomo_refine3D_job.joboptions['fn_ref'].value = utils.reconstruct_particle_job.output_dir + 'merged.mrc'

        # Run the Auto Refine at Bin = 1
        utils.run_auto_refine(rerunRefine=rerun)

        # Run Post Process
        utils.post_process_job.joboptions['fn_in'].value = utils.tomo_refine3D_job.output_dir + 'run_half1_class001_unfil.mrc'
        utils.post_process_job.joboptions['fn_mask'].value = utils.mask_create_job.output_dir + 'mask.mrc'
        utils.run_post_process(rerunPostProcess=rerun)

# Decorator for CLI options
def high_resolution_options(func):
    """Decorator to add shared options for high-resolution commands."""
    options = [
        click.option("--parameter", type=str, required=True, default='sta_parameters.json', 
                      help="The Saved Parameter Path",),
        click.option("--tomograms", type=str, required=True, default='tomograms.star', 
                      help="The Tomograms Star File to Start Refinement",),
        click.option("--particles", type=str, required=True, default='particles.star', 
                      help="The Particles Star File to Start Refinement",),
        click.option("--mask", type=str, required=False, default=None, 
                      help="The Mask to Use for Refinement, if none provided a new mask will be created.",),
        click.option("--low-pass", type=float, required=True, default=10, 
                      help="The Low-Pass Filter to Use for Refinement",),
        click.option('--rerun', type=bool, required=False, default=False, 
                      help="Rerun the pipeline if it has already been run.",),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  


@click.command(context_settings={"show_default": True}, name='bin1')
@high_resolution_options
def high_resolution_cli(
    parameter: str,
    tomograms: str,
    particles: str,
    mask: str,
    low_pass: float,
    rerun: bool,
    ):    
    """
    Run the high-resolution refinement through cli.
    """
    HighResolutionRefinement.run_new_pipeline(
        parameter, particles, low_pass,  mask, tomograms, rerun)


@click.command(context_settings={"show_default": True}, name='bin1-pipeline')
@high_resolution_options
@my_slurm.add_compute_options
def high_resolution_slurm(
    parameter: str,
    tomograms: str,
    particles: str,
    mask: str,
    low_pass: float,
    rerun: bool,
    num_gpus: int,
    gpu_constraint: str,
    ):
    """
    Run the high-resolution refinement through slurm.
    """

    # Create Refine3D Command
    command = f"""
pyrelion pipelines bin1 \\
    --parameter {parameter} \\
    --tomograms {tomograms} \\
    --particles {particles} \\
    """

    if mask is not None:
        command += f" --mask {mask}"

    if low_pass is not None:
        command += f" --low-pass {low_pass}"

    if rerun:
        command += f" --rerun True"

    # Create Slurm Submit Script
    my_slurm.create_shellsubmit(
        job_name="bin1-pipeline",
        output_file="bin1_pipeline.out",
        shell_name="high-res-pipeline.sh",
        command=command,
        num_gpus=num_gpus,
        gpu_constraint=gpu_constraint
    )