from pipeliner.jobs.relion import select_job, maskcreate_job, postprocess_job
import pipeliner.job_manager as job_manager
import glob, starfile, json, re, mrcfile
from scipy import ndimage
import subprocess, os
import numpy as np
import warnings

# Define Custom Postprocess Job to Avoid Future Warnings
from pipeliner.job_options import JobOptionValidationResult
from pipeliner.jobs.relion.postprocess_job import PostprocessJob
from typing import List

class CustomPostprocessJob(PostprocessJob):
    """
    Custom Post Processing Job to Supress the Requirement for Auto Sharpening
    """
    def additional_joboption_validation(self) -> List[JobOptionValidationResult]:
        return []
##############################################################################

# Suppress all future warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

class PipelineHelper:
    """
    A helper class for managing and running a Relion-based pipeline in a cryo-EM project.
    """    

    def __init__(self, inProject, requireRelion = True):
        """
        Initialize the PipelineHelper with the given project.

        Args:
            inProject: The project instance that manages the pipeline.
        """

        if requireRelion:
            self.check_if_relion_is_available()

        self.myProject = inProject

        # Define sampling angles and box sizes for various stages of the pipeline.
        self.sampling = ['30 degrees', '15 degrees', '7.5 degrees', '3.7 degrees', '1.8 degrees', '0.9 degrees',\
                         '0.5 degrees', '0.2 degrees', '0.1 degrees']

        # Extract numeric values from self.sampling and convert them to floats
        self.sampling_degrees = [float(angle.split()[0]) for angle in self.sampling]                         

        self.boxSizes = [24, 32, 36, 40, 44, 48, 52, 56, 60, 64, 72, 84, 96, 100, 104, 112, 120, 128,\
                         132, 140, 168, 180, 192, 196, 208, 216, 220, 224, 256, 288, 300, 320, 352, 360,\
                         384, 416, 440, 448, 480, 480, 512, 540, 560, 576, 588, 600, 630, 648, 672, 686, 700]

        # self.initialize_post_process()

        # Initialize binning factor
        self.binning = None      

        # Initialize Jobs
        self.reconstruct_job = None
        self.pseudo_subtomo_job = None
        self.mask_create_job = None
        self.post_process_job = None
        self.tomo_select_job = None

    def print_pipeline_parameters(self, process: str, header: str = None, **kwargs):
        """
        Pretty-print pipeline parameters using Rich and optionally save them to JSON.

        Args:
            process: The name of the pipeline process or step.
            header: Optional header name under which parameters will be saved in JSON.
            **kwargs: Arbitrary parameters. If 'file_name' is given, parameters are also saved.
        """
        import os
        from py2rely.utils.progress import get_console
        from rich.syntax import Syntax
        from rich.table import Table
        from rich.panel import Panel

        console = get_console()
        file_name = kwargs.pop("file_name", None)

        # Prepare data
        json_data = {header: kwargs} if header else kwargs

        # ---- Rich summary ----
        console.rule(f"[bold cyan]{process} Parameters Summary")

        # Nicely formatted parameter table
        table = Table(show_header=True, header_style="bold magenta", expand=False)
        table.add_column("Parameter", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        for key, value in kwargs.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, indent=2)
            table.add_row(str(key), str(value))

        console.print(table)

        # ---- Save to JSON (quietly) ----
        if file_name:
            if os.path.exists(file_name):
                with open(file_name, "r") as json_file:
                    existing_data = json.load(json_file)
            else:
                existing_data = {}

            existing_data.update(json_data)
            with open(file_name, "w") as json_file:
                json.dump(existing_data, json_file, indent=4)

            # Print confirmation *after* summary is fully shown
            console.print(
                f"\n[green]Parameters saved to[/green] [b]{file_name}[/b]"
                + (f" under header [cyan]{header}[/cyan]" if header else "")
            )

    def check_if_relion_is_available(self):
        """
        Check if Relion is available on the system by attempting to run `relion --help`.
        Exits the program if Relion is not found.
        """
        try:
            result = subprocess.run('relion_refine --help', shell=True, check=True, capture_output=True, text=True)
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

        # Check if the provided JSON file path exists. If not, raise a FileNotFoundError 
        # with a message to notify the user to check the path.
        if not os.path.exists(json_fname):
            raise FileNotFoundError(f"The file '{json_fname}' does not exist. Please check the path and try again.")

        #  Read the contents of the JSON file and store it in the 'params' attribute.
        # This assumes the method `read_json` is defined elsewhere to handle reading the file.
        self.params = self.read_json(json_fname)

        # Extract the binning list from the 'resolutions' section of the parameters.
        # The binning list is stored as a JSON-formatted string, so it's parsed using `json.loads`.
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
        history_fname = json_fname.replace('.json', '_history.json')
        self.historyDirectories = self.read_json(history_fname)     

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
        except Exception as e:
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
            if key in job.joboptions:
                job.joboptions[key].value = value
            else:
                print(f"Warning: Key '{key}' not found in job options, not adding.")
        return job

    def set_new_tomograms_starfile(self, tomogram_path):

        # Check if 'tomograms.star' exists in the specified directory
        path1 = os.path.join(tomogram_path, 'tomograms.star')
        if os.path.exists(path1):
            self.outputDirectories['reconstruct_tomograms'] = path1
        elif os.path.exists(tomogram_path):
            self.outputDirectories['reconstruct_tomograms'] = tomogram_path
        else:
            # If neither the file nor the directory exists,
            # raise a FileNotFoundError with a detailed message
            FileNotFoundError(f"Error: Neither {path1} nor {tomogram_path} exists.")
    
    def run_job(self, 
                job, 
                jobName: str, 
                jobTag: str, 
                jobIter: str = None,
                classifyStep: bool = False, 
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

        # Set Timeout to XX hours
        nDays = 14
        nHours = nDays * 24

        # Assume We Are Re-Running a Job if JobIter is not None
        if not self.check_if_job_already_completed(job,jobName) or jobIter:

            # Run Import Tomograms Job
            print(f'\n[{jobTag}] Starting Job...')

            # Run Import Job
            self.myProject.run_job(job)

            # Wait up to 24 hours for the job to finish
            result = job_manager.wait_for_job_to_finish(job, timeout=nHours * 3600)

            # Print Results
            print('[{}] Job Complete!'.format(jobTag))
            print('[{}] Job Result :: '.format(jobTag) + result)

            # Exit If Job Fails
            if result == 'Failed': print(f'{jobTag} Failed!...\n'); exit()

            # Ensure the binning key exists before assigning the job output directory
            bin_key = f'bin{self.binning}'
            if bin_key not in self.outputDirectories:
                self.outputDirectories[bin_key] = {}

            # Save Job Name to Output Directory (Main Pipeline)
            self.outputDirectories[bin_key][jobName] = job.output_dir

            # Log All the Repititions for Each Process
            # if jobIter is not None:
            #     self.historyDirectories[bin_key][jobName][jobIter] = job.output_dir
            # else:
            #     self.historyDirectories[bin_key][jobName] = {}
            #     self.historyDirectories[bin_key][jobName][jobIter] = job.output_dir
            if bin_key not in self.historyDirectories:
                self.historyDirectories[bin_key] = {}
            if jobName not in self.historyDirectories[bin_key]:
                self.historyDirectories[bin_key][jobName] = {}
                # Assume this is the first iteration for this job at this resolution
                jobIter = 'iter1'
            self.historyDirectories[bin_key][jobName][jobIter] = job.output_dir                
                # self.outputDirectories[bin_key][jobName+'_history'][jobIter] = job.output_dir

            # Save the new output directory
            self.save_new_output_directory()     

            # Automatically Exit if Classification (User Needs to Export Best Class)
            # if classifyStep:
            #         exit()

            if keepClasses is not None: 
                self.custom_select(self.find_final_iteration(), keepClasses=keepClasses)   
        else: 
            job.output_dir = self.outputDirectories[f'bin{self.binning}'][jobName]
         

    def get_resolution(self, job, 
                      job_name: str = None):
        """
        Extract the resolution from the job output logs.

        Args:
            job: A pipeline job object.
            job_name: Name of the job.
        Returns:
            int: The resolution value extracted from the logs.
        """       

        # Define a regular expression pattern to match floating point numbers
        pattern = r"\d+\.\d+|\d+"

        if job_name == 'reconstruct_particles' or job_name == 'post_process': 
            sub_string = 'RESOLUTION'
        else:                                  
            sub_string = 'Final resolution'

        with open(job.output_dir + 'run.out','r') as file:
            for line in file:
                if sub_string in line:
                    new_resolution = int(float(re.search(pattern, line).group()))
                    print(line) 

        # Check to See if Resolution is Improving. If not, terminate the pipeline early
        if job_name == 'post_process' and new_resolution >= self.current_resolution * 1.5:
            # Exit Condition, tell user resolution is divering. Consider more classification.
            raise ValueError("Resolution is diverging. Consider more classification.")
        elif job_name == 'post_process':
            self.current_resolution = new_resolution
        
        return new_resolution

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
    
    def find_best_particle_class(self, class3D_job):
        """
        Find the best particle class based on the maximum class distribution.

        Returns:
            tuple: (class index, path to MRC file of the best class)
        """        

        # Find the Final Iteration Model Star File and Pull out the Iteraiton Number 
        iterationStarFiles = glob.glob(class3D_job.output_dir + 'run_*_model.star')
        maxIterationStarFile = max(iterationStarFiles, key=lambda x: int(re.search(r'_it(\d+)_', x).group(1)))
        maxIter = int(re.search(r'it(\d+)', maxIterationStarFile).group(1))

        # Read the Corresponding Classification Star File
        classification = starfile.read(maxIterationStarFile)

        # Pull out the Max Class Index and Corresponding MRC - Reconstruction 
        maxClassIndex = classification['model_classes']['rlnClassDistribution'].idxmax() + 1
        maxClassMrc = class3D_job.output_dir  + 'run_it{:03}_class{:03}.mrc'.format(maxIter,maxClassIndex)

        return (maxClassIndex, maxClassMrc)

    def update_job_binning_box_size(self,
                                    reconstruct_particle_job,
                                    pseudo_subtomo_job, 
                                    binInd: int,
                                    binningFactor: int = None):
        """
        Update jobs with new binning and box size parameters.

        Args:
            binInd: Index of the binning factor to use.
        """        

        # Update New Binning / Resolution 
        if binningFactor is None:   self.binning = self.binningList[binInd]
        else:                       self.binning  = binningFactor
        boxSize = self.return_new_box_size(self.binning)

        # Update Job with New Binning
        reconstruct_particle_job.joboptions['binfactor'].value = self.binning
        pseudo_subtomo_job.joboptions['binfactor'].value = self.binning 

        # Only Set Crop Size to Box Size at Bin = 1, Else Keep at -1
        if self.binning == 1:
            reconstruct_particle_job.joboptions['crop_size'].value = boxSize
            pseudo_subtomo_job.joboptions['crop_size'].value = boxSize
            scale = 1.5
        else:
            scale = 1

        # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job  
        index = np.searchsorted(self.boxSizes, boxSize * scale, side='left')
        reconstruct_particle_job.joboptions['box_size'].value = self.boxSizes[index]
        pseudo_subtomo_job.joboptions['box_size'].value = self.boxSizes[index]

        # Print the Current Reconstruction Crop and Box Size  
        print('Current Reconstruct Box Size: ', self.reconstruct_particle_job.joboptions['box_size'].value)
        print('Current Reconstruct Crop Size: ', self.reconstruct_particle_job.joboptions['crop_size'].value)

    def get_new_sampling(self, job, update_local=True):
        """
        Get the next finer sampling angle based on the current one.

        Returns:
            str: The next finer sampling angle.
        """

        # Estimate Angular Sampling
        resolution = self.binning * self.params['resolutions']['angpix'] * 2
        radians = np.arctan(resolution / self.params['refine3D']['particle_diameter'])
        degrees = np.degrees(radians)

        # Find the smallest sampling angle that rounds up to or is greater than the computed degrees
        rounded_angle = min([angle for angle in self.sampling_degrees if angle >= degrees])
        local_rounded_angle = min([angle for angle in self.sampling_degrees if angle >= degrees])

        # We Only Keep Float for 15 or 30 degree search increment
        if rounded_angle > 10:
            rounded_angle = int(rounded_angle)

        # We Only Need to Scale Sampling if It's Less than Course Value
        job.joboptions['sampling'].value = f"{rounded_angle} degrees"
            
        if update_local: 
            job.joboptions['auto_local_sampling'].value = f"{local_rounded_angle} degrees"

        # Get the corresponding sampling string
        return f"{rounded_angle} degrees"
        
    def save_new_output_directory(self):
        """
        Save the updated output directories to the JSON file.
        """
        with open('output_directories.json', 'w') as outFile: 
            json.dump(self.outputDirectories,outFile,indent=4)  

        with open('output_directories_history.json', 'w') as outFile: 
            json.dump(self.historyDirectories,outFile,indent=4)              

    def check_if_job_already_completed(self, 
                                      job, 
                                      job_name: str):
        """
        Check if a job has already been completed by looking for its output directory.

        Args:
            job: A pipeline job object.
            job_name: Name of the job.

        Returns:
            bool: True if the job is already completed, False otherwise.
        """
        # Check if the job_name exists at the top level
        if job_name in self.outputDirectories:
            return True
        # Check if the binning key exists and then if the job_name exists within that binning
        elif f'bin{self.binning}' in self.outputDirectories and job_name in self.outputDirectories[f'bin{self.binning}']:
            return True
        else:
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
            jobName = f'{baseJobName}_{customStep}'
            customStep = '_' + customStep 
        else:
            jobName = f'{baseJobName}'
            customStep = ''
        
        return jobName            

    # Subset Selection Job
    def initialize_selection(self, selectStep: str =' '):
        """
        Initialize the selection job for selecting particles.

        Args:
            selectStep (optional): An optional step name for the selection process.
        """
        self.tomo_select_job = select_job.RelionSelectOnValue()
        self.tomo_select_job.joboptions['select_label'].value = "rlnClassNumber" 

        try: self.tomo_select_job.output_dir = self.outputDirectories[f'bin{self.binning}'][self.check_custom_job_name('select',selectStep)]
        except: pass

    # Select Class Job - Pick class with Largest Distribution
    def run_subset_select(self, 
                          keepClasses: list = None, 
                          selectStep: str = None,
                          rerunSelect: bool = False ):
        """
        Run the subset selection job to pick classes with the largest distribution.

        Args:
            keepClasses (optional): List of classes to keep after selection.
            selectStep (optional): An optional step name for the selection process.
        """
        if rerunSelect: selectJobIter = self.return_job_iter(f'bin{self.binning}', 'select')
        else:           selectJobIter = None
        self.run_job(self.tomo_select_job, 'select', f'Subset Selection', keepClasses=keepClasses, jobIter = selectJobIter )            

    # Edit the Selection Job For the Pre-defined Best Class and Apply top 
    def custom_select(self, 
                     classPath: str, 
                     keepClasses: list,
                     uniqueExport: str = None ):
        """
        Perform a custom selection based on the pre-defined best class and selected classes.

        Args:
            classPath: Path to the class file to select from.
            keepClasses: List of classes to keep.
        """

        # Read Particles File and Parse Optics + Particles Group
        particlesFile = starfile.read(classPath)
        optics = particlesFile['optics']
        particles = particlesFile['particles']

        # Only Extract the Particles with Desired Class
        filteredParticles = particles[particles['rlnClassNumber'].isin(keepClasses)]
        
        # Relion5 Output - See if General Exists (Specifies Whether Sub-Tomograms is 2D MRCs Stacks)
        try:
            general = particlesFile['general']
            newParticles = {'general': general, 'optics':optics, 'particles':filteredParticles}
        # Relion4 Output 
        except:
            newParticles = {'optics':optics, 'particles':filteredParticles}       

        # Define Write Directory if Not intended to be written in new directory
        if uniqueExport is None:
            uniqueExport = self.tomo_select_job.output_dir + 'particles.star' 

        # Remove Old Particles Directory to Be used for next process
        os.remove(self.tomo_select_job.output_dir + 'particles.star')
        starfile.write( newParticles, uniqueExport)            

    # Post Processing Job
    def initialize_post_process(self):
        """
        Initialize the post-processing job with default settings.
        """        
        # self.post_process_job = postprocess_job.PostprocessJob()
        self.post_process_job = CustomPostprocessJob()
        self.post_process_job.joboptions['angpix'].value = -1
        self.post_process_job.joboptions['do_auto_bfac'].value = 'no'

        # Initialize Current Resolution as 1 micron
        self.current_resolution = 999

    # Post Processing Job
    def run_post_process(self,
                         rerunPostProcess: bool = False):
        """
        Run the post-processing job to finalize the results.
        """        
        # If Completed Post Process Already Exists, Start Logging New Iterations if rerunPostProcess is True. 
        if rerunPostProcess: postProcessJobIter = self.return_job_iter(f'bin{self.binning}', 'post_process')
        else:                postProcessJobIter = None
        # self.post_process_job.joboptions['autob_lowres'].value = self.binning * self.params['resolutions']['angpix'] * 3
        self.run_job(self.post_process_job, 'post_process', 'Post Process', jobIter = postProcessJobIter)  

    # Mask Creation Job
    def initialize_mask_create(self):
        """
        Initialize the mask creation job with parameters from the JSON file.
        """
        self.mask_create_job = maskcreate_job.RelionMaskCreate()
        self.mask_create_job = self.parse_params(self.mask_create_job,'mask_create')

        try: self.mask_create_job.output_dir = self.outputDirectories[f'bin{self.binning}'][f"mask_create"]
        except: pass    

        self.initialize_post_process()                    

    # Create Mask with Estimated Isonet Contour Value
    def run_mask_create(self, 
                        refine3D_job, 
                        class3D_job,
                        autoContour: bool = True,
                        rerunMaskCreate: bool = False):
        """
        Run the mask creation job with an automatically estimated isocontour value.
        Also update related jobs with the newly created mask.
        """        
        # Estimate Mask Isocontour if autoContour is True
        if autoContour:
            with  mrcfile.open(self.mask_create_job.joboptions['fn_in'].value) as file:
                autoContour = np.percentile( file.data.flatten(), 98)
                self.mask_create_job.joboptions['inimask_threshold'].value = str(autoContour)

        # If Completed Mask Create Already Exists, Start Logging New Iterations if rerunMaskCreate is True. 
        if rerunMaskCreate: maskCreateJobIter = self.return_job_iter(f'bin{self.binning}', 'mask_create')
        else:               maskCreateJobIter = None
        self.run_job(self.mask_create_job, 'mask_create', 'Mask Create', jobIter = maskCreateJobIter)   

        try:    
            self.post_process_job.joboptions['fn_mask'].value = self.mask_create_job.output_dir + 'mask.mrc' 

            # Update The Refinement and Classification Job with the New Mask (If Available)    
            refine3D_job.joboptions['fn_mask'].value = self.mask_create_job.output_dir + 'mask.mrc' 
            class3D_job.joboptions['fn_mask'].value = self.mask_create_job.output_dir + 'mask.mrc'
        except Exception as e: 
            pass

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
            
    # Find the Subgroup That Reflects 'binX/process/iterY' In The OutputDirectories Tree
    def get_subgroup(self, data, key_path, optional_path=None, delimiter='/'):
        key_path = f'{key_path}{"/" + optional_path if optional_path else ""}'
        keys = key_path.split(delimiter)
        subgroup = data
        for key in keys:
            subgroup = subgroup[key]
        return subgroup

    # Find the Subgroup That Reflects 'binX/process/iterY' In The OutputDirectories Tree
    def return_job_iter(self, binKey, jobName):

        # Check if the binKey and jobName exist in the outputDirectories
        if binKey in self.historyDirectories and jobName in self.historyDirectories[binKey]:
            
            # If jobName is already a dictionary, find the next iteration
            current_iters = sorted(self.historyDirectories[binKey][jobName].keys())
            last_iter = current_iters[-1]
            last_iter_num = int(last_iter.replace('iter', ''))
            return f'iter{last_iter_num + 1}'
        else:
            # If the jobName or binKey doesn't exist, return None
            return None


    def get_reconstruction_std(self, 
        reconstruction_path: str, 
        low_pass: float = -1, 
        save_vol: bool = False
    ):
        """
        Get the standard deviation of the reconstruction.
        """

        # Read the MRC file with header information
        with mrcfile.open(reconstruction_path, 'r') as mrc:
            vol = mrc.data.copy()
            voxel_size = mrc.voxel_size.x  # Assuming cubic voxels

        if low_pass > 0:
            # Calculate sigma for Gaussian filter
            # The relationship between resolution and Gaussian sigma
            # Resolution ≈ 2 * π * sigma * voxel_size
            sigma = low_pass / (2 * np.pi * voxel_size)
            
            # Apply Gaussian low-pass filter
            filtered_vol = ndimage.gaussian_filter(vol, sigma=sigma)

            # TODO : 
            # Try both np.std(vol) and np.std(filtered_vol) to see which one is better
            # How do I determine which is the better mask?

            if save_vol:
                self.write_mrc(filtered_vol, 'filtered_vol.mrc', voxel_size)

            return np.std(filtered_vol)
        else:        
            return np.std(vol)

    def get_half_fsc(self, post_process_path: str, target_fsc: float = 0.5):
        """
        Get the half FSC curve from the post-process job.
        """

        # Read the FSC curve and resolutions
        fsc_df = starfile.read(post_process_path + 'postprocess.star')
        curve =  fsc_df['fsc']['rlnFourierShellCorrelationCorrected']
        resolutions =  fsc_df['fsc']['rlnAngstromResolution']

        # Check for NaN values in the curve
        if (curve == '-nan').any():
            print('[WARNING] Post Processing is Corrupted (the FSC resolution curve contains NAN values)')
            print('Please Check the Refinement Results..\n')
            exit()

        # Find the index of the value closest to target_fsc
        closest_index = (np.abs(curve - target_fsc)).idxmin()

        # Get the resolution at the closest index
        closest_resolution = resolutions[closest_index]
        return closest_resolution



    # # Find the Subgroup That Reflects 'binX/process/iterY' In The OutputDirectories Tree
    # def return_job_iter(self, binKey, jobName):

    #     # Check if the binKey and jobName exist in the outputDirectories
    #     if binKey in self.outputDirectories and jobName in self.outputDirectories[binKey]:
    #         # If jobName is a string (e.g., 'job002'), set it as the first iteration
    #         if isinstance(self.outputDirectories[binKey][jobName], str):
    #             # Assign the current job to 'iter1'
    #             self.outputDirectories[binKey][jobName + '_history'] = {'iter1': self.outputDirectories[binKey][jobName]}
    #             return 'iter2'
            
    #         # If jobName is already a dictionary, find the next iteration
    #         current_iters = sorted(self.outputDirectories[binKey][jobName].keys())
    #         last_iter = current_iters[-1]
    #         last_iter_num = int(last_iter.replace('iter', ''))
    #         return f'iter{last_iter_num + 1}'
    #     else:
    #         # If the jobName or binKey doesn't exist, return None
    #         return None
