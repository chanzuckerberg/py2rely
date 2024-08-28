from pipeliner.jobs.tomography.relion_tomo import tomo_reconstruct_job, tomo_reconstructparticle_job, tomo_pseudosubtomo_job, tomo_refine3D_job, tomo_initialmodel_job, tomo_class3D_job
from pipeliner.jobs.relion import select_job, maskcreate_job, postprocess_job
from relion_sta_pipeline.utils.sta_tools import PipelineHelper
import pipeliner.job_manager as job_manager
import glob, starfile, json, re, mrcfile
import subprocess, os
import numpy as np
import warnings

class Relion5Pipeline(PipelineHelper):
    """
    A class that extends PipelineHelper to provide specific methods for 
    initializing and running various jobs in a Relion5 cryo-ET pipeline.
    """    

    def __init__(self, inProject: str):
        """
        Initialize the Relion5Pipeline with the given project.

        Args:
            inProject: The project instance that manages the pipeline.
        """        
        super().__init__(inProject)

        # Initialize Jobs
        self.tomo_reconstruct_job = None
        self.reconstruct_particle_job = None
        self.pseudo_subtomo_job = None        
        self.tomo_class3D_job = None   
        self.tomo_refine3D_job = None
        self.initial_model_job = None
        self.tomo_class3D_job = None

    def initialize_reconstruct_tomograms(self):
        """
        Initialize the job for reconstructing tomograms. The job parameters are parsed 
        and set according to the configuration specified in the 'reconstruct_tomograms' 
        section of the JSON file.
        """        
        self.tomo_reconstruct_job = tomo_reconstruct_job.RelionTomoReconstructJob()
        self.tomo_reconstruct_job = self.parse_params(self.tomo_reconstruct_job,'reconstruct_tomograms')

    def run_reconstruct_tomograms(self):
        """
        Run the tomogram reconstruction job and handle its execution.
        """        
        self.run_job(self.tomo_reconstruct_job, 'reconstruct_tomograms', 'Reconstruct Tomograms')

    def initialize_reconstruct_particle(self, includeSphereMask: bool = False):
        """
        Initialize the job for reconstructing particles. The job parameters are parsed 
        and set according to the configuration specified in the 'reconstruct' section 
        of the JSON file. Optionally, a spherical mask can be created for the initial 
        reconstruction.

        Args:
            includeSphereMask: If True, creates an initial spherical mask. Defaults to False.
        """
        self.reconstruct_particle_job = tomo_reconstructparticle_job.RelionReconstructParticleJob()
        self.reconstruct_particle_job = self.parse_params(self.reconstruct_particle_job,'reconstruct')  

        self.reconstruct_particle_job.joboptions['binfactor'].value = self.binning
        self.reconstruct_particle_job.joboptions['box_size'].value = self.return_new_box_size(self.binning)
        self.reconstruct_particle_job.joboptions['in_tomograms'].value = self.outputDirectories['reconstruct_tomograms'] + 'tomograms.star'  

        # Apply Output Directories from Previous Job       
        try: self.pseudo_subtomo_job.output_dir = self.outputDirectories[f'bin{self.binning}']['reconstruct']
        except: pass            

        # Create Spherical Mask for Initial Reconstruction 
        if includeSphereMask: 
            self.create_initial_spherical_mask()        

    def run_reconstruct_particle(self):
        """
        Run the particle reconstruction job and handle its execution.
        """            
        self.run_job(self.reconstruct_particle_job, 'reconstruct', 'Reconstruct Particles')

    def initialize_pseudo_tomos(self):
        """
        Initialize the job for generating pseudo-subtomograms. The job parameters are 
        parsed and set according to the configuration specified in the 'pseudo_subtomo' 
        section of the JSON file.
        """        
        self.pseudo_subtomo_job = tomo_pseudosubtomo_job.RelionPseudoSubtomoJob()
        self.pseudo_subtomo_job = self.parse_params(self.pseudo_subtomo_job,'pseudo_subtomo')
        
        self.pseudo_subtomo_job.joboptions['binfactor'].value = self.binning
        self.pseudo_subtomo_job.joboptions['box_size'].value = self.return_new_box_size(self.binning)        
        self.pseudo_subtomo_job.joboptions['in_tomograms'].value = self.outputDirectories['reconstruct_tomograms'] + 'tomograms.star'

        # Apply Output Directories from Previous Job       
        try: self.pseudo_subtomo_job.output_dir = self.outputDirectories[f'bin{self.binning}']['pseudo_subtomo']
        except: pass

    def run_pseudo_subtomo(self):
        """
        Run the pseudo-subtomogram generation job and handle its execution.
        """        
        self.run_job(self.pseudo_subtomo_job, 'pseudo_subtomo', f'Psuedo Tomogram Generation @ bin={self.binning}')

    def initialize_initial_model(self):
        """
        Initialize the job for generating the initial 3D model. The job parameters are 
        parsed and set according to the configuration specified in the 'initial_model' 
        section of the JSON file.
        """        
        self.initial_model_job = tomo_initialmodel_job.RelionTomoInimodelJob()
        self.initial_model_job = self.parse_params(self.initial_model_job,'initial_model')

    def run_initial_model(self):
        """
        Run the initial 3D model generation job and handle its execution.
        """
        self.run_job(self.initial_model_job, 'initial_model', '3D Initial Model')  

    def initialize_auto_refine(self, refineStep: str = None):
        """
        Initialize the job for automatic 3D refinement. The job parameters are parsed 
        and set according to the configuration specified in the 'refine3D' section of 
        the JSON file.

        Args:
            refineStep (optional): Custom step name for the refinement process. Defaults to an empty string.
        """
        self.tomo_refine3D_job = tomo_refine3D_job.TomoRelionRefine3D()
        self.tomo_refine3D_job.joboptions['tomograms_star'].value = self.outputDirectories['reconstruct_tomograms'] + 'tomograms.star'
        self.tomo_refine3D_job = self.parse_params(self.tomo_refine3D_job,'refine3D')

        # Apply Output Directories from Previous Job  
        self.tomo_refine3D_iter = 0
        try: self.tomo_refine3D_job.output_dir = self.outputDirectories[f'bin{self.binning}'][self.check_custom_job_name('refine3D',refineStep)]
        except: pass  

    def run_auto_refine(self, refineStep: str = None):
        """
        Run the automatic 3D refinement job and handle its execution.

        Args:
            refineStep (optional): Custom step name for the refinement process. Defaults to None.
        """
        jobName = self.check_custom_job_name('refine3D',refineStep)    
        self.run_job(self.tomo_refine3D_job, jobName, f'3D Auto Refine @ bin={self.binning}')                              

    def initialize_tomo_class3D(self,classStep=None):
        """
        Initialize the job for 3D classification of tomograms. The job parameters are 
        parsed and set according to the configuration specified in the 'class3D' section 
        of the JSON file.
        """        
        self.tomo_class3D_job = tomo_class3D_job.TomoRelionClass3DJob()
        self.tomo_class3D_job.joboptions['tomograms_star'].value = self.outputDirectories['reconstruct_tomograms'] + 'tomograms.star'        
        self.tomo_class3D_job = self.parse_params(self.tomo_class3D_job,'class3D')
        
        # Apply Output Directories from Previous Job  
        self.tomo_class3D_iter = 0
        try: self.tomo_class3D_job.output_dir = self.outputDirectories[f'bin{self.binning}'][self.check_custom_job_name('class3D',classStep)]
        except: pass          

    def run_tomo_class3D(self):
        """
        Run the 3D classification job and handle its execution.
        """              
        self.run_job(self.tomo_class3D_job, 'class3D', '3D Classification', classifyStep=True)            

    def update_resolution(self, binFactorIndex: int):
        """
        Updates the resolution of the tomographic reconstruction process based on the provided binning factor index.

        Args:
            binFactorIndex: The index corresponding to the desired binning factor to update the resolution.
        """        

        # Update the binning and box size based on the provided binning factor index.
        self.update_job_binning_box_size(self.reconstruct_particle_job, self.pseudo_subtomo_job, binFactorIndex)

        # Update Refinement Parameters (Should I increase sampling for Classification? )
        self.tomo_refine3D_job.joboptions['sampling'].value = self.get_new_sampling(self.tomo_refine3D_job.joboptions['sampling'].value )
        self.tomo_refine3D_job.joboptions['do_solvent_fsc'].value = "yes"

        # Print the current reconstruction crop size, box size, and sampling to the console for verification.
        # These values are essential for monitoring the progress and correctness of the reconstruction process.
        print('Current Reconstruct Crop Size: ', self.reconstruct_particle_job.joboptions['crop_size'].value)
        print('Current Reconstruct Box Size: ', self.reconstruct_particle_job.joboptions['box_size'].value)
        print('Current Sampling: ', self.tomo_refine3D_job.joboptions['sampling'].value)
