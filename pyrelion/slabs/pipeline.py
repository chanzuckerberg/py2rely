from pipeliner.jobs.relion import import_job, extract_job, class2D_job, select_job
from pyrelion.slabs.preprocess import default_parameters
from pyrelion.slabs.visualize import gallery
import pipeliner.job_manager as job_manager
import glob, starfile, json, re, mrcfile
import subprocess, os, glob
import warnings, subprocess
import numpy as np

# Suppress all future warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

class SlabAveragePipeline:

    def __init__(self,inProject):

        self.myProject = inProject

        self.check_if_relion_is_available()

        self.params = default_parameters.get_config()

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

    def print_pipeline_parameters(self, process, header=None, **kwargs):
        """
        Print pipeline parameters to the console and optionally save them to a JSON file
        under a specific header.

        Args:
            process: The name of the process or step in the pipeline.
            header: An optional header name under which the parameters will be saved in the JSON file.
            **kwargs: Arbitrary keyword arguments representing parameters to print or save.
                    If 'file_name' is provided in kwargs, parameters will be saved to a JSON file.
        """
        # Check if 'file_name' is provided in kwargs. If so, extract it and save the parameters to a JSON file.
        file_name = kwargs.pop('file_name', None)

        # Prepare the dictionary for saving or printing.
        json_data = {header: kwargs} if header else kwargs

        if file_name:

            # Read JSON File If Available
            if os.path.exists(file_name):
                with open(file_name, 'r') as json_file:
                    existing_data = json.load(json_file)
            else: 
                existing_data = {}
            existing_data.update(json_data)

            # Save the parameters to the specified JSON file with the same indentation.
            with open(file_name, 'w') as json_file:
                json.dump(existing_data, json_file, indent=4)

            # Print the file name and a confirmation message.
            print(f"\nParameters saved to {file_name} under the header '{header}'" if header else f"\nParameters saved to {file_name}")
        
        # Print the parameters in a JSON-formatted string with the same indentation.
        print(f"\n[{process}] Parameters (JSON format):\n")
        print(json.dumps(json_data, indent=4))            

    def read_json_params_file(self, json_fname):
        """
        Read parameters from a JSON file.

        Args:
            json_fname: Path to the JSON file containing pipeline parameters.
        """        

        # Check if the provided JSON file path exists. If not, raise a FileNotFoundError 
        # with a message to notify the user to check the path.
        if not os.path.exists(json_fname):
            raise FileNotFoundError(f"The file '{json_fname}' does not exist. Please check the path and try again.")        

        self.params = self.read_json(json_fname)

    def read_json_directories_file(self,json_fname):
        """
        Read output directories from a JSON file.

        Args:
            json_fname: Path to the JSON file containing output directories.
        """        
        self.outputDirectories = self.read_json(json_fname) 

    def read_json(self, json_fname):
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

    def parse_params(self,job,step):
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
    
    def run_job(self, job, jobName, jobTag, classifyStep = None, keepClasses = None):
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

            # We Want to Automatically Exit if We're Performing Several Rounds of Classification
            # if classifyStep is not None:
            #     exit()   
            # This is not true anymore      

            if keepClasses is not None: 
                self.custom_select(keepClasses=keepClasses)    
                
    def find_final_iteration(self, classPath):
        """
        Find the final iteration file based on the highest iteration number.

        Returns:
            str: Path to the final iteration star file.
        """              

        # Find the Final Iteration 
        iterationStarFiles = glob.glob( os.path.join('Class2D', classPath, 'run_*_data.star') )
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
        
    def save_new_output_directory(self):
        """
        Save the updated output directories to the JSON file.
        """        

        with open('output_directories.json', 'w') as outFile: 
            json.dump(self.outputDirectories,outFile,indent=4)  

    def check_if_job_already_completed(self, job, job_name):
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

    def check_custom_job_name(self,baseJobName,customStep):
        """
        Generate a custom job name based on the base job name and an optional custom step.

        Args:
            baseJobName: The base name of the job.
            customStep: An optional custom step name.

        Returns:
            str: The generated job name.
        """        

        if customStep is not None:
            jobName = f'{customStep}_{baseJobName}'
            customStep = customStep + '_'
        else:
            jobName = f'{baseJobName}'
            customStep = ''
        
        return jobName            
    
    def initialize_import_micrographs(self):

        self.import_micrographs_job = import_job.RelionImportMovies()
        self.import_micrographs_job = self.parse_params(self.import_micrographs_job,'import_micrographs')

    def run_import_micrographs(self):

        self.run_job(self.import_micrographs_job, 'import_micrographs', 'Import Micrographs')     

    def initialize_particle_extraction(self):

        self.extract_job = extract_job.RelionExtract()
        self.extract_job = self.parse_params(self.extract_job,'extract')

    def run_extract(self):

        self.run_job(self.extract_job, 'extract', f'Particle Extraction')
    
    def initialize_classification(self, 
                                  classifyMethod: str ='2DEM', 
                                  nr_iter: int = None):

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

        # Parse Paramters 
        self.class2D_job = self.parse_params(self.class2D_job,'class2D')    
        try: self.class2D_job.output_dir = self.outputDirectories[self.check_custom_job_name('class2D',classifyStep)]
        except: pass

    # Classify 3D Job 
    def run_class2D(self,classifyStep=None):

        try: 
            previous_jobs = glob.glob('Class2D/job*')
            classIter = len(previous_jobs) + 1
        except:
            classIter = 1

        jobName = f'class2D_iter{classIter}'
        self.run_job(self.class2D_job, jobName, f'2D Classification', classifyStep = classifyStep)

        class_job = self.class2D_job.output_dir.split('/')[1]
        final_class_averages = self.find_final_iteration(class_job).replace('data.star', 'classes.mrcs')

        # Plot the Class Averages
        gallery.class_average_gallery(final_class_averages) 
    
    # Subset Selection Job
    def initialize_selection(self,selectStep=''):

        self.tomo_select_job = select_job.RelionSelectOnValue()
        self.tomo_select_job.joboptions['select_label'].value = "rlnClassNumber" 

        try: self.tomo_select_job.output_dir = self.outputDirectories[self.check_custom_job_name('select',selectStep)]
        except: pass

    # Select Class Job - Pick class with Largest Distribution
    def run_subset_select(self, keepClasses=None, selectStep=None, classPath = None):

        jobName = self.check_custom_job_name(selectStep,'select') 
        self.classPath = classPath         
        self.run_job(self.tomo_select_job, jobName, f'Subset Selection', keepClasses=keepClasses)           

    def initialize_auto_selection(self, selectStep=''):

        self.auto_select_job = select_job.RelionSelectClass2DAuto()

        try: self.auto_select_job.output_dir = self.outputDirectories[self.check_custom_job_name('auto_select',selectStep)]
        except: pass

    # Select Class Job - Pick class with Largest Distribution
    def run_auto_select(self, selectStep=None):

        jobName = self.check_custom_job_name(selectStep,'auto_select')         
        self.run_job(self.auto_select_job, jobName, f'Auto Selection')                   

    # Edit the Selection Job For the Pre-defined Best Class and Apply top 
    def custom_select(self, keepClasses):

        particlesFile = starfile.read(self.classPath)

        optics = particlesFile['optics']
        particles = particlesFile['particles']

        # I need to Pull out Data Optics
        filteredParticles = particles[particles['rlnClassNumber'].isin(keepClasses)]

        starfile.write({'optics':optics, 'particles':filteredParticles}, self.tomo_select_job.output_dir + 'particles.star')            