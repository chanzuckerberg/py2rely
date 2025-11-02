from pipeliner.jobs.tomography.relion_tomo import tomo_reconstructparticle_job, tomo_pseudosubtomo_job, tomo_coords_import_job, tomo_refine3D_job, tomo_initialmodel_job
from pipeliner.jobs.relion import class3D_job, select_job, maskcreate_job, postprocess_job
from py2rely.utils.sta_tools import PipelineHelper
import pipeliner.job_manager as job_manager
import glob, starfile, json, re, mrcfile
import subprocess, os
import numpy as np
import warnings

class Relion4Pipeline(PipelineHelper):

    def __init__(self, inProject):
        super().__init__(inProject)

    def initialize_import_tomograms(self):

        self.import_tomo_job = tomo_coords_import_job.RelionImportTomograms()
        self.import_tomo_job = self.parse_params(self.import_tomo_job,'import_tomograms')

    def run_import_tomograms(self):

        self.run_job(self.import_tomo_job, 'import_tomograms', 'Import Tomograms')

    def initialize_import_coordinates(self):

        self.import_particles_job = tomo_coords_import_job.RelionImportParticles()
        self.import_particles_job = self.parse_params(self.import_particles_job,'import_particles')       

    def run_import_particles(self):

        self.run_job(self.import_particles_job, 'import_particles', 'Import Particles')

    def initialize_initial_model(self):

        self.initial_model_job = tomo_initialmodel_job.RelionTomoInimodelJob()
        self.initial_model_job = self.parse_params(self.initial_model_job,'initial_model')

    def run_initial_model(self):

        self.run_job(self.initial_model_job, 'initial_model', '3D Initial Model')                

    def initialize_reconstruction(self):  

        self.reconstruct_job = tomo_reconstructparticle_job.RelionReconstructParticleJob()
        self.reconstruct_job = self.parse_params(self.reconstruct_job,'reconstruct')
        
        self.reconstruct_job.joboptions['binfactor'].value = self.binning
        self.reconstruct_job.joboptions['box_size'].value = self.return_new_box_size(self.binning)
        self.reconstruct_job.joboptions['in_tomograms'].value = self.outputDirectories['import_tomograms'] + 'tomograms.star'      

        # Apply Output Directories from Previous Job
        try: self.reconstruct_job.output_dir = self.outputDirectories['reconstruct_bin' + str(self.binning)]
        except: pass

        # Create Spherical Mask for Initial Reconstruction 
        self.create_initial_spherical_mask()

    def run_reconstruct(self):

        jobName = f'reconstruct_bin{self.binning}'
        self.run_job(self.reconstruct_job, jobName, f'Reconstruction  @ bin={self.binning}')

    def initialize_pseudo_tomos(self):

        self.pseudo_subtomo_job = tomo_pseudosubtomo_job.RelionPseudoSubtomoJob()
        self.pseudo_subtomo_job = self.parse_params(self.pseudo_subtomo_job,'pseudo_subtomo')
        
        self.pseudo_subtomo_job.joboptions['binfactor'].value = self.binning
        self.pseudo_subtomo_job.joboptions['box_size'].value = self.return_new_box_size(self.binning)        
        self.pseudo_subtomo_job.joboptions['in_tomograms'].value = self.outputDirectories['import_tomograms'] + 'tomograms.star'

        # Apply Output Directories from Previous Job
        try: self.pseudo_subtomo_job.output_dir = self.outputDirectories['pseudo_subtomo_bin' + str(self.binning)]                
        except: pass

    def run_pseudo_subtomo(self):

        jobName = f'pseudo_subtomo_bin{self.binning}'
        self.run_job(self.pseudo_subtomo_job, jobName, f'Psuedo Tomogram Generation @ bin={self.binning}')        

    def initialize_auto_refine(self, refineStep=''):

        self.tomo_refine3D_job = tomo_refine3D_job.TomoRelionRefine3D()
        self.tomo_refine3D_job.joboptions['tomograms_star'].value = self.outputDirectories['import_tomograms'] + 'tomograms.star'
        self.tomo_refine3D_job = self.parse_params(self.tomo_refine3D_job,'refine3D')

        try: self.tomo_refine3D_job.output_dir = self.outputDirectories[self.check_custom_job_name('refine3D',refineStep)]
        except: pass  

    def run_auto_refine(self,refineStep=None):

        jobName = self.check_custom_job_name('refine3D',refineStep)    
        self.run_job(self.tomo_refine3D_job, jobName, f'3D Auto Refine @ bin={self.binning}')                   
    
    def initialize_classification(self, classifyStep=''):

        self.tomo_class3D_job = class3D_job.RelionClass3D()
        self.tomo_class3D_job = self.parse_params(self.tomo_class3D_job,'class3D')    

        try: self.tomo_class3D_job.output_dir = self.outputDirectories[self.check_custom_job_name('class3D',classifyStep)]
        except: pass

    # Classify 3D Job 
    def run_class3D(self, classifyStep=None):

        jobName = self.check_custom_job_name('class3D',classifyStep)      
        self.run_job(self.tomo_class3D_job, jobName, f'Classification @ bin={self.binning}', classifyStep = classifyStep)              
    
    # Subset Selection Job
    def initialize_selection(self,selectStep=''):

        self.tomo_select_job = select_job.RelionSelectOnValue()
        self.tomo_select_job.joboptions['select_label'].value = "rlnClassNumber" 

        try: self.tomo_select_job.output_dir = self.outputDirectories[self.check_custom_job_name('select',selectStep)]
        except: pass


    # Select Class Job - Pick class with Largest Distribution
    def run_subset_select(self, keepClasses=None, selectStep=None):

        jobName = self.check_custom_job_name('select',selectStep) 
        self.run_job(self.tomo_select_job, jobName, f'Subset Selection', keepClasses=keepClasses)            

    # Edit the Selection Job For the Pre-defined Best Class and Apply top 
    def custom_select(self, classPath, keepClasses):

        particlesFile = starfile.read(classPath)

        optics = particlesFile['optics']
        particles = particlesFile['particles']

        # I need to Pull out Data Optics
        filteredParticles = particles[particles['rlnClassNumber'].isin(keepClasses)]

        starfile.write({'optics':optics, 'particles':filteredParticles}, self.tomo_select_job.output_dir + 'particles.star')            

    # Mask Creation Job
    def initialize_mask_create(self):   

        self.mask_create_job = maskcreate_job.RelionMaskCreate()
        self.mask_create_job = self.parse_params(self.mask_create_job,'mask_create')

        try: self.mask_create_job.output_dir = self.outputDirectories[f"mask_create_bin{self.binning}"]
        except: pass    

        self.initialize_post_process()

    # Create Mask with Estimated Isonet Contour Value
    def run_mask_create(self):

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

    def initialize_post_process(self):

        self.post_process_job = postprocess_job.PostprocessJob()
        self.post_process_job.joboptions['angpix'].value = -1

    def run_post_process(self):

        jobName = f'post_process_bin{self.binning}'
        self.run_job(self.post_process_job, jobName, 'Post Process')      

    def create_initial_spherical_mask(self):

        specimenDiameter = float(self.params['specimenDiameter'])
        vSize = float(self.params['voxelSize']) * self.binning
        boxSize = self.return_new_box_size(self.binning)
        specimenRadius = np.round(specimenDiameter / (2 * vSize))

        # Create mask if Doesn't Exist
        maskName  = '{}_mask_{}pix.mrc'.format(self.params['specimen'],boxSize,vSize)
        if not os.path.isfile(maskName):
            maskCreateCommand = f'pytom_create_mask.py -o {maskName} --voxel-size {vSize} --radius {specimenRadius} -b {boxSize} --sigma 1'
            subprocess.run(maskCreateCommand,shell=True)  

        # Assign Spherical Mask to Reconstruct Job
        self.reconstruct_job.joboptions['fn_mask'].value = maskName

    def write_mrc(self,tomo, fname, voxelSize=1, dtype=None, no_saxes=True):

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

    def create_relion_three_input(self, pixelSize):
        import pandas as pd

        # Create Micrographs.star
        optics = {}
        optics['rlnOpticsGroup'] = [1]
        optics['rlnOpticsGroupName'] = [ 'opticsGroup1' ]
        optics['rlnMicrographOriginalPixelSize'] = [ pixelSize ]
        optics['rlnVoltage'] = [ 300 ]
        optics['rlnSphericalAberration'] = [ 2.7 ]
        optics['rlnAmplitudeContrast'] = [ 0.1 ]
        optics['rlnMicrographPixelSize'] = [ pixelSize ]

        # TODO : Read input/tomograms_description.star and pull out all Tomograms, Ctf Files, and PyTom Coordinates
        df = starfile.read(self.params['import_tomograms']['in_tomograms'])
        
        os.makedirs('input/particles',exist_ok=True)

        micrographs = {}; particles = {}
        tomoNames = []; ctfImages = []; particleCoords = []        
        coordsX = []; coordsY = []; coordsZ = []; rotAng = []; tiltAng = []; psiAng = []; microNames =[]
        for tsInd in range(len(df['rlnTomoName'])):
            
            ts = df['rlnTomoName'][tsInd]
            
            tomoName =  '/'.join(df['rlnTomoTiltSeriesName'][tsInd].split('/')[:-2])

            # TODO : Generic Path for Pulling Out the Tomogram            
            particleName = tomoName + f'/VoxelSpacing_10.0_Binning_6.4935/Annotations/ribo80S_TemplateMatching/WBP/{ts}_Vol_WBP_ribo80S_particles.star'
    
            try:
                particleDF = starfile.read(particleName)

                coordsX.extend(particleDF['rlnCoordinateX'].tolist())
                coordsY.extend(particleDF['rlnCoordinateY'].tolist())
                coordsZ.extend(particleDF['rlnCoordinateZ'].tolist())
                rotAng.extend(particleDF['rlnAngleRot'].tolist())
                tiltAng.extend(particleDF['rlnAngleTilt'].tolist())
                psiAng.extend(particleDF['rlnAnglePsi'].tolist())
                
                nRows = len(particleDF['rlnAnglePsi'])

                # TODO : Generic Path for Pulling Out the Tomogram
                microNames.extend( [tomoName + f'/VoxelSpacing_10.0_Binning_6.4935/Tomograms/{ts}_Vol_WBP.mrc']  * nRows )

                coordsName = f'input/particles/{ts}_particles.star'
                starfile.write(particleDF,coordsName)
                particleCoords.append(coordsName)
                ctfImages.append(df['rlnTomoImportCtfFindFile'][tsInd])                

                # TODO : Generic Path for Pulling Out the Tomogram                
                tomoNames.append(tomoName + f'/VoxelSpacing_10.0_Binning_6.4935/Tomograms/{ts}_Vol_WBP.mrc')
            except:
                pass

        micrographs['rlnMicrographName'] = tomoNames
        micrographs['rlnCtfImage'] = ctfImages
        micrographs['rlnOpticsGroup'] = [ '1' ] * len(ctfImages)
        starfile.write({'optics': pd.DataFrame(optics), 'micrographs': pd.DataFrame(micrographs)},'input/relion3_micrographs.star')

        # Create particles.star
        coord_files = {}
        coord_files['rlnMicrographName'] = tomoNames
        coord_files['rlnMicrographCoordinates'] = particleCoords
        starfile.write({'coordinate_files': pd.DataFrame(coord_files)},'input/particles.star')     

        optics2 = {}
        optics2['rlnOpticsGroup'] = 1
        optics2['rlnOpticsGroupName'] = 'opticsGroup1'
        optics2['rln']

        # Create Relion3 particles.star
        particles['rlnCoordinateX'] = coordsX; particles['rlnCoordinateY'] = coordsY; particles['rlnCoordinateZ'] = coordsZ        
        particles['rlnAngleRot'] = rotAng; particles['rlnAngleTilt'] = tiltAng; particles['rlnAnglePsi'] = psiAng      
        particles['rlnMicrographName'] = microNames
        starfile.write({'optics': pd.DataFrame(optics), 'particles': pd.DataFrame(particles)},'input/relion3_particles.star')        

    def run_extract_job(self, tomoInput, coordsInput,):

        self.extractJob = relion.extract_job.RelionExtract()
        self.extractJob.joboptions['star_mics'].value = tomoInput
        self.extractJob.joboptions['cfoords_suffix'].value = coordsInput
        self.extractJob.joboptions['extract_size'].value = self.return_new_box_size(self.binning)

        jobName = f'extract_{self.binning}'
        if not self.check_if_job_already_completed(self.extractJob,jobName):

            print('\n[Extract] Starting Job...')
            result = self.run_job(self.extractJob,'Extract')
            if result == 'Failed': print('Post Process Failed!\n'); exit()

            self.outputDirectories[jobName] = self.extractJob.output_dir
            self.save_new_output_directory()               

    def edit_extraction_output(self):

        particlesPath = self.extractJob.output_dir + 'particles.star'
        
        particlesDF = starfile.read(particlesPath)
        tomosList = particlesDF['particles']['rlnImageName'] 

        ctfImages = []
        pattern = r'TS_\d+_\d+'
        for tomo in tomosList:
            tomoID = re.findall(pattern, tomo)[0]
            ctfImages.append(f'../ExperimentRuns/{tomoID}/TiltSeries/{tomoID}_CTF.mrc')

        particlesDF['particles']['rlnCtfImage'] = ctfImages

        starfile.write(particlesDF,self.extractJob.output_dir+'particles.star')