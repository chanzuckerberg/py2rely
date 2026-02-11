from pipeliner.api.manage_project import PipelinerProject
import py2rely.routines.submit_slurm as my_slurm 
from py2rely.utils import relion5_tools
import rich_click as click

class ThePolisher:
    """Class for high-resolution polishing with two entry points."""
        
    max_counts = 5 # Max Counts before terminating the Polisher

    def __init__(self, parameter_path: str, 
                 tomograms: str = None, motion: str = None,
                 box_size: int = 256, crop_size: int = 256):
        """Initialize the polishing pipeline with configuration file."""

        # Initialize the Pipeliner Project 
        self.project = PipelinerProject(make_new_project=True)
        self.utils = relion5_tools.Relion5Pipeline(self.project)
        self.utils.read_json_params_file(parameter_path)
        self.utils.read_json_directories_file('output_directories.json')

        # If a Path for Refined Tomograms is Provided, Assign it
        if tomograms is not None:
            self.utils.set_new_tomograms_starfile(tomograms)
        
        # Initialize the processes
        self.utils.initialize_pseudo_tomos()        
        self.utils.initialize_reconstruct_particle()
        self.utils.initialize_ctf_refine()
        self.utils.initialize_bayesian_polish()
        self.utils.initialize_mask_create()

        # Assumption: This pipeline can only be ran at bin1
        self.utils.update_job_binning_box_size(
            self.utils.reconstruct_particle_job,
            self.utils.pseudo_subtomo_job,
            None,
            binningFactor=1
        )

        # Initialize the Auto Refine Job
        self.utils.initialize_auto_refine()


    @classmethod
    def from_utils(cls, utils):
        """Create instance directly from utils object."""
        instance = cls.__new__(cls)  # Create instance without calling __init__
        instance.utils = utils

        # Initialize the processes
        instance.utils.initialize_ctf_refine()
        instance.utils.initialize_bayesian_polish()

        # Update the Box Size to Current Pipeline Parameter
        init_box_size = utils.reconstruct_particle_job.joboptions['box_size'].value
        instance.utils.ctf_refine_job.joboptions['box_size'].value = init_box_size
        instance.utils.bayesian_polish_job.joboptions['box_size'].value = init_box_size

        return instance

    def run(self, particles: str, mask: str, num_iterations: int = 2):
        """Execute the main polishing pipeline."""

        # Initialize the Best Resolution
        self.best_resolution = 999
        self.counter = 0

        # For now, lets start off with 2 iterations
        for ii in range(num_iterations):

            # Half Map from Refinement
            # half_map = self.utils.tomo_refine3D_job.output_dir + 'run_half1_class001_unfil.mrc'
            half_map = self.utils.reconstruct_particle_job.output_dir + 'half1.mrc'

            # CTF Refinement
            self.utils.ctf_refine_job.joboptions['in_post'].value = self.utils.post_process_job.output_dir + 'postprocess.star'
            self.utils.ctf_refine_job.joboptions['in_particles'].value = particles
            self.utils.ctf_refine_job.joboptions['in_halfmaps'].value = half_map
            self.utils.ctf_refine_job.joboptions['in_refmask'].value = mask
            self.utils.run_ctf_refine(rerunCtfRefine=True)

            # Bayesian Polishing
            self.utils.bayesian_polish_job.joboptions['in_post'].value = self.utils.post_process_job.output_dir + 'postprocess.star'
            self.utils.bayesian_polish_job.joboptions['in_tomograms'].value = self.utils.ctf_refine_job.output_dir + 'tomograms.star'
            self.utils.bayesian_polish_job.joboptions['in_particles'].value = particles
            self.utils.bayesian_polish_job.joboptions['in_halfmaps'].value = half_map
            self.utils.bayesian_polish_job.joboptions['in_refmask'].value = mask
            self.utils.run_bayesian_polish(rerunPolish=True)

            # Update the Trajectories and Tomograms Starfile for Polish and Ctf Refine
            self._update_inputs(self.utils.ctf_refine_job)
            self._update_inputs(self.utils.bayesian_polish_job)

            # Pseudo-Subtomogram Extraction
            self._update_inputs(self.utils.pseudo_subtomo_job)
            self.utils.pseudo_subtomo_job.joboptions['in_particles'].value = self.utils.bayesian_polish_job.output_dir + 'particles.star'
            self.utils.run_pseudo_subtomo(rerunPseudoSubtomo=True)
            
            # Reconstruction
            self._update_inputs(self.utils.reconstruct_particle_job)            
            self.utils.reconstruct_particle_job.joboptions['in_particles'].value = self.utils.pseudo_subtomo_job.output_dir + 'particles.star'
            self.utils.run_reconstruct_particle(rerunReconstruct=True)

            # Post Process
            self.utils.post_process_job.joboptions['fn_in'].value = self.utils.reconstruct_particle_job.output_dir + 'half1.mrc'
            self.utils.run_post_process(rerunPostProcess=True)
            if self._check_stopping_criteria(): break

            # 3D Refinement
            self._update_inputs(self.utils.tomo_refine3D_job)
            self.utils.tomo_refine3D_job.joboptions['in_particles'].value = self.utils.pseudo_subtomo_job.output_dir + 'particles.star'
            self.utils.tomo_refine3D_job.joboptions['fn_ref'].value = self.utils.reconstruct_particle_job.output_dir + 'half1.mrc'
            self.utils.run_auto_refine(rerunRefine=True)

            # Reconstruction 
            self.utils.reconstruct_particle_job.joboptions['in_particles'].value = self.utils.tomo_refine3D_job.output_dir + 'run_data.star'
            self.utils.run_reconstruct_particle(rerunReconstruct=True)

            # Update Particles for Next Iteration
            particles = self.utils.tomo_refine3D_job.output_dir + 'run_data.star'

            # Post-Process to Estimate Resolution     
            self.utils.post_process_job.joboptions['fn_in'].value = self.utils.reconstruct_particle_job.output_dir + 'half1.mrc'
            self.utils.run_post_process(rerunPostProcess=True)
            if self._check_stopping_criteria(): break

    def _update_inputs(self, job):
        """Update job inputs with latest bayesian polish results."""
        job.joboptions['in_tomograms'].value = self.utils.bayesian_polish_job.output_dir + 'tomograms.star'
        job.joboptions['in_trajectories'].value = self.utils.bayesian_polish_job.output_dir + 'motion.star'

    def _check_stopping_criteria(self):
        """ Check to See if Best Resolution Needs Updating """

        curr_resolution = self.utils.get_resolution(self.utils.post_process_job, 'post_process')
        if curr_resolution < self.best_resolution:
            self.best_resolution = curr_resolution
            print(f"New best resolution: {self.best_resolution:.2f} Å")
            return False
        else:
            self.counter += 1
            if self.counter >= self.max_counts:
                print("Max counts reached, stopping the polisher.")
                return True
            else:
                print(f"No improvement. Counter: {self.counter}/{self.max_counts}")
                return False

def polishing_options(func):
    """Decorator to add shared options for polishing commands."""
    options = [
        click.option("--parameter-path", type=str, required=True, default='sta_parameters.json', 
                      help="The Saved Parameter Path",),
        click.option("--particles", type=str, required=True, default='particles.star', 
                      help="The Particles Star File to Start Polishing",),
        click.option("--mask", type=str, required=True, default='mask.mrc', 
                      help="The Mask to Use for Polishing",),
        click.option('--tomograms', type=str, required=False, default=None, 
                      help="The Tomograms Star File to Start Polishing (e.g., 'tomograms.star')",),
        click.option('--motion', type=str, required=False, default=None, 
                      help="The Motion Star File to Start Polishing (e.g., 'motion.star')",),
        click.option('--box-size', type=int, required=False, default=256,
                      help="The Box Size for Polishing (default: 256)",),
        click.option('--crop-size', type=int, required=False, default=256,
                      help="The Crop Size for Polishing (default: 256)",),
        click.option('--num-iterations', type=int, required=False, default=2,
                      help="Number of Iterations for Polishing (default: 2)",),
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
    tomograms: str,
    motion: str,
    box_size: int,
    crop_size: int,
    num_iterations: int = 2
    ):
    """
    Run polishing and ctf refinement through cli.
    """

    polish = ThePolisher(parameter_path, tomograms, motion, box_size, crop_size)
    polish.run(particles, mask, num_iterations) 

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