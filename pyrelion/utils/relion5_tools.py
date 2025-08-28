from pipeliner.jobs.tomography.relion_tomo import (
    tomo_reconstruct_job, tomo_reconstructparticle_job, tomo_pseudosubtomo_job, tomo_refine3D_job, 
    tomo_initialmodel_job, tomo_class3D_job, tomo_ctfrefine_job, tomo_bayesianpolish_job
)
from pyrelion.utils.sta_tools import PipelineHelper
import os

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
        self.ctf_refine_job = None
        self.bayesian_polish_job = None

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

        # Apply Output Directories from Previous Job       
        try: self.pseudo_subtomo_job.output_dir = self.get_subgroup(self.outputDirectories, f'bin{self.binning}/pseudo_subtomo') 
        except: pass

    def run_pseudo_subtomo(self, rerunPseudoSubtomo: bool = False):
        """
        Run the pseudo-subtomogram generation job and handle its execution.
        """        
        if rerunPseudoSubtomo: pseudoSubtomoIter = self.return_job_iter(f'bin{self.binning}', 'pseudo_subtomo')
        else:                  pseudoSubtomoIter = None
        self.run_job(self.pseudo_subtomo_job, 'pseudo_subtomo', f'Pseudo Tomogram Generation @ bin={self.binning}', jobIter=pseudoSubtomoIter)

    def initialize_initial_model(self):
        """
        Initialize the job for generating the initial 3D model. The job parameters are 
        parsed and set according to the configuration specified in the 'initial_model' 
        section of the JSON file.
        """        
        self.initial_model_job = tomo_initialmodel_job.RelionTomoInimodelJob()
        self.initial_model_job = self.parse_params(self.initial_model_job,'initial_model')
        self.initial_model_job.joboptions['in_particles'].value = self.pseudo_subtomo_job.output_dir + 'particles.star'

    def run_initial_model(self):
        """
        Run the initial 3D model generation job and handle its execution.
        """
        self.run_job(self.initial_model_job, 'initial_model', '3D Initial Model')  

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
        # self.reconstruct_particle_job.joboptions['in_tomograms'].value = self.outputDirectories['reconstruct_tomograms']

        # Apply Output Directories from Previous Job       
        try: self.reconstruct_particle_job.output_dir = self.get_subgroup(self.outputDirectories, f'bin{self.binning}/reconstruct')
        except: pass            

        # Create Spherical Mask for Initial Reconstruction 
        if includeSphereMask: 
            self.create_initial_spherical_mask()        

    def run_reconstruct_particle(self, rerunReconstruct: bool = False):
        """
        Run the particle reconstruction job and handle its execution.
        """          
        # If Completed Refine Process Already Exists, Start Logging New Iterations if rerunRefine is True. 
        if rerunReconstruct: reconstructJobIter = self.return_job_iter(f'bin{self.binning}', 'reconstruct') 
        else:                reconstructJobIter = None    
        self.run_job(self.reconstruct_particle_job, 'reconstruct', 'Reconstruct Particles', jobIter = reconstructJobIter)        

    def initialize_auto_refine(self):
        """
        Initialize the job for automatic 3D refinement. The job parameters are parsed 
        and set according to the configuration specified in the 'refine3D' section of 
        the JSON file.
        """
        self.tomo_refine3D_job = tomo_refine3D_job.TomoRelionRefine3D()
        self.tomo_refine3D_job = self.parse_params(self.tomo_refine3D_job,'refine3D')

        # Set Particles 
        self.tomo_refine3D_job.joboptions['in_particles'].value = self.pseudo_subtomo_job.output_dir + 'particles.star'

        # Apply Output Directories from Previous Job  
        try: self.tomo_refine3D_job.output_dir = self.get_subgroup(self.outputDirectories, f'bin{self.binning}/refine3D')
        except: pass  

    def run_auto_refine(self, 
                        rerunRefine: bool = False,
                        generateInitialModel: bool = False):
        """
        Run the automatic 3D refinement job and handle its execution.

        Args:
            rerunRefine (optional): For the Pipeline to Re-Run this step.
        """

        # If Completed Refine Process Already Exists, Start Logging New Iterations if rerunRefine is True. 
        if rerunRefine: refineJobIter = self.return_job_iter(f'bin{self.binning}', 'refine3D') 
        else:           refineJobIter = None        
        
        # Assuming Class3D is Used to Generate the Initial Reference
        if generateInitialModel: refine3Dname = 'initialmodel_refine3D'
        else:                    refine3Dname = 'refine3D'

        self.run_job(self.tomo_refine3D_job, refine3Dname, f'3D Auto Refine @ bin={self.binning}', jobIter=refineJobIter)            

    def initialize_tomo_class3D(self):
        """
        Initialize the job for 3D classification of tomograms. The job parameters are 
        parsed and set according to the configuration specified in the 'class3D' section 
        of the JSON file.
        """        
        self.tomo_class3D_job = tomo_class3D_job.TomoRelionClass3DJob()
        # self.tomo_class3D_job.joboptions['tomograms_star'].value = self.outputDirectories['reconstruct_tomograms']        
        self.tomo_class3D_job = self.parse_params(self.tomo_class3D_job,'class3D')
        
        # Apply Output Directories from Previous Job  
        self.next_tomo_class3D_iter = self.return_job_iter(f'bin{self.binning}','class3D')
        try: self.tomo_class3D_job.output_dir = self.get_subgroup(self.outputDirectories, f'bin{self.binning}', 'class3D')       
        except: pass

    def run_tomo_class3D(self, 
                         rerunClassify: bool = False,
                         isClassifyStep: bool = True,
                         generateInitialModel: bool = False):
        """
        Run the 3D classification job and handle its execution.
        """

        # If Completed Classify Process Already Exists, Start Logging New Iterations if rerunClassify is True. 
        if rerunClassify: classifyJobIter = self.return_job_iter(f'bin{self.binning}', 'class3D') 
        else:             classifyJobIter = None    

        # Assuming Class3D is Used to Generate the Initial Reference
        if generateInitialModel: class3Dname = 'initialmodel_class3D'
        else:                    class3Dname = 'class3D'

        self.run_job(self.tomo_class3D_job, class3Dname, f'3D Classification @ bin={self.binning}', classifyStep=isClassifyStep, jobIter=classifyJobIter)            

    def run_initial_model_class3D(self,
                                  reference_template: str,
                                  nClasses: int = 1,
                                  nr_iter: int = 5,
                                  tau_fudge: int = 3):
        """
        Apply Default Options for Generating an Initial Model with Class3D Job
        """

        # I/O 
        self.tomo_class3D_job.joboptions['in_particles'].value = self.pseudo_subtomo_job.output_dir + 'particles.star'
        self.tomo_class3D_job.joboptions['fn_ref'].value = reference_template

        # In this Case Reference isn't On Correct GrayScale
        self.tomo_class3D_job.joboptions['ref_correct_greyscale'].value = "no"
        self.tomo_class3D_job.joboptions['dont_skip_align'].value = "yes"
        self.tomo_class3D_job.joboptions['do_local_ang_searches'].value = 'no'        
        self.tomo_class3D_job.joboptions['allow_coarser'].value = 'yes'
        self.tomo_class3D_job.joboptions['use_gpu'].value = 'yes' 
        self.tomo_class3D_job.joboptions['ini_high'].value *= 1.5

        # Swap Tau_Fudge and NClasses for Initial Model Generation
        (nr_iter, self.tomo_class3D_job.joboptions['nr_iter'].value) = (self.tomo_class3D_job.joboptions['nr_iter'].value, nr_iter)
        (nClasses, self.tomo_class3D_job.joboptions['nr_classes'].value) = (self.tomo_class3D_job.joboptions['nr_classes'].value, nClasses)
        (tau_fudge, self.tomo_class3D_job.joboptions['tau_fudge'].value) = (self.tomo_class3D_job.joboptions['tau_fudge'].value, tau_fudge)
        self.run_tomo_class3D(isClassifyStep=False, generateInitialModel=True)

        # Restore Original Classification Parameters Parameters
        self.tomo_class3D_job.joboptions['ref_correct_greyscale'].value = "yes"
        self.tomo_class3D_job.joboptions['dont_skip_align'].value = "no"        
        self.tomo_class3D_job.joboptions['do_local_ang_searches'].value = 'yes'                
        self.tomo_class3D_job.joboptions['allow_coarser'].value = 'no'   
        self.tomo_class3D_job.joboptions['use_gpu'].value = 'no'  
        self.tomo_class3D_job.joboptions['ini_high'].value /= 1.5          

        # Swap Tau_Fudge, Niter, and NClasses for Future Classification Jobs
        nIter = self.tomo_class3D_job.joboptions['nr_iter'].value         
        (nr_iter, self.tomo_class3D_job.joboptions['nr_iter'].value) = (self.tomo_class3D_job.joboptions['nr_iter'].value, nr_iter)        
        (tau_fudge, self.tomo_class3D_job.joboptions['tau_fudge'].value) = (self.tomo_class3D_job.joboptions['tau_fudge'].value, tau_fudge)
        (nClasses, self.tomo_class3D_job.joboptions['nr_classes'].value) = (self.tomo_class3D_job.joboptions['nr_classes'].value, nClasses)                  

        # Return Refinement Template Path       
        return self.tomo_class3D_job.output_dir + f'run_it{nIter:03}_class001.mrc' 

    def initialize_ctf_refine(self):
        """
        Initialize the job for CTF Refinement for the particles. The job parameters are 
        parsed and set according to the configuration specified in the 'class3D' section 
        of the JSON file.
        """        
        self.ctf_refine_job = tomo_ctfrefine_job.TomoRelionCtfRefine()
        # self.ctf_refine_job.joboptions['in_tomograms'].value = self.outputDirectories['reconstruct_tomograms']      
        self.ctf_refine_job = self.parse_params(self.ctf_refine_job,'ctf_refine')
        
        # Apply Output Directories from Previous Job  
        ctfRefineIter = self.return_job_iter(f'bin{self.binning}','ctf_refine')
        try: self.ctf_refine_job.output_dir = self.get_subgroup(self.outputDirectories, f'bin{self.binning}', 'ctf_refine')       
        except: pass

    def run_ctf_refine(self,
                       rerunCtfRefine: bool = False):

        # If Completed Classify Process Already Exists, Start Logging New Iterations if rerunClassify is True. 
        if rerunCtfRefine: ctfRefineJobIter = self.return_job_iter(f'bin{self.binning}', 'ctf_refine') 
        else:              ctfRefineJobIter = None    

        self.run_job(self.ctf_refine_job, 'ctf_refine', f'CTF Refine', jobIter=ctfRefineJobIter)                                   

    def initialize_bayesian_polish(self):
        """
        Initialize the job for CTF Refinement for the particles. The job parameters are 
        parsed and set according to the configuration specified in the 'class3D' section 
        of the JSON file.
        """        
        self.bayesian_polish_job = tomo_bayesianpolish_job.TomoRelionBayesPolishJob()
        # self.bayesian_polish.joboptions['in_tomograms'].value = self.outputDirectories['reconstruct_tomograms']      
        self.bayesian_polish_job = self.parse_params(self.bayesian_polish_job,'bayesian_polish')

        # Apply Output Directories from Previous Job  
        self.bayesian_polish_iter = self.return_job_iter(f'bin{self.binning}','bayesian_polish')
        try: self.bayesian_polish.output_dir = self.get_subgroup(self.outputDirectories, f'bin{self.binning}', 'bayesian_polish')       
        except: pass

    def run_bayesian_polish(self,
                            rerunPolish: bool = False):

        # If Completed Classify Process Already Exists, Start Logging New Iterations if rerunClassify is True. 
        if rerunPolish: polishJobIter = self.return_job_iter(f'bin{self.binning}', 'ctf_refine') 
        else:           polishJobIter = None    

        self.run_job(self.bayesian_polish_job, 'bayesian_polish', f'Bayesian Polish', jobIter=polishJobIter)                                   


    def update_resolution(self, binFactorIndex: int):
        """
        Updates the resolution of the tomographic reconstruction process based on the provided binning factor index.

        Args:
            binFactorIndex: The index corresponding to the desired binning factor to update the resolution.
        """        

        # Update the binning and box size based on the provided binning factor index.
        if self.pseudo_subtomo_job is None:
            self.initialize_pseudo_tomos()
        if self.reconstruct_particle_job is None:
            self.initialize_reconstruct_particle()
        self.update_job_binning_box_size(self.reconstruct_particle_job, self.pseudo_subtomo_job, binFactorIndex)

        # Update Refinement Parameters (Should I increase sampling for Classification? )
        if self.tomo_refine3D_job is not None:
            self.get_new_sampling(self.tomo_refine3D_job)
            self.tomo_refine3D_job.joboptions['do_solvent_fsc'].value = "yes"

            # Print the current reconstruction crop size, box size, and sampling to the console for verification.
            # These values are essential for monitoring the progress and correctness of the reconstruction process.
            print('Current Sampling: ', self.tomo_refine3D_job.joboptions['sampling'].value)

        # Update Healpix Order for Refinement when Binning is 2
        # if self.binning == 2:
            # self.tomo_refine3D_job.joboptions['healpix_order'].value = 3
            # self.tomo_refine3D_job.joboptions['auto_local_healpix_order'].value = 5

        if self.tomo_class3D_job is not None: 
            self.get_new_sampling(self.tomo_class3D_job, update_local=False)

    def check_and_create_symlink(symlink_path, target_path):
        """
        Check if a symbolic link exists at symlink_path, and create it if it doesn't.

        Args:
            symlink_path (str): The path where the symbolic link should be created.
            target_path (str): The target path that the symbolic link should point to.
        """
        if not os.path.islink(symlink_path):
            # If the symlink does not exist, create it
            os.symlink(target_path, symlink_path)
            print(f"Created symbolic link: {symlink_path} -> {target_path}")
        else:
            print(f"Symbolic link already exists: {symlink_path}")
