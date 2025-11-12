from pipeliner.api.manage_project import PipelinerProject
import py2rely.routines.submit_slurm as my_slurm 
from py2rely.utils import relion5_tools
import rich_click as click, starfile, os

@click.group()
@click.pass_context
def cli(ctx):
    pass

class TheClassifier:
    """Class for automated classification."""

    def __init__(self, parameter_path: str, low_pass: float = 15):

        # Initialize the Pipeliner Project 
        self.project = PipelinerProject(make_new_project=True)
        self.utils = relion5_tools.Relion5Pipeline(self.project)
        self.utils.read_json_params_file(parameter_path)
        self.utils.read_json_directories_file('output_directories.json')
        self.low_pass = low_pass

    @classmethod
    def from_utils(cls, utils):
        """Create instance directly from utils object."""
        instance = cls.__new__(cls)  # Create instance without calling __init__
        instance.utils = utils

        # Get the Low Pass from the Pipeline Criteria
        instance.low_pass = utils.get_resolution(utils.tomo_refine3D_job, 'refine3D') * 1.25

        # Initialize Selection Job
        if instance.utils.tomo_select_job is None:
            instance.utils.initialize_selection()

        return instance

    def _get_best_class(self, input, metric='rlnEstimatedResolution'):
        """ Get the best class from the classification job"""
        
        input = input.replace('data','model')
        output = starfile.read(input)['model_classes']
        results = output[metric]

        # If the resolutions are identical, we use the translations accuracy
        if results[0] != results[1]:
            best_class = results.argmin() + 1
        else: 
            results = output['rlnAccuracyTranslationsAngst']
            best_class = results.argmin() + 1
        current_resolution = output['rlnEstimatedResolution'][best_class-1]

        return best_class, current_resolution

    def _create_mask(self, reference: str):
        """Create a mask for the particles."""
        # Create Mask for Classification
        self.utils.mask_create_job.joboptions['fn_in'].value = reference
        self.utils.mask_create_job.joboptions['lowpass_filter'].value = self.low_pass
        self.utils.run_mask_create(self.utils.tomo_refine3D_job, self.utils.tomo_class3D_job)

    def run(self, particles: str, reference: str, mask: str = None):
        # Only Create Mask if None was Provided
        if mask is None:
            self._create_mask(reference)

        # Core Classification Parameters
        self.utils.tomo_class3D_job.joboptions['fn_ref'].value = reference
        self.utils.tomo_class3D_job.joboptions['in_particles'].value = particles
        self.utils.tomo_class3D_job.joboptions['ini_high'].value = self.low_pass
        self.utils.tomo_class3D_job.joboptions['fn_mask'].value = self.utils.mask_create_job.output_dir + 'mask.mrc' 
        self.utils.run_tomo_class3D()

        # Determine Best Class
        maxIter = self.utils.find_final_iteration()
        best_class, current_res = self._get_best_class(maxIter)

         # Start off By running the selection job
        self.utils.tomo_select_job.joboptions['fn_data'].value = maxIter
        self.utils.tomo_select_job.joboptions['select_minval'].value = best_class
        self.utils.tomo_select_job.joboptions['select_maxval'].value = best_class
        self.utils.run_subset_select()

        # Set Up Refinement Job
        current_particles = self.utils.tomo_select_job.output_dir + 'particles.star'
        if self.utils.binning == 2:

            # Re-run Refinement
            self.utils.tomo_refine3D_job.joboptions['ini_high'].value = current_res * 1.5
            self.utils.tomo_refine3D_job.joboptions['in_particles'].value = current_particles
            self.utils.tomo_refine3D_job.joboptions['fn_ref'].value = reference
            self.utils.run_auto_refine(rerunRefine=True)
            output = self.utils.tomo_refine3D_job.output_dir + 'run_data.star'

            # Re-Run Masking
            self.utils.mask_create_job.joboptions['fn_in'].value = self.utils.tomo_refine3D_job.output_dir + 'run_class001.mrc'
            self.utils.mask_create_job.joboptions['lowpass_filter'].value = self.utils.get_resolution(self.utils.tomo_refine3D_job, 'refine3D') * 1.25
            self.utils.run_mask_create(self.utils.tomo_refine3D_job, None, rerunMaskCreate = True)
        else:
            output = self.utils.tomo_select_job.output_dir + 'particles.star'
        return output

    def run_iterative(self, particles: str, reference: str, mask: str = None, num_iterations: int = 2):
        """Run the classification pipeline."""

        # Only Create Mask if None was Provided
        if mask is None:
            self._create_mask(reference)

        # Initialize Best Resolution
        best_resA = 999

        # Main Loop
        final_particles = {}

        # Core Classification Parameters
        self.utils.tomo_class3D_job.joboptions['ini_high'].value = self.low_pass
        self.utils.tomo_class3D_job.joboptions['fn_ref'].value = reference
        self.utils.tomo_class3D_job.joboptions['fn_mask'].value = self.utils.mask_create_job.output_dir + 'mask.mrc'
        for i in range(num_iterations):

            # Run Classification
            self.utils.tomo_class3D_job.joboptions['in_particles'].value = particles
            self.utils.run_tomo_class3D(rerunClassify=True)

            # Determine Best Class
            maxIter = self.utils.find_final_iteration()
            best_class, current_res = self._get_best_class(maxIter)

            # If we Get a reasonable resolution, Extract Remaining Particles for Second Round
            if current_res < best_resA * 1.2:
                final_particles[f'iter{i}'] = [maxIter, best_class]

                # Create New Particles with Rejected Particles
                particles = self.utils.tomo_class3D_job.output_dir + 'rejected_particles.star'
                sub_particles = self._subset_select(maxIter, best_class, include=False)
                starfile.write(sub_particles, particles)

                # We need to Update the Mask...

            # Reset the Current resolution if we get a lower value:
            if current_res < best_resA:
                best_resA = current_res

        # We need to merge these particles into a final particles file
        best_particles = self._extract_final_particles(final_particles)

        print('Path to Best Particles: ', best_particles)
        exit()
        return best_particles

    def _subset_select(self, particlesFname, bestClass, include=True):

        # Read Particles File and Parse Optics + Particles Group
        particlesFile = starfile.read(particlesFname)
        optics = particlesFile['optics']
        particles = particlesFile['particles']

        # Keep only the Best Class
        if include: 
            keepClasses = [bestClass]
        # Remove BestClass from the List
        else:
            allClasses = particles['rlnClassNumber'].unique()
            keepClasses = allClasses[allClasses != bestClass] 

        # Only Extract the Particles with Desired Class
        filteredParticles = particles[particles['rlnClassNumber'].isin(keepClasses)]
        
        # Relion5 Output - See if General Exists (Specifies Whether Sub-Tomograms is 2D MRCs Stacks)
        general = particlesFile['general']
        newParticles = {'general': general, 'optics':optics, 'particles':filteredParticles}

        return newParticles

    def _extract_final_particles(self, final_particles):
        """Extract final particles from the classification results."""

        # Start off By running the selection job
        self.utils.tomo_select_job.joboptions['fn_data'].value = final_particles['iter0'][0]
        self.utils.tomo_select_job.joboptions['select_minval'].value = final_particles['iter0'][1]
        self.utils.tomo_select_job.joboptions['select_maxval'].value = final_particles['iter0'][1]
        self.utils.run_subset_select(rerunSelect = True)
        output = self.utils.tomo_select_job.output_dir + 'particles.star'

        # Use Subset Select Function to Retain the Final Particles
        particles = starfile.read(output)
        all_particles = particles['particles']
        for ii in range(1, len(final_particles)):
            sub_particles = self._subset_select(final_particles[f'iter{ii}'][0], output, final_particles[f'iter{ii}'][1])['particles']
            all_particles = pd.concat([all_particles, sub_particles], ignore_index=True)
        particles['particles'] = all_particles

        os.remove(output)
        starfile.write(particles, output)

        return output
