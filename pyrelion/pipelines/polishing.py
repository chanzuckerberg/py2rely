from pipeliner.api.manage_project import PipelinerProject
import pyrelion.routines.submit_slurm as my_slurm 
from pyrelion.utils import relion5_tools
import click

class ThePolisher:
    """Class for high-resolution polishing with two entry points."""

    def __init__(self, parameter_path: str):
        """Initialize the polishing pipeline with configuration file."""
        self.project = PipelinerProject(make_new_project=True)
        self.utils = relion5_tools.Relion5Pipeline(self.project)
        self.utils.read_json_params_file(parameter_path)
        self.utils.read_json_directories_file('output_directories.json')
        
        # Initialize the processes
        self.utils.initialize_reconstruct_particle()
        self.utils.initialize_ctf_refine()
        self.utils.initialize_mask_create()

    @classmethod
    def from_utils(cls, utils):
        """Create instance directly from utils object."""
        instance = cls.__new__(cls)  # Create instance without calling __init__
        instance.utils = utils
        return instance

    def run_new_pipeline(self, particles: str, mask: str, tomograms: str = None, 
                        box_size: int = None, num_iterations: int = 2):
        """Run the high-resolution refinement and polishing stage."""
        # If a Path for Refined Tomograms is Provided, Assign it 
        if tomograms is not None:
            self.utils.set_new_tomograms_starfile(tomograms)        

        # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
        self.utils.update_job_binning_box_size(
            self.utils.reconstruct_particle_job,
            self.utils.pseudo_subtomo_job,
            None,
            binningFactor=1
        )    

        # Run the Polishing Pipeline
        self._run_polishing(particles, mask, box_size, num_iterations)

    def run(self, particles: str):
        """Run polishing with existing setup."""
        # Implementation would go here based on your needs
        pass

    def _run_polishing(self, particles: str, mask: str, box_size: int, num_iterations: int = 2):
        """Execute the main polishing pipeline."""
        self.utils.initialize_ctf_refine()
        self.utils.initialize_bayesian_polish()

        # For now, lets start off with 2 iterations
        for ii in range(num_iterations):

            # Reconstruction
            self.utils.reconstruct_particle_job.joboptions['in_particles'].value = particles
            self.utils.run_reconstruct_particle(rerunReconstruct=True)

            # Post Process
            self.utils.post_process_job.joboptions['fn_in'].value = self.utils.reconstruct_particle_job.output_dir + 'half1.mrc'
            self.utils.run_post_process(rerunPostProcess=True)

            # CTF Refinement
            self.utils.ctf_refine_job.joboptions['in_particles'].value = particles
            self.utils.ctf_refine_job.joboptions['in_halfmaps'].value = self.utils.reconstruct_particle_job.output_dir + 'half1.mrc'
            self.utils.ctf_refine_job.joboptions['in_refmask'].value = mask
            self.utils.run_ctf_refine()

            # Update the tomograms starfile
            # Here just bayesian polish is ine

            # Bayesian Polishing
            # self.utils.bayesian_polish_job.joboptions['box_size'].value = 
            self.utils.bayesian_polish_job.joboptions['in_post'].value = self.utils.post_process_job.output_dir + 'postprocess.star'
            self.utils.bayesian_polish_job.joboptions['in_tomograms'].value = self.utils.ctf_refine_job.output_dir + 'tomograms.star'
            self.utils.bayesian_polish_job.joboptions['in_particles'].value = particles
            self.utils.run_bayesian_polish()

            # Update motion and tomograms starfile
            # For 1. Pseudo-subtomo, 2. Reconstruct, 3. Post Process, 4. 3D Refinement

            # Pseudo-Subtomogram Extraction
            # self.utils.pseudo_subtomo_job.joboptions['box_size'].value = 
            # self.utils.pseudo_subtomo_job.joboptions['crop_size'].value = 
            self._update_inputs(self.utils.pseudo_subtomo_job)
            self.utils.run_pseudo_subtomo(rerunPseudoSubtomo=True)
            
            # Reconstruction
            self._update_inputs(self.utils.reconstruct_particle_job)            
            self.utils.reconstruct_particle_job.joboptions['in_particles'].value = self.utils.pseudo_subtomo_job.output_dir + 'particles.star'
            self.utils.run_reconstruct_particle(rerunReconstruct=True)

            # Post Process     
            self._update_inputs(self.utils.post_process_job)
            self.utils.post_process_job.joboptions['fn_in'].value = self.utils.reconstruct_particle_job.output_dir + 'half1.mrc'
            self.utils.run_post_process(rerunPostProcess=True)

            # 3D Refinement
            self._update_inputs(self.utils.tomo_refine3D_job)
            self.utils.tomo_refine3D_job.joboptions['in_particles'].value = self.utils.pseudo_subtomo_job.output_dir + 'particles.star'
            self.utils.tomo_refine3D_job.joboptions['fn_ref'].value = self.utils.ctf_refine_job.output_dir + 'run_class001.mrc'
            self.utils.run_auto_refine(rerunRefine=True)

            # Post-Process to Estimate Resolution     
            self._update_inputs(self.utils.post_process_job)
            self.utils.post_process_job.joboptions['fn_in'].value = self.utils.reconstruct_particle_job.output_dir + 'half1.mrc'
            self.utils.run_post_process(rerunPostProcess=True)

    def _update_inputs(self, job):
        """Update job inputs with latest bayesian polish results."""
        job.joboptions['in_particles'].value = self.utils.bayesian_polish_job.output_dir + 'particles.star'
        job.joboptions['in_tomograms'].value = self.utils.bayesian_polish_job.output_dir + 'tomograms.star'
        job.joboptions['in_trajectories'].value = self.utils.bayesian_polish_job.output_dir + 'motion.star'
        job.joboptions['in_post'].value = self.utils.post_process_job.output_dir + 'postprocess.star'


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