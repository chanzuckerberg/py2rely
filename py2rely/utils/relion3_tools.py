from pipeliner.jobs import relion
import pandas as pd    
import starfile

    
class Relion3Pipeline(PipelineHelper):

    def create_relion_three_input(self, pixelSize):

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