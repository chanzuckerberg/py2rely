import os, glob, argparse, starfile, click, copick
from scipy.spatial.transform import Rotation as R
from relion_sta_pipeline.utils import sta_tools
from typing import List
from tqdm import tqdm
import pandas as pd
import numpy as np

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings={"show_default": True})
@click.option(
    "--base-project",
    type=str,
    required=False,
    default = "krios1.processing",
    help="Main Project Folder Name"
)
@click.option(
    "--session",
    type=str,
    required=True,
    default='23dec21',
    help="Session for Generating Relion Experiment (e.g, 23dec21)",
)
@click.option(
    "--run",
    type=str,
    required=False,
    default='run001',
    help="Run for Generating Relion Experiment",
)
@click.option(
    "--output",
    type=str,
    required=False,
    default='input/tiltSeries',
    help="Output directory path",
)
@click.option(
    "--pixel-size",
    type=float,
    required=False,
    default=1.54,
    help="Unbinned Tilt Tilt Series Pixel Size (Å)",
)
@click.option(
    "--total-dose",
    type=float,
    required=False,
    default=60,
    help="Total Accumulated Dose",
)
@click.option(
    "--symlinks",
    type=str,
    required=False,
    default=None,
    help="Output directory path for the MRCS symlinks",
)
@click.option(
    "--voltage",
    type=float,
    required=False,
    default=300,
    help="Microscope Acceleration Voltage (kV)"
)
@click.option(
    "--spherical-aberration",
    type=float,
    required=False,
    default=2.7,
    help="Estimated Microscope Aberrations (mm)"
)
@click.option(
    "--amplitude-contrast",
    type=float,
    required=False,
    default=0.07,
    help="Microscope Amplitude Contrast"
)
def import_tilt_series(
    base_project: str, 
    session: str,
    run: str,
    output: str,
    pixel_size: float,
    total_dose: float,
    symlinks: str,
    voltage: float,
    spherical_aberration: float,
    amplitude_contrast: float
    ):

    tiltSeriesHeader = output.split('/')[-1]

    utils = sta_tools.PipelineHelper(None, requireRelion=False)
    utils.print_pipeline_parameters('Importing Tilt-Series', base_project = base_project, session = session, 
                                    output = output, pixel_size = pixel_size, total_dose = total_dose, 
                                    voltage = voltage, spherical_aberration = spherical_aberration,
                                    amplitude_contrast = amplitude_contrast, header = tiltSeriesHeader, 
                                    file_name='input/import.json')                               
    
    inputPath = os.path.join( '/hpc/projects/group.czii', base_project, 'aretomo3', session, run, '*_CTF.txt')
    tiltSeries = np.array(glob.glob(inputPath), dtype=str)

    try: 
        if not os.path.isdir(symlinks):
            os.makedirs(symlinks, exist_ok=True)
    except:
        pass

    tiltSeriesDirectory = output
    os.makedirs(tiltSeriesDirectory, exist_ok=True)
    aln_column_names = ['SEC', 'ROT', 'GMAG', 'TX', 'TY', 'SMEAN', 'SFIT', 'SCALE', 'BASE', 'TILT']

    # Image Names
    tomoNames = []
    tiltSeriesStarNames = []

    # Create Each Tilt Series
    for tomos in tqdm(tiltSeries):
        
        # Read the Tomogram ID and baseTomoPath
        tomoPath = '/'.join(tomos.split('/')[:-1])
        tomoID = '_'.join(tomos.split('/')[-1].split('_')[:-1])

        # Read IMOD *.xf alignment Parameters 
        xfPath = os.path.join(tomoPath, tomoID + '_Imod', tomoID + '_st.xf')
        xfDF = np.loadtxt(xfPath)

        if len(xfDF.shape) < 2 or xfDF.shape[1] < 6:
            continue

        tomoNames.append(session + '_' + tomoID)

        # Read the CTF Parameters
        ctfPath = os.path.join(tomoPath, tomoID + '_CTF.txt')
        ctfText = np.loadtxt(ctfPath)

        # Read the AreTomo Alignment Parameters
        alnPath = os.path.join(tomoPath, tomoID + '.aln')
        alnDF = pd.read_csv(alnPath, delimiter='\s+', comment='#', header=None, names=aln_column_names)

        # Read Acqusition Order List
        orderListPath = os.path.join(tomoPath, tomoID + '_Imod', tomoID + '_order_list.csv')
        orderList = np.genfromtxt(orderListPath, delimiter=',', skip_header=1)
        totalExposure = [] 

        # Tomogram Alignment Parameters
        tomoYtilt = []
        tomoZRot = []
        tomoXshift = []
        tomoYshift = []
        tiltSeriesNames = []

        # CTF Fit Parameters
        ctfImageNames = []
        defocusU = []
        defocusV = []
        defocusAngle = []

        # Link to MRC stack file extension
        if symlinks is None:
            tiltSeriesName = f'{tomoPath}/{tomoID}.mrcs'
            ctfImageName = f'{tomoPath}/{tomoID}_CTF.mrcs'

            if not os.path.isfile(tiltSeriesName):
                os.symlink(f'{tomoID}.mrc', tiltSeriesName)

            if not os.path.isfile(ctfImageName):
                os.symlink(f'{tomoID}_CTF.mrc', ctfImageName)
        else:
            tiltSeriesName = os.path.join(symlinks, f'{tomoID}.mrcs')
            ctfImageName = os.path.join(symlinks, f'{tomoID}_CTF.mrcs')

            tiltSeriesNameAbs = os.path.abspath(f'{tomoPath}/{tomoID}.mrc')
            ctfImageNameAbs = os.path.abspath(f'{tomoPath}/{tomoID}_CTF.mrc')

            if not os.path.isfile(tiltSeriesName):
                os.symlink(tiltSeriesNameAbs, tiltSeriesName)

            if not os.path.isfile(ctfImageName):
                os.symlink(ctfImageNameAbs, ctfImageName)

        tiltInd = 0
        nTilts = xfDF.shape[0]
        while tiltInd < nTilts:

            # Assume if Rotation is Identity and No Translation that We're Excluding this Tilt
            if xfDF[tiltInd, 0] == 1 and xfDF[tiltInd, 2] == 0 and xfDF[tiltInd, 5] == 0:
                pass
            else:
                # Read Tilt from Full Tilt Series
                tiltSeriesName_id = f'{tiltInd + 1}@{tiltSeriesName}'
                tiltSeriesNames.append(tiltSeriesName_id)

                ctfImageName_id = f'{tiltInd + 1}@{ctfImageName}'
                ctfImageNames.append(ctfImageName_id)

                # Append Tilt Angle (Y-Tilt)
                tomoYtilt.append(alnDF['TILT'][tiltInd])

                # Option 1: Pull TX and TY from *.aln
                tomoXshift.append(alnDF['TX'][tiltInd] * pixel_size)
                tomoYshift.append(alnDF['TY'][tiltInd] * pixel_size)

                # Option 2: Pull TX and TY from *.xf
                # tomoXshift.append(xfDF[tiltInd,4] * pixel_size)
                # tomoYshift.append(xfDF[tiltInd,5] * pixel_size)

                defocusU.append(ctfText[tiltInd, 1])
                defocusV.append(ctfText[tiltInd, 2])
                defocusAngle.append(ctfText[tiltInd, 3])

                acqNum = np.argmin( np.abs(orderList[:,1] - alnDF['TILT'][tiltInd]) )
                totalExposure.append( total_dose / nTilts * (orderList[acqNum,0] - 1) )

            tiltInd += 1

        num_rows = len(tiltSeriesNames)

        # Count Number of Rows that Reflects Tilts Used for Alignment / Reconstruction
        # nRows = np.count_nonzero(~np.isnan(alnDF['TILT']))
        tomoZRot.extend([alnDF['ROT'][0]] * num_rows)            

        # Save TS_XX_YY starfile
        ts_dict = {}
        ts_dict['rlnMicrographName'] = tiltSeriesNames
        # ts_dict['rlnTomoXTilt'] = [0] * nRows
        ts_dict['rlnTomoXTilt'] = [0] * num_rows
        ts_dict['rlnTomoYTilt'] = tomoYtilt
        ts_dict['rlnTomoZRot'] = tomoZRot
        ts_dict['rlnTomoXShiftAngst'] = tomoXshift
        ts_dict['rlnTomoYShiftAngst'] = tomoYshift
        ts_dict['rlnCtfImage'] = ctfImageNames
        ts_dict['rlnDefocusU'] = defocusU
        ts_dict['rlnDefocusV'] = defocusV
        ts_dict['rlnDefocusAngle'] = defocusAngle
        ts_dict['rlnMicrographPreExposure'] = totalExposure        

        # Placeholders
        # ts_dict['rlnMicrographMovieName'] = ["none" for _ in range(num_rows)]
        ts_dict['rlnTomoTiltMovieFrameCount'] = ["1" for _ in range(num_rows)]
        ts_dict['rlnTomoNominalStageTiltAngle'] = ["0" for _ in range(num_rows)]
        ts_dict['rlnTomoNominalTiltAxisAngle'] = ["0" for _ in range(num_rows)]
        ts_dict['rlnTomoNominalDefocus'] = defocusU
        # ts_dict['rlnCtfPowerSpectrum'] = ["none" for _ in range(num_rows)]
        # ts_dict['rlnMicrographNameEven'] = ["none" for _ in range(num_rows)]
        # ts_dict['rlnMicrographNameOdd'] = ["none" for _ in range(num_rows)]
        # ts_dict['rlnMicrographMetadata'] = ["none" for _ in range(num_rows)]
        ts_dict['rlnAccumMotionTotal'] = ["0" for _ in range(num_rows)]
        ts_dict['rlnAccumMotionEarly'] = ["0" for _ in range(num_rows)]
        ts_dict['rlnAccumMotionLate'] = [str(i) for i in range(num_rows)]
        ts_dict['rlnCtfFigureOfMerit'] = ["0" for _ in range(num_rows)]
        ts_dict['rlnCtfMaxResolution'] = ["0" for _ in range(num_rows)]
        ts_dict['rlnCtfIceRingDensity'] = ["0" for _ in range(num_rows)]

        # Write the Output and Track StarFileName Name
        writeTSpath = os.path.join(tiltSeriesDirectory, tomoID + '.star')
        starfile.write({tomoID: pd.DataFrame(ts_dict)}, writeTSpath, overwrite=True)
        tiltSeriesStarNames.append(writeTSpath)

    # Create aligned_tilt_series.star
    nRows = len(tomoNames)
    aligned_ts = {}
    aligned_ts['rlnTomoName'] = tomoNames
    aligned_ts['rlnVoltage'] = [voltage] * nRows
    aligned_ts['rlnSphericalAberration'] = [spherical_aberration] * nRows
    aligned_ts['rlnAmplitudeContrast'] = [amplitude_contrast] * nRows
    aligned_ts['rlnMicrographOriginalPixelSize'] = [pixel_size] * nRows
    aligned_ts['rlnTomoHand'] = [-1] * nRows
    aligned_ts['rlnOpticsGroupName'] = ['optics1'] * nRows
    aligned_ts['rlnTomoTiltSeriesPixelSize'] = [pixel_size] * nRows
    aligned_ts['rlnTomoTiltSeriesStarFile'] = tiltSeriesStarNames

    fn = os.path.join(tiltSeriesDirectory, "aligned_tilt_series.star")
    starfile.write({"global": pd.DataFrame(aligned_ts)}, fn, overwrite=True)

    # Inform the user that the file has been written successfully
    print(f"\nRelion5 Tomograms STAR file saved to: {fn}\n")    

###########################################################################################

@cli.command(context_settings={"show_default": True})
@click.option(
    "--input",
    type=str,
    required=True,
    help="Input STAR-file with coordinates",
)
@click.option(
    "--output",
    type=str,
    required=False,
    default=None,
    help="Output STAR-file (if not provided, output will be 'full_picks.star')",
)
@click.option(
    "--x",
    type=float,
    required=True,
    default='4096',
    help="Box size along x-axis in the picked tomogram",
)
@click.option(
    "--y",
    type=float,
    required=True,
    default='4096',
    help="Box size along y-axis in the picked tomogram",
)
@click.option(
    "--z",
    type=float,
    required=True,
    default='1200',
    help="Box size along z-axis in the picked tomogram",
)
@click.option(
    "--pixel-size",
    type=float,
    required=False,
    default=1.54,
    help="Picked Coordinates Pixel Size (Å)",
)
@click.option(
    "--voltage",
    type=float,
    required=False,
    default=300,
    help="Microscope Acceleration Voltage  (kV)"
)
@click.option(
    "--spherical-aberration",
    type=float,
    required=False,
    default=2.7,
    help="Estimated Microscope Aberrations (mm)"
)
@click.option(
    "--amplitude-contrast",
    type=float,
    required=False,
    default=0.07,
    help="Microscope Amplitude Contrast"
)
@click.option(
    "--optics-group",
    type=int,
    required=False,
    default=1,
    help="Optics Group"
)
@click.option(
    "--optics-group-name",
    type=str,
    required=False,
    default="opticsGroup1",
    help="Optics Group"
)
def import_particles(
    input: str,
    output: str,
    x: float,
    y: float,
    z: float,
    pixel_size: float,
    voltage: float, 
    spherical_aberration: float, 
    amplitude_contrast: float,
    optics_group: int,
    optics_group_name: str
    ):

    utils = sta_tools.PipelineHelper(None, requireRelion=False)
    utils.print_pipeline_parameters('Importing Particles', input = input, output = output, 
                                    x = x, y = y, z = z, pixel_size = pixel_size, voltage = voltage, 
                                    spherical_aberration = spherical_aberration, amplitude_contrast = amplitude_contrast,
                                    header = f'particles', file_name=f'input/import.json')                               

    # Read the input STAR file into a DataFrame
    inputDF = starfile.read(input)

    # Convert coordinates to centered values in Angstroms
    x = (inputDF["rlnCoordinateX"] - x / 2) * pixel_size
    y = (inputDF["rlnCoordinateY"] - y / 2) * pixel_size
    z = (inputDF["rlnCoordinateZ"] - z / 2) * pixel_size
    
    # Add new columns for centered coordinates in Angstroms
    inputDF["rlnCenteredCoordinateXAngst"] = x
    inputDF["rlnCenteredCoordinateYAngst"] = y
    inputDF["rlnCenteredCoordinateZAngst"] = z

    # if name is not None:
    #     inputDF["rlnTomoName"] = name

    # Remove '_Vol' substring
    inputDF['rlnTomoName'] = inputDF['rlnTomoName'].str.replace('_Vol', '')

    # Assign a default optics group value to all particles
    inputDF['rlnOpticsGroup'] = [1] * len(inputDF['rlnTomoName'])

    # Set default output file name if not provided
    if output is None: 
        output = 'input/full_picks.star'

    # Create optics group metadata as a dictionary
    optics = {
        'rlnOpticsGroup': optics_group,
        'rlnOpticsGroupName': optics_group_name,
        'rlnSphericalAberration': spherical_aberration,
        'rlnVoltage': voltage,
        'rlnAmplitudeContrast': amplitude_contrast,
        'rlnTomoTiltSeriesPixelSize': [pixel_size]
    }    

    # Write the optics and particles data to a new STAR file
    starfile.write({'optics': pd.DataFrame(optics), "particles": inputDF}, output)

    # Inform the user that the file has been written successfully
    print(f"\nRelion5 Particles STAR file saved to: {output}\n")

###########################################################################################

@cli.command(context_settings={"show_default": True})
@click.option(
    "--config",
    type=str,
    required=True,
    help="Path to Copick Config",    
)
@click.option(
    "--session",
    type=str,
    required=True,
    help="Experiment Session For When the Data was Collected"
)
@click.option(
    "--output-path",
    type=str,
    required=False,
    default="input",
    help="Path to Write Star File"
)
@click.option(
    "--pixel-size",
    type=float,
    required=False, 
    default = 1.54,
    help="Pixel Size of the Tilt Series"
)
@click.option(
    "--copick-name",
    type=str,
    required=True,
    help="Protein Name to Query Data"
)
@click.option(
    "--copick-session-id",
    type=str,
    required=False,
    default=None,
    help="session_id to Query Picks"
)
@click.option(
    "--copick-user-id",
    type=str,
    required=False, 
    default=None,
    help="UserID to Query Picks"
)
@click.option(
    "--x",
    type=float,
    required=True,
    default='4096',
    help="Box size along x-axis in the picked tomogram",
)
@click.option(
    "--y",
    type=float,
    required=True,
    default='4096',
    help="Box size along y-axis in the picked tomogram",
)
@click.option(
    "--z",
    type=float,
    required=True,
    default='1200',
    help="Box size along z-axis in the picked tomogram",
)
@click.option(
    "--voltage",
    type=float,
    required=False,
    default=300,
    help="Microscope Acceleration Voltage  (kV)"
)
@click.option(
    "--spherical-aberration",
    type=float,
    required=False,
    default=2.7,
    help="Estimated Microscope Aberrations (mm)"
)
@click.option(
    "--amplitude-contrast",
    type=float,
    required=False,
    default=0.07,
    help="Microscope Amplitude Contrast"
)
@click.option(
    "--optics-group",
    type=int,
    required=False,
    default=1,
    help="Optics Group"
)
@click.option(
    "--optics-group-name",
    type=str,
    required=False,
    default="opticsGroup1",
    help="Optics Group"
)
def gather_copick_particles(
    config: str, 
    session: str,
    copick_name: str, 
    output_path: str = 'input',
    pixel_size: float = 1.54, 
    copick_session_id: str = None, 
    copick_user_id: str = None,
    x: float = 4096,
    y: float = 4096, 
    z: float = 4096,
    voltage: float = 300,
    spherical_aberration: float = 2.7,
    amplitude_contrast: float = 0.07,
    optics_group: int = 1,
    optics_group_name: str = 'opticsGroup1'
    ):

    # Determine Which Write Path Based On Copick Query
    if copick_session_id is not None and copick_user_id is not None:
        fname = f'{copick_user_id}_{copick_session_id}_{copick_name}'
    elif copick_session_id is not None:
        fname = f'{copick_user_id}_{copick_name}'
    else: # Assume copick_user_id is not None
        fname = f'{copick_session_id}_{copick_name}'

    # Specify Output Path
    os.makedirs(output_path, exist_ok=True)
    writePath = os.path.join( output_path, f'{fname}.star' )          

    utils = sta_tools.PipelineHelper(None, requireRelion=False)
    utils.print_pipeline_parameters('Gathering Copick Particles', config = config, output_path = writePath, 
                                    copick_name = copick_name, copick_session_id = copick_session_id, copick_user_id = copick_user_id, 
                                    pixel_size = pixel_size, tomo_dim_x = x, tomo_dim_y = y, tomo_dim_z = z, voltage = voltage, 
                                    spherical_aberration = spherical_aberration, amplitude_contrast = amplitude_contrast, 
                                    optics_group = optics_group, optics_group_name = optics_group_name, 
                                    header = fname, file_name=f'{output_path}/import.json')       

    # Gather Copick Root from Config File 
    root = copick.from_file(config)

    # Dictionary That Will Be Exported As a StarFile
    myStarFile = {} 
    myStarFile['rlnTomoName'] = []
    myStarFile['rlnCoordinateX'] = []
    myStarFile['rlnCoordinateY'] = []
    myStarFile['rlnCoordinateZ'] = []
    myStarFile['rlnAngleRot'] = []
    myStarFile['rlnAngleTilt'] = []
    myStarFile['rlnAnglePsi'] = []

    # Load tomo_ids
    run_ids = [run.name for run in root.runs] 

    for runID in tqdm(run_ids):

        # Query CopickRun and Picks
        run = root.get_run(runID)
        picks = run.get_picks(object_name = copick_name, session_id = copick_session_id, user_id = copick_user_id)

        # Iterate Through All Available Picks Based On Query
        nPicks = len(picks)
        for ii in range(nPicks):       

            # Extract All Points Per Pick
            points = picks[ii].points
            nPoints = len(points)             
            coordinates = np.zeros([nPoints, 3])
            orientations = np.zeros([nPoints, 3])            
            for ii in range(nPoints):

                # Extract 3D Coordinates (Scale By Tilt-Series Pixel Size)
                coordinates[ii,] = [points[ii].location.x / pixel_size,   
                                    points[ii].location.y / pixel_size,
                                    points[ii].location.z / pixel_size]
                
                # Convert from Rotation to Euler Angles
                rot = np.array(points[ii].transformation_)[:3,:3] # Ignore Translation Vector
                r = R.from_matrix(rot)
                orientations[ii,] = r.inv().as_euler('ZYZ',degrees=True)
            
            # Write Outputs to StarFile Dictionary
            myStarFile['rlnTomoName'].extend([session + '_' + runID]*nPoints)
            myStarFile['rlnCoordinateX'].extend(coordinates[:,0])
            myStarFile['rlnCoordinateY'].extend(coordinates[:,1])
            myStarFile['rlnCoordinateZ'].extend(coordinates[:,2]) 
            myStarFile['rlnAngleRot'].extend(orientations[:,0])
            myStarFile['rlnAngleTilt'].extend(orientations[:,1])
            myStarFile['rlnAnglePsi'].extend(orientations[:,2])
        
    # Convert coordinates to centered values in Angstroms and Add new columns for centered coordinates in Angstroms
    myStarFile["rlnCenteredCoordinateXAngst"] = (np.array(myStarFile["rlnCoordinateX"]) - x / 2) * pixel_size
    myStarFile["rlnCenteredCoordinateYAngst"] = (np.array(myStarFile["rlnCoordinateY"]) - y / 2) * pixel_size
    myStarFile["rlnCenteredCoordinateZAngst"] = (np.array(myStarFile["rlnCoordinateZ"]) - z / 2) * pixel_size

    # Convert From Dictionary to DataFrame
    myStarFile = pd.DataFrame(myStarFile)

    # Remove '_Vol' substring
    myStarFile['rlnTomoName'] = myStarFile['rlnTomoName'].str.replace('_Vol', '')

    # Assign a default optics group value to all particles
    myStarFile['rlnOpticsGroup'] = [1] * len(myStarFile['rlnTomoName'])

    # Create optics group metadata as a dictionary
    optics = {
        'rlnOpticsGroup': optics_group,
        'rlnOpticsGroupName': optics_group_name,
        'rlnSphericalAberration': spherical_aberration,
        'rlnVoltage': voltage,
        'rlnAmplitudeContrast': amplitude_contrast,
        'rlnTomoTiltSeriesPixelSize': [pixel_size]
    }    

    # Write the optics and particles data to a new STAR file
    starfile.write({'optics': pd.DataFrame(optics), "particles": myStarFile}, writePath)

    # # Inform the user that the file has been written successfully
    print(f"\nRelion5 Particles STAR file saved to: {writePath}\n")      

@cli.command(context_settings={"show_default": True})
@click.option(
    "--input",
    type=str,
    required=True,
    multiple=True,    
    help="StarFiles to Merge for STA Pipeline"
)
@click.option(
    "--output",
    type=str,
    required=False,
    default="input/full_picks.star",
    help="Output Filename to Write Merged Starfile"
)
def combine_star_files(
    input: List[str],
    output: str
    ):

    # Iterate Through all Input StarFiles
    for ii in range(len(input)):

        filename = input[ii]
        print(f'Adding {filename} to the Merged StarFile')
        file = starfile.read(filename)

        if ii == 0:
            merged_optics = file['optics']
            merged_particles = file['particles']           
        else:
            merged_particles = pd.concat([merged_particles, file['particles']], axis=0)
            if merged_optics['rlnOpticsGroup'].iloc[0] != file['optics']['rlnOpticsGroup'].iloc[0]:
                merged_optics = pd.concat([merged_optics, file['optics']], axis=0)

    # TODO: Add All the Starfiles to the input/import.json

    # Write the Merged DataFrame to New StarFile
    if os.path.exists(output):

    starfile.write({'optics': merged_optics, 'particles': merged_particles}, output)

    # Inform the user that the file has been written successfully
    print(f"\nRelion5 Particles STAR file Merged to: {output}\n")
      

if __name__ == "__main__":
    cli()