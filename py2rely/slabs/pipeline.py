from pipeliner.jobs.relion import import_job, extract_job, class2D_job, select_job
from py2rely.slabs.preprocess import default_parameters
from py2rely.utils.sta_tools import PipelineHelper  # Import the parent class
from py2rely.slabs.visualize import gallery
import glob, starfile, os, re
import numpy as np

class SlabAveragePipeline(PipelineHelper):
    """
    A specialized pipeline for slab averaging that inherits from PipelineHelper.
    Leverages parent class's job tracking and rerun capabilities.
    """
    
    def __init__(self, inProject):
        """
        Initialize the SlabAveragePipeline with the given project.
        
        Args:
            inProject: The project instance that manages the pipeline.
        """
        # Call parent class constructor
        super().__init__(inProject, requireRelion=True)
        
        # Override params with slab-specific default parameters
        self.params = default_parameters.get_config()
        
        # Initialize slab-specific job attributes
        self.import_micrographs_job = None
        self.extract_job = None
        self.class2D_job = None
        self.auto_select_job = None
        self.classPath = None
        
        # For slab averaging, we use a fixed binning of 1
        self.binning = 1
        self.binningList = [1]
    
    def read_json_params_file(self, json_fname: str):
        """
        Read parameters from a JSON file for slab averaging.
        Sets up binning as 1 for compatibility with parent class.
        
        Args:
            json_fname: Path to the JSON file containing pipeline parameters.
        """
        if not os.path.exists(json_fname):
            raise FileNotFoundError(f"The file '{json_fname}' does not exist. Please check the path and try again.")
        
        self.params = self.read_json(json_fname)
        # Set fixed binning for slab averaging
        self.binning = 1
        self.binningList = [1]
    
    # ============ Slab-specific methods ============
    
    def initialize_import_micrographs(self):
        """Initialize the import micrographs job."""
        self.import_micrographs_job = import_job.RelionImportMovies()
        self.import_micrographs_job = self.parse_params(self.import_micrographs_job, 'import_micrographs')
        
        # Try to set output directory if already exists
        try:
            self.import_micrographs_job.output_dir = self.outputDirectories[f'bin{self.binning}']['import_micrographs']
        except:
            pass
    
    def run_import_micrographs(self, rerunImport: bool = False):
        """
        Run the import micrographs job.
        
        Args:
            rerunImport: If True, force rerun even if job exists
        """
        if rerunImport:
            importJobIter = self.return_job_iter(f'bin{self.binning}', 'import_micrographs')
        else:
            importJobIter = None
        
        self.run_job(self.import_micrographs_job, 'import_micrographs', 'Import Micrographs', jobIter=importJobIter)
    
    def initialize_particle_extraction(self):
        """Initialize the particle extraction job."""
        self.extract_job = extract_job.RelionExtract()
        self.extract_job = self.parse_params(self.extract_job, 'extract')
        
        try:
            self.extract_job.output_dir = self.outputDirectories[f'bin{self.binning}']['extract']
        except:
            pass
    
    def run_extract(self, rerunExtract: bool = False):
        """
        Run the particle extraction job.
        
        Args:
            rerunExtract: If True, force rerun even if job exists
        """
        if rerunExtract:
            extractJobIter = self.return_job_iter(f'bin{self.binning}', 'extract')
        else:
            extractJobIter = None
        
        self.run_job(self.extract_job, 'extract', 'Particle Extraction', jobIter=extractJobIter)
    
    def initialize_classification(self, classifyMethod: str = '2DEM', nr_iter: int = None, classifyStep: str = None):
        """
        Initialize 2D classification job.
        
        Args:
            classifyMethod: Classification method ('2DEM' or 'VDAM').
            nr_iter: Number of iterations for classification.
            classifyStep: Optional step identifier for multiple classification rounds
        """
        # Specify 2D-Classification Algorithm (EM vs VDAM)
        if classifyMethod == 'VDAM':
            self.class2D_job = class2D_job.RelionClass2DVDAM()
            if nr_iter is not None:
                self.class2D_job.joboptions['nr_iter_grad'].value = nr_iter
            print(f'\nRunning Class2D with VDAM Algorithm\n')
        else:
            self.class2D_job = class2D_job.RelionClass2DEM()
            if nr_iter is not None:
                self.class2D_job.joboptions['nr_iter_em'].value = nr_iter
            print(f'\nRunning Class2D with EM Algorithm\n')
        
        # Parse Parameters
        self.class2D_job = self.parse_params(self.class2D_job, 'class2D')
        
        # Generate job name based on classifyStep
        jobName = self.check_custom_job_name('class2D', classifyStep)
        
        # Try to set output directory if already exists
        try:
            self.class2D_job.output_dir = self.outputDirectories[f'bin{self.binning}'][jobName]
        except:
            pass
    
    def run_class2D(self, classifyStep: str = None, rerunClass2D: bool = True):
        """
        Run 2D classification job with proper iteration tracking.
        
        Args:
            classifyStep: Optional classification step identifier
            rerunClass2D: If True, force rerun even if job exists
        """
        # Generate job name
        jobName = self.check_custom_job_name('class2D', classifyStep)
        
        # Determine if we should track iterations
        if rerunClass2D:
            class2DJobIter = self.return_job_iter(f'bin{self.binning}', jobName)
        else:
            class2DJobIter = None
        
        self.run_job(self.class2D_job, jobName, '2D Classification', jobIter=class2DJobIter)
        
        # Get final class averages and visualize
        class_job = self.class2D_job.output_dir.split('/')[1]
        final_class_averages = self.find_final_iteration_2D(class_job).replace('data.star', 'classes.mrcs')
        
        # Plot the Class Averages
        gallery.class_average_gallery(final_class_averages)
    
    def find_final_iteration_2D(self, classPath: str):
        """
        Find the final iteration file for 2D classification.
        
        Args:
            classPath: Path to the class job directory.
        
        Returns:
            str: Path to the final iteration star file.
        """
        # Find the Final Iteration for 2D classification
        iterationStarFiles = glob.glob(os.path.join('Class2D', classPath, 'run_*_data.star'))
        maxIterationStarFile = max(iterationStarFiles, key=lambda x: int(re.search(r'_it(\d+)_', x).group(1)))
        self.maxIter = int(re.search(r'it(\d+)', maxIterationStarFile).group(1))
        return maxIterationStarFile
    
    def initialize_auto_selection(self, selectStep: str = None):
        """
        Initialize auto selection job for 2D classification.
        
        Args:
            selectStep: Optional selection step identifier.
        """
        self.auto_select_job = select_job.RelionSelectClass2DAuto()
        
        jobName = self.check_custom_job_name('auto_select', selectStep)
        
        try:
            self.auto_select_job.output_dir = self.outputDirectories[f'bin{self.binning}'][jobName]
        except:
            pass
    
    def run_auto_select(self, selectStep: str = None, rerunAutoSelect: bool = True):
        """
        Run auto selection job with iteration tracking.
        
        Args:
            selectStep: Optional selection step identifier
            rerunAutoSelect: If True, force rerun even if job exists
        """
        jobName = self.check_custom_job_name('auto_select', selectStep)
        
        if rerunAutoSelect:
            autoSelectJobIter = self.return_job_iter(f'select', jobName)
        else:
            autoSelectJobIter = None
        
        self.run_job(self.auto_select_job, jobName, 'Auto Selection', jobIter=autoSelectJobIter)
    
    def run_subset_select(self, keepClasses: list = None, # selectStep: str = None, 
                         classPath: str = None, rerunSelect: bool = True):
        """
        Run subset selection with full iteration tracking from parent class.
        
        Args:
            keepClasses: List of classes to keep.
            selectStep: Optional selection step identifier.
            classPath: Path to the class file.
            rerunSelect: If True, force rerun even if job exists
        """
        # Store classPath for custom_select
        if classPath:
            self.classPath = classPath
        
        # Generate job name
        # jobName = self.check_custom_job_name('select', selectStep)
        
        # Use parent class's iteration tracking
        if rerunSelect:
            selectJobIter = self.return_job_iter(f'bin{self.binning}', 'select')
        else:
            selectJobIter = None
        
        # Run using parent's run_job with full tracking
        self.run_job(self.tomo_select_job, 'select', 'Subset Selection', 
                    keepClasses=keepClasses, jobIter=selectJobIter)
    
    def custom_select(self, classPath: str, keepClasses: list, uniqueExport: str = None):
        """
        Perform custom selection for 2D classification.
        Simplified version for 2D workflows.
        
        Args:
            classPath: Path to the class file to select from (or uses self.classPath)
            keepClasses: List of classes to keep.
            uniqueExport: Optional custom export path.
        """

        # Make sure indexing is correct
        keepClasses = np.array(keepClasses) + 1
        
        # Read particles file
        particlesFile = starfile.read(classPath)
        optics = particlesFile['optics']
        particles = particlesFile['particles']
        
        # Filter particles by class
        filteredParticles = particles[particles['rlnClassNumber'].isin(keepClasses)]
        
        # Define write directory
        if uniqueExport is None:
            uniqueExport = self.tomo_select_job.output_dir + 'particles.star'
            # Remove old file if it exists
            if os.path.exists(uniqueExport):
                os.remove(uniqueExport)
        
        # Write filtered particles
        starfile.write({'optics': optics, 'particles': filteredParticles}, uniqueExport)

    def find_final_iteration(self):
        # Find the Final Iteration
        # iterationStarFiles = glob.glob(os.path.join('Class2D', classPath, 'run_*_data.star'))
        # maxIterationStarFile = max(iterationStarFiles, key=lambda x: int(re.search(r'_it(\d+)_', x).group(1)))
        # maxIter = int(re.search(r'it(\d+)', maxIterationStarFile).group(1))
        # Filter out unwanted filenames (exclude 'run_annon_itXXX_*' cases)

        # Find the Final Iteration, Ignore User Submission Runs
        iterationStarFiles = glob.glob(os.path.join(self.class2D_job.output_dir, 'run_it*_data.star'))
        iterationStarFiles = [f for f in iterationStarFiles if re.search(r'run_it\d+_data\.star$', f)]
        
        if not iterationStarFiles:
            raise ValueError(f"No valid iteration files found in {os.path.join(self.class2D_job.output_dir)}")
        
        # Extract iteration number and find the max iteration
        maxIterationStarFile = max(iterationStarFiles, key=lambda x: int(re.search(r'run_it(\d+)_', x).group(1)))
        maxIter = int(re.search(r'run_it(\d+)_', maxIterationStarFile).group(1))

        return os.path.join(self.class2D_job.output_dir, f'run_it{maxIter:03d}_data.star')