from py2rely.utils import common
from py2rely import cli_context
import rich_click as click

class HighResolutionRefinement:
    """Class for high-resolution refinement with two entry points."""

    def __init__(
            self, parameter_file: str, 
            tomograms: str = None, rerun: bool = False,
            submitit: bool = False, cpu_constraint: str = '1', 
            gpu_constraint: str = None, num_gpus: int = 0, timeout: int = 0
        ):
        """Initialize the refinement pipeline with configuration file."""

        from pipeliner.api.manage_project import PipelinerProject
        from py2rely.utils import relion5_tools

        self.project = PipelinerProject(make_new_project=True)
        self.utils = relion5_tools.Relion5Pipeline(self.project)
        self.utils.read_json_params_file(parameter_file)
        self.utils.read_json_directories_file('output_directories.json')

        # Set Compute Constraints if Using Submitit
        if submitit:
            self.utils.use_submitit = True
            self.utils.set_compute_constraints(cpu_constraint, gpu_constraint, num_gpus, timeout)

        # Initialize the processes
        self.utils.initialize_pseudo_tomos()
        self.utils.initialize_reconstruct_particle()
        self.utils.initialize_mask_create()
        self.utils.initialize_auto_refine()

        # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
        self.utils.update_job_binning_box_size(
            self.utils.reconstruct_particle_job,
            self.utils.pseudo_subtomo_job,
            binningFactor=1
        )

        # Initialize the Mask Create and Auto Refine Jobs
        self.utils.initialize_mask_create()
        self.utils.initialize_auto_refine()         

        # Store the rerun flag
        self.rerun = rerun

    @classmethod
    def from_utils(cls, utils):
        """Create instance directly from utils object."""
        instance = cls.__new__(cls)  # Create instance without calling __init__
        instance.utils = utils
        instance.rerun = False  # Default to not rerun
        return instance

    def run(self, particles: str):
        """Run refinement with existing setup, estimating resolution first."""
        
        # Run Resolution Estimate to Get Low-Pass Filter
        self.run_resolution_estimate()

        # Which of these two do we want?
        # low_pass = self.utils.get_resolution(self.utils.post_process_job, 'post_process')
        low_pass = self.utils.get_half_fsc(self.utils.post_process_job.output_dir)

        # Check to see if resolution is sufficient - this should be optional. Ignore if not provided

        # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
        self.utils.update_job_binning_box_size(
            self.utils.reconstruct_particle_job,
            self.utils.pseudo_subtomo_job, 
            binningFactor=1
        )

        # Run the High Resolution Refinement Pipeline
        self.run_hr_refinement(particles, low_pass)

    def run_resolution_estimate(self):
        """Run resolution estimation for high-resolution refinement."""
        # Add Logic to Check if Mask is Available, if not create a new mask
        if self.utils.mask_create_job.output_dir == '': 
            self.utils.mask_create_job.joboptions['fn_in'].value = self.utils.tomo_refine3D_job.output_dir + 'run_class001.mrc'
            self.utils.mask_create_job.joboptions['lowpass_filter'].value = self.utils.get_resolution(self.utils.tomo_refine3D_job, 'refine3D') * 1.25
            self.utils.run_mask_create(self.utils.tomo_refine3D_job, None)       

        # Run Another Post Process to Estimate Low-Pass Filter
        self.utils.post_process_job.joboptions['fn_in'].value = self.utils.tomo_refine3D_job.output_dir + 'run_half1_class001_unfil.mrc'
        self.utils.post_process_job.joboptions['fn_mask'].value = self.utils.mask_create_job.output_dir + 'mask.mrc'
        self.utils.run_post_process(rerunPostProcess=True)

    def run_hr_refinement(self, particles: str, low_pass: float, mask: str = None):
        """Execute the main refinement pipeline."""
        from py2rely.routines.mask_create import auto_mask_create

        # Generate Pseudo Sub-Tomograms at Bin = 1
        self.utils.pseudo_subtomo_job.joboptions['in_particles'].value = particles
        self.utils.run_pseudo_subtomo() 

        # Reconstruct the Particle at Bin = 1
        self.utils.reconstruct_particle_job.joboptions['in_particles'].value = particles
        self.utils.run_reconstruct_particle(rerunReconstruct=self.rerun)

        # Automatically Create Mask if None is Provided
        if mask is None:
            auto_mask_create(self.utils, low_pass)

        # Processing Parameters for Auto Refine
        self.utils.tomo_refine3D_job.joboptions['nr_threads'].value = 24
        self.utils.tomo_refine3D_job.joboptions['ini_high'].value = low_pass 
        self.utils.tomo_refine3D_job.joboptions['do_solvent_fsc'].value = "yes"
        self.utils.tomo_refine3D_job.joboptions['sampling'].value = self.utils.sampling[5]
        self.utils.tomo_refine3D_job.joboptions['auto_local_sampling'].value = self.utils.sampling[5]    
        
        # Inputs for Auto Refine
        self.utils.tomo_refine3D_job.joboptions['in_particles'].value = self.utils.pseudo_subtomo_job.output_dir + 'particles.star'
        self.utils.tomo_refine3D_job.joboptions['fn_ref'].value = self.utils.reconstruct_particle_job.output_dir + 'half1.mrc'

        # Run the Auto Refine at Bin = 1
        self.utils.run_auto_refine(rerunRefine=self.rerun)

        # Reconstruct Particles with New Alignments
        self.utils.reconstruct_particle_job.joboptions['in_particles'].value = self.utils.tomo_refine3D_job.output_dir + 'run_data.star'
        self.utils.run_reconstruct_particle(rerunReconstruct=True)

        # Run Post Process
        self.utils.post_process_job.joboptions['fn_in'].value = self.utils.reconstruct_particle_job.output_dir + 'half1.mrc'
        self.utils.post_process_job.joboptions['fn_mask'].value = self.utils.mask_create_job.output_dir + 'mask.mrc'

        self.utils.run_post_process(rerunPostProcess=True)

# Decorator for CLI options
def high_resolution_options(func):
    """Decorator to add shared options for high-resolution commands."""
    options = [
        click.option("--parameter", '-p', type=str, required=True, default='sta_parameters.json', 
                      help="The Saved Parameter Path",),
        click.option("--tomograms", '-t', type=str, required=True, default='tomograms.star', 
                      help="The Tomograms Star File to Start Refinement",),
        click.option("--particles", '-pts', type=str, required=True, default='particles.star', 
                      help="The Particles Star File to Start Refinement",),
        click.option("--mask", '-m', type=str, required=False, default=None, 
                      help="The Mask to Use for Refinement, if none provided a new mask will be created.",),
        click.option("--low-pass", '-lp', type=float, required=True, default=10, 
                      help="The Low-Pass Filter to Use for Refinement",),
        click.option('--rerun', '-rr', type=bool, required=False, default=False, 
                      help="Rerun the pipeline if it has already been run.",),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  


@click.command(context_settings=cli_context, name='bin1', no_args_is_help=True)
@high_resolution_options
@common.add_submitit_options
def high_resolution_cli(
    parameter: str,
    tomograms: str,
    particles: str,
    mask: str,
    low_pass: float,
    rerun: bool,
    submitit: bool,
    cpu_constraint: str,
    gpu_constraint: str,
    num_gpus: int,
    timeout: int
    ):    
    """
    Run the high-resolution refinement through cli.
    """

    # Create Instance of HighResolutionRefinement Class and Run the Pipeline
    bin1 = HighResolutionRefinement(
        parameter, tomograms, rerun, submitit, 
        cpu_constraint, gpu_constraint, num_gpus, timeout
    )
    
    bin1.run_hr_refinement(particles, low_pass, mask)
