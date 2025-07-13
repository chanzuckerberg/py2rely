from pipeliner.api.manage_project import PipelinerProject
import pyrelion.routines.submit_slurm as my_slurm 
from pyrelion.utils import relion5_tools
import click

def polishing_options(func):
    """Decorator to add shared options for polishing commands."""
    options = [
        click.option("--parameter-path", type=str, required=True, default='sta_parameters.json', 
                      help="The Saved Parameter Path",),
        click.option("--particles", type=str, required=True, default='particles.star', 
                      help="The Particles Star File to Start Polishing",),
        click.option("--mask", type=str, required=True, default='mask.mrc', 
                      help="The Mask to Use for Polishing",),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  


class ThePolisher:

    @staticmethod
    def run_new_pipeline(parameter_path: str, particles: str, mask: str):
        """
        Run the high-resolution refinement and polishing stage.
        """

        # Create Pipeliner Project
        my_project = PipelinerProject(make_new_project=True)
        utils = relion5_tools.Relion5Pipeline(my_project)
        utils.read_json_params_file(parameter_path)
        utils.read_json_directories_file('output_directories.json')

        # If a Path for Refined Tomograms is Provided, Assign it 
        if tomograms is not None:
            utils.set_new_tomograms_starfile(tomograms)        

        # Initialize the Processes
        utils.initialize_reconstruct_particle()
        utils.initialize_ctf_refine()

        # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
        utils.update_job_binning_box_size(utils.reconstruct_particle_job,
                                        utils.pseudo_subtomo_job,
                                        None,
                                        binningFactor = 1)    

        # Initialize the Mask Create and Auto Refine Jobs   

        utils.initialize_mask_create()

        # Run the Polishing Pipeline
        polisher(
            parameter_path, particles, mask, num_iterations=2
            )

    @staticmethod
    def run(
        utils, 
        particles, 
    ):

    def run_polishing(

    ):


    self.utils.initialize_ctf_refine()
    self.utils.initialize_bayesian_polish()

    # For now, lets start off with 2 iterations
    for ii in range(num_iterations):

        # Reconstruction
        utils.reconstruct_particle_job.joboptions['in_particles'].value = particles
        utils.run_reconstruct_particle()

        # Post Process

        # CTF Refinement
        utils.ctf_refine_job.joboptions['in_particles'].value = particles
        utils.ctf_refine_job.joboptions['in_halfmaps'].value = utils.reconstruct_particle_job.output_dir + 'half1.mrc'
        utils.ctf_refine_job.joboptions['in_refmask'].value = mask
        utils.run_ctf_refine()

        # Update the tomograms starfile
        # Here just bayesian polish is ine

        # Bayesian Polishing
        # utils.bayesian_polish_job.joboptions['box_size'].value = 
        utils.bayesian_polish_job.joboptions['in_post'].value = utils.post_process_job.output_dir + 'postprocess.star'
        utils.bayesian_polish_job.joboptions['in_tomograms'].value = utils.ctf_refine_job.output_dir + 'tomograms.star'
        utils.bayesian_polish_job.joboptions['in_particles'].value = particles
        utils.run_bayesian_polish()

        # Update motion and tomograms starfile
        # For 1. Pseudo-subtomo, 2. Reconstruct, 3. Post Process, 4. 3D Refinement

        # Pseudo-Subtomogram Extraction
        # utils.pseudo_subtomo_job.joboptions['box_size'].value = 
        # utils.pseudo_subtomo_job.joboptions['crop_size'].value = 
        utils.pseudo_subtomo_job.joboptions['in_particles'].value = utils.bayesian_polish_job.output_dir + 'particles.star'
        utils.pseudo_subtomo_job.joboptions['in_tomograms'].value = utils.bayesian_polish_job.output_dir + 'tomograms.star'
        utils.pseudo_subtomo_job.joboptions['in_trajectories'].value = utils.bayesian_polish_job.output_dir + 'motion.star'
        utils.run_pseudo_subtomo()
        
        # Reconstruction
        utils.reconstruct_particle_job.joboptions['in_particles'].value = utils.pseudo_subtomo_job.output_dir + 'particles.star'
        utils.run_reconstruct_particle()

        # Post Process     
        utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'half1.mrc'
        utils.run_post_process()

        # 3D Refinement
        utils.tomo_refine3D_job.joboptions['in_particles'].value = utils.pseudo_subtomo_job.output_dir + 'particles.star'
        utils.tomo_refine3D_job.joboptions['fn_ref'].value = utils.ctf_refine_job.output_dir + 'run_class001.mrc'
        utils.run_auto_refine()

        # Post-Process to Estimate Resolution     
        utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'half1.mrc'
        utils.run_post_process()

def polisher(
    parameter_path: str,
    particles: str,
    mask: str,
    num_iterations: int = 2,
    ):
    """
    Run the high-resolution refinement and polishing stage.
    """

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # Initialize the Processes
    utils.initialize_reconstruct_particle()
    utils.initialize_mask_create()
    utils.initialize_ctf_refine()
    utils.initialize_bayesian_polish()
    utils.initialize_pseudo_tomos()

    # For now, lets start off with 2 iterations
    for ii in range(num_iterations):

        # Reconstruction
        utils.reconstruct_particle_job.joboptions['in_particles'].value = particles
        utils.run_reconstruct_particle()

        # CTF Refinement
        utils.ctf_refine_job.joboptions['in_particles'].value = utils.reconstruct_particle_job.output_dir + 'particles.star'
        utils.run_ctf_refine()

        # Bayesian Polishing
        utils.bayesian_polish_job.joboptions['in_particles'].value = utils.ctf_refine_job.output_dir + 'particles.star'
        utils.run_bayesian_polish()

        # Pseudo-Subtomogram Extraction
        utils.pseudo_subtomo_job.joboptions['in_particles'].value = utils.ctf_refine_job.output_dir + 'particles.star'
        utils.run_pseudo_subtomo()

        # 3D Refinement
        utils.tomo_refine3D_job.joboptions['fn_img'].value = utils.pseudo_subtomo_job.output_dir + 'particles.star'
        utils.tomo_refine3D_job.joboptions['fn_ref'].value = utils.ctf_refine_job.output_dir + 'run_class001.mrc'
        utils.run_auto_refine()

        # Post-Process to Estimate Resolution     
        utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'half1.mrc'
        utils.run_post_process()


@click.command(context_settings={"show_default": True})
@polishing_options
def polish_pipeline(
    parameter_path: str,
    particles: str,
    mask: str,
    ):
    """
    Run polishing and ctf refinement through cli.
    """

    polishing(parameter_path, particles, mask) 

@click.command(context_settings={"show_default": True})
@polishing_options
@my_slurm.add_compute_options
def polish_pipeline_slurm(
    parameter_path: str,
    particles: str,
    mask: str,
    num_gpus: int,
    gpu_constraint: str,
):
    """
    Run the high-resolution refinement and polishing stage through slurm.
    """

    # Create Polishing Command
    pass

if __name__ == "__main__":
    polishing()