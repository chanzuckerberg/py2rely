from pipeliner.jobs.relion import select_job, maskcreate_job, postprocess_job
import pipeliner.job_manager as job_manager
import glob, starfile, json, re, mrcfile
import subprocess, os
import numpy as np
import warnings

# Suppress all future warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

class PipelineHelper:
    """
    A helper class for managing and running a Relion-based pipeline in a cryo-EM project.
    """    

    def __init__(self, inProject):
        """
        Initialize the PipelineHelper with the given project.

        Args:
            inProject: The project instance that manages the pipeline.
        """

        self.check_if_relion_is_available()

        self.myProject = inProject

        # Define sampling angles and box sizes for various stages of the pipeline.
        self.sampling = ['30 degrees', '15 degrees', '7.5 degrees', '3.7 degrees', '1.8 degrees', '0.9 degrees',\
                         '0.5 degrees', '0.2 degrees', '0.1 degrees']

        self.boxSizes = [24, 32, 36, 40, 44, 48, 52, 56, 60, 64, 72, 84, 96, 100, 104, 112, 120, 128,\
                         132, 140, 168, 180, 192, 196, 208, 216, 220, 224, 256, 288, 300, 320, 352, 360,\
                         384, 416, 440, 448, 480, 480, 512, 540, 560, 576, 588, 600, 630, 648, 672, 686, 700]

        # self.initialize_post_process()

        # Initialize binning factor
        self.binning = None      

    def check_if_relion_is_available(self):
        """
        Check if Relion is available on the system by attempting to run `relion --help`.
        Exits the program if Relion is not found.
        """
        try:
            result = subprocess.run('relion --help', shell=True, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Standard Error:\n{e.stderr}")
            exit()          

    def report_box_sizes(self):
        """
        Report the box sizes calculated for the current binning factors defined in the pipeline.
        """

        print('\n[Initialize] Running Refinement Pipeline with Given Binnings and Resulting Box Sizes')
        for bin in self.binningList:        
        
            boxSize = self.return_new_box_size(bin)
            print('[Initialize] Box Size: {} @ bin={}'.format(boxSize,bin))  

    def return_new_box_size(self, bin: float):
        """
        Calculate the new box size based on the given binning factor.

        Args:
            bin: Input binning factor.
        Returns:
            int: The closest box size from the predefined list.
        """        

        boxSize = int( (self.params['resolutions']['box_scaling'] * float(self.params['refine3D']['particle_diameter']) ) / (float(self.params['resolutions']['angpix']) * bin) )
        index = np.searchsorted(self.boxSizes, boxSize, side='right')

        return self.boxSizes[index]       

    def read_json_params_file(self, json_fname: str):
        """
        Read parameters from a JSON file and initialize the binning list.

        Args:
            json_fname: Path to the JSON file containing pipeline parameters.
        """        

        self.params = self.read_json(json_fname)

        self.binningList = json.loads(self.params['resolutions']['binning_list'])
        self.binning = self.binningList[0]

        # Report Box Sizes for Refinement Experiment
        if self.binning is not None:
            self.report_box_sizes()

    def read_json_directories_file(self, json_fname: str):
        """
        Read output directories from a JSON file.

        Args:
            json_fname: Path to the JSON file containing output directories.
        """        

        self.outputDirectories = self.read_json(json_fname) 

    def read_json(self, json_fname: str):
        """
        Read data from a JSON file.

        Args:
            json_fname: Path to the JSON file
        Returns:
            dict: Parsed JSON data.
        """

        try:
            readFile = open(json_fname)
            outData = json.load(readFile)
        except:
            outData = {}

        return outData

    def parse_params(self, job, step: str):
        """
        Parse parameters from the JSON file and set them for a given job.

        Args:
            job: A pipeline job object.
            step (str): The step of the pipeline to retrieve parameters for.

        Returns:
            job: The job with updated parameters.
        """


        for key,value in self.params[step].items():
            job.joboptions[key].value = value
        return job
    
    def run_job(self, job, 
                jobName: str, 
                jobTag: str, 
                classifyStep: str = None, 
                keepClasses: list = None):
        """
        Run a job and handle its completion status.

        Args:
            job: A pipeline job object.
            jobName: Name of the job.
            jobTag: Tag to identify the job in logs.
            classifyStep (optional): Classification step to stop at, if provided.
            keepClasses (optional): List of classes to keep after classification.
        """        

        if not self.check_if_job_already_completed(job,jobName):

            # Run Import Tomograms Job
            print(f'\n[{jobTag}] Starting Job...')

            # Run Import Job
            self.myProject.run_job(job)

            # Wait up to 24 hours for the job to finish
            result = job_manager.wait_for_job_to_finish(job)

            print('[{}] Job Complete!'.format(jobTag))
            print('[{}] Job Result :: '.format(jobTag) + result)

            if result == 'Failed': print(f'{jobTag} Failed!...\n'); exit()

            self.outputDirectories[jobName] = job.output_dir
            self.save_new_output_directory()

            # Automatically Exit if We're Performing Several Rounds of Classification
            if classifyStep is not None:
                exit()         

            if keepClasses is not None: 
                self.custom_select(self.find_final_iteration(), keepClasses=keepClasses)    

    def get_resolution(self,job, job_name: str):
        """
        Extract the resolution from the job output logs.

        Args:
            job: A pipeline job object.
            job_name: Name of the job.
        Returns:
            int: The resolution value extracted from the logs.
        """        

        # Define a regular expression pattern to match floating point numbers
        pattern = r"\d+\.\d+"

        if job_name == 'reconstruct_particles' or job_name == 'post_process': 
            sub_string = 'RESOLUTION'
        else:                                  
            sub_string = 'Final resolution'

        with open(job.output_dir + 'run.out','r') as file:
            for line in file:
                if sub_string in line:
                    resolution = int(float(re.search(pattern, line).group()))
                    print(line)
        
        return resolution

    def find_final_iteration(self):
        """
        Find the final iteration file based on the highest iteration number.

        Returns:
            str: Path to the final iteration star file.
        """        

        # Find the Final Iteration 
        iterationStarFiles = glob.glob(self.tomo_class3D_job.output_dir + 'run_*_data.star')
        maxIterationStarFile = max(iterationStarFiles, key=lambda x: int(re.search(r'_it(\d+)_', x).group(1)))
        self.maxIter = int(re.search(r'it(\d+)', maxIterationStarFile).group(1))
        return maxIterationStarFile
    
    def find_best_particle_class(self):
        """
        Find the best particle class based on the maximum class distribution.

        Returns:
            tuple: (class index, path to MRC file of the best class)
        """        

        # Find the Final Iteration Model Star File and Pull out the Iteraiton Number 
        iterationStarFiles = glob.glob(self.tomo_class3D_job.output_dir + 'run_*_model.star')
        maxIterationStarFile = max(iterationStarFiles, key=lambda x: int(re.search(r'_it(\d+)_', x).group(1)))
        maxIter = int(re.search(r'it(\d+)', maxIterationStarFile).group(1))

        # Read the Corresponding Classification Star File
        classification = starfile.read(maxIterationStarFile)

        # Pull out the Max Class Index and Corresponding MRC - Reconstruction 
        maxClassIndex = classification['model_classes']['rlnClassDistribution'].idxmax() + 1
        maxClassMrc = self.tomo_class3D_job.output_dir  + 'run_it{:03}_class{:03}.mrc'.format(maxIter,maxClassIndex)

        return (maxClassIndex, maxClassMrc)

    def update_job_binning_box_size(self, binInd: int):
        """
        Update jobs with new binning and box size parameters.

        Args:
            binInd: Index of the binning factor to use.
        """        

        # Update New Binning / Resolution 
        self.binning = self.binningList[binInd]
        boxSize = self.return_new_box_size(self.binning)

        # Update Job with New Binning
        self.reconstruct_job.joboptions['binfactor'].value = self.binning
        self.pseudo_subtomo_job.joboptions['binfactor'].value = self.binning        

        # Define New Box Size Based on User Defined Incremental Scaling
        self.reconstruct_job.joboptions['box_size'].value = boxSize
        self.pseudo_subtomo_job.joboptions['box_size'].value = boxSize        

        # Set Crop Box Size to Half of Box Size
        if self.reconstruct_job.joboptions['crop_size'].value > 0: 
            self.reconstruct_job.joboptions['crop_size'].value = int(boxSize / 2)
            self.pseudo_subtomo_job.joboptions['crop_size'].value = int(boxSize / 2)        

    def get_new_sampling(self,currentSampling: str):
        """
        Get the next finer sampling angle based on the current one.

        Returns:
            str: The next finer sampling angle.
        """        

        currentSamplingIndex = self.sampling.index(currentSampling)

        return self.sampling[currentSamplingIndex + 1]
        
    def save_new_output_directory(self):
        """
        Save the updated output directories to the JSON file.
        """        

        with open('output_directories.json', 'w') as outFile: 
            json.dump(self.outputDirectories,outFile,indent=4)  

    def check_if_job_already_completed(self, job, job_name: str):
        """
        Check if a job has already been completed by looking for its output directory.

        Args:
            job: A pipeline job object.
            job_name: Name of the job.

        Returns:
            bool: True if the job is already completed, False otherwise.
        """        

        try: 
            job.output_dir = self.outputDirectories[job_name]
            return True
        except: 
            return False

    def check_custom_job_name(self,
                              baseJobName: str,
                              customStep: str ):
        """
        Generate a custom job name based on the base job name and an optional custom step.

        Args:
            baseJobName: The base name of the job.
            customStep: An optional custom step name.

        Returns:
            str: The generated job name.
        """        

        if customStep is not None:
            jobName = f'{customStep}_{baseJobName}_bin{self.binning}'
            customStep = customStep + '_'
        else:
            jobName = f'{baseJobName}_bin{self.binning}'
            customStep = ''
        
        return jobName            

    # Subset Selection Job
    def initialize_selection(self,selectStep: str =' '):
        """
        Initialize the selection job for selecting particles.

        Args:
            selectStep (optional): An optional step name for the selection process.
        """        

        self.tomo_select_job = select_job.RelionSelectOnValue()
        self.tomo_select_job.joboptions['select_label'].value = "rlnClassNumber" 

        try: self.tomo_select_job.output_dir = self.outputDirectories[self.check_custom_job_name('select',selectStep)]
        except: pass


    # Select Class Job - Pick class with Largest Distribution
    def run_subset_select(self, 
                          keepClasses: list = None, 
                          selectStep: str = None ):
        """
        Run the subset selection job to pick classes with the largest distribution.

        Args:
            keepClasses (optional): List of classes to keep after selection.
            selectStep (optional): An optional step name for the selection process.
        """        

        jobName = self.check_custom_job_name('select',selectStep) 
        self.run_job(self.tomo_select_job, jobName, f'Subset Selection', keepClasses=keepClasses)            

    # Edit the Selection Job For the Pre-defined Best Class and Apply top 
    def custom_select(self, 
                     classPath: str, 
                     keepClasses: list ):
        """
        Perform a custom selection based on the pre-defined best class and selected classes.

        Args:
            classPath: Path to the class file to select from.
            keepClasses: List of classes to keep.
        """        

        particlesFile = starfile.read(classPath)

        optics = particlesFile['optics']
        particles = particlesFile['particles']

        # I need to Pull out Data Optics
        filteredParticles = particles[particles['rlnClassNumber'].isin(keepClasses)]

        starfile.write({'optics':optics, 'particles':filteredParticles}, self.tomo_select_job.output_dir + 'particles.star')            

    # Mask Creation Job
    def initialize_mask_create(self):   
        """
        Initialize the mask creation job with parameters from the JSON file.
        """        

        self.mask_create_job = maskcreate_job.RelionMaskCreate()
        self.mask_create_job = self.parse_params(self.mask_create_job,'mask_create')

        try: self.mask_create_job.output_dir = self.outputDirectories[f"mask_create_bin{self.binning}"]
        except: pass    

        self.initialize_post_process()

    def initialize_post_process(self):
        """
        Initialize the post-processing job with default settings.
        """        

        self.post_process_job = postprocess_job.PostprocessJob()
        self.post_process_job.joboptions['angpix'].value = -1

    def run_post_process(self):
        """
        Run the post-processing job to finalize the results.
        """        

        jobName = f'post_process_bin{self.binning}'
        self.run_job(self.post_process_job, jobName, 'Post Process')              

    # Create Mask with Estimated Isonet Contour Value
    def run_mask_create(self):
        """
        Run the mask creation job with an automatically estimated isocontour value.
        Also update related jobs with the newly created mask.
        """        

        # Estimate Mask Isocontour
        with  mrcfile.open(self.mask_create_job.joboptions['fn_in'].value) as file:
            autoContour = np.percentile( file.data.flatten(), 98)
            self.mask_create_job.joboptions['inimask_threshold'].value = str(autoContour)

        jobName = f'mask_create_bin{self.binning}'
        self.run_job(self.mask_create_job, jobName, 'Mask Create')   

        # Update The Reconstruction, Refinement and Classification Job with the New Mask    
        self.tomo_refine3D_job.joboptions['fn_mask'].value = self.mask_create_job.output_dir + 'mask.mrc' 
        try:    
            self.post_process_job.joboptions['fn_mask'].value = self.mask_create_job.output_dir + 'mask.mrc'            
            self.tomo_class3D_job.joboptions['fn_mask'].value = self.mask_create_job.output_dir + 'mask.mrc'              
        except: pass        

    def write_mrc(self, tomo, fname, voxelSize=1, dtype=None, no_saxes=True):
        """
        Write a 3D tomogram to an MRC file.

        Args:
            tomo (np.ndarray): The 3D tomogram data.
            fname (str): The filename to save the MRC file as.
            voxelSize (float, optional): The voxel size in Angstroms. Defaults to 1.
            dtype (np.dtype, optional): The data type to save the tomogram as. Defaults to None.
            no_saxes (bool, optional): Whether to swap axes before writing. Defaults to True.
        """        

        with mrcfile.new(fname, overwrite=True) as mrc:
            if dtype is None:
                if no_saxes:
                    mrc.set_data(np.swapaxes(tomo, 0, 2))
                else:
                    mrc.set_data(tomo)
            else:
                if no_saxes:
                    mrc.set_data(np.swapaxes(tomo, 0, 2).astype(dtype))
                else:
                    mrc.set_data(tomo.astype(dtype))
            mrc.voxel_size.flags.writeable = True
            mrc.voxel_size = (voxelSize, voxelSize, voxelSize)
            mrc.set_volume()         
            
    