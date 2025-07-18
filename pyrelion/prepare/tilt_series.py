from pyrelion.prepare.common import add_optics_options
import os, glob, argparse, starfile, click, copick, io
from scipy.spatial.transform import Rotation as R
from pyrelion.utils import sta_tools
from typing import List
from tqdm import tqdm
import pandas as pd
import numpy as np

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings={"show_default": True})
@click.option("--base-project",type=str,required=False,
              default = "/hpc/projects/group.czii/krios1.processing/aretomo3",
              help="Main Aretomo Project Folder Path" )
@click.option("--session",type=str,required=True, default='23dec21',
              help="Session for Generating Relion Experiment")
@click.option("--run",type=str,required=False, default='run001',
              help="Run for Generating Relion Experiment")
@click.option("--output",type=str,required=False, default='input',
              help="Output directory path to write STAR files")
@click.option("--pixel-size",type=float,required=False, default=1.54,
              help="Unbinned Tilt Tilt Series Pixel Size (Å)")
@click.option("--total-dose",type=float,required=False, default=60,
              help="Total Accumulated Dose (e-/Å^2)")
@click.option("--symlinks",type=str,required=False, default=None,
              help="Output directory path for the MRCS symlinks")
@add_optics_options
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
    amplitude_contrast: float,
    optics_group: int,
    optics_group_name: str    
    ):
    """
    Import tilt series data, process alignment and CTF parameters, and generate
    Relion-compatible STAR files for tomograms.
    """

    # Set up output paths and directories
    # Entry to Save in `import.json`
    tiltSeriesHeader = f'{session}_tiltSeries'
    # Path to Output Without TiltSeries Sub-Folder
    output_path = output
    # Create TiltSeries Sub-Folder
    output = os.path.join(output,'tiltSeries')
    os.makedirs(output, exist_ok=True)

    # Log pipeline parameters
    utils = sta_tools.PipelineHelper(None, requireRelion=False)
    utils.print_pipeline_parameters('Importing Tilt-Series', base_project = base_project, session = session, run = run,
                                    output = output, pixel_size = pixel_size, total_dose = total_dose, 
                                    voltage = voltage, spherical_aberration = spherical_aberration,
                                    amplitude_contrast = amplitude_contrast, header = tiltSeriesHeader, 
                                    file_name=os.path.join(output_path,'import.json'))

    # Locate all CTF parameter files in the project directory
    inputPath = os.path.join( base_project, session, run, '*_CTF.txt')
    print(f'Searching for Data from the Following Search Path: {inputPath}')
    tiltSeries = np.array(glob.glob(inputPath), dtype=str)

    # Ensure the symlink directory exists if specified
    try: 
        if not os.path.isdir(symlinks):
            os.makedirs(symlinks, exist_ok=True)
    except:
        pass

    # Initialize containers for tomogram data
    tiltSeriesDirectory = output
    os.makedirs(tiltSeriesDirectory, exist_ok=True)
    aln_column_names = ['SEC', 'ROT', 'GMAG', 'TX', 'TY', 'SMEAN', 'SFIT', 'SCALE', 'BASE', 'TILT']
    tomoNames = [] # Names of tomograms
    tiltSeriesStarNames = [] # Paths to individual STAR files for tilt series

    # Process Each Tilt Series
    for tomos in tqdm(tiltSeries):
        
        # Read the Tomogram ID and baseTomoPath
        tomoPath = '/'.join(tomos.split('/')[:-1])
        tomoID = '_'.join(tomos.split('/')[-1].split('_')[:-1])

        # Add session and tomogram ID to the list
        tomoNames.append(session + '_' + tomoID)

        # Read the CTF Parameters
        ctfPath = os.path.join(tomoPath, tomoID + '_CTF.txt')
        ctfText = np.loadtxt(ctfPath)

        # Read the AreTomo Alignment Parameters
        alnPath = os.path.join(tomoPath, tomoID + '.aln')

        # Read file until we hit the Local Alignment section
        with open(alnPath, 'r') as f:
            content = f.read()
        
        # Split at Local Alignment marker (If Provided)
        before_local = content.split('# Local Alignment')[0]

        # Parse with pandas, skipping comment lines
        alnDF = pd.read_csv(io.StringIO(before_local), 
                        comment='#',  # Skip lines starting with #
                        sep='\s+',    # Whitespace separator
                        names=aln_column_names)

        # Read Acqusition Order List
        orderListPath = os.path.join(tomoPath, tomoID + '_Imod', tomoID + '_order_list.csv')
        orderList = np.genfromtxt(orderListPath, delimiter=',', skip_header=1)
        totalExposure = [] 

        # Initialize containers for tilt series metadata
        totalExposure = []  # Cumulative electron dose for each tilt
        tomoYtilt = []  # Tilt angles
        tomoZRot = []  # Rotations around Z-axis
        tomoXshift = []  # Shifts along X-axis
        tomoYshift = []  # Shifts along Y-axis
        tiltSeriesNames = []  # Filenames of tilt images
        ctfImageNames = []  # Filenames of CTF images
        defocusU = []  # Defocus U values
        defocusV = []  # Defocus V values
        defocusAngle = []  # Defocus angle values        

        # Handle symlinks for MRC stack files
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

        # Iterate Through the Alignment File
        nTilts = orderList.shape[0]
        for tiltInd in range(len(alnDF)):

            # Determine the Tilt Index from the Alignment File
            ind = int(alnDF.iloc[tiltInd]['SEC'])
            tiltSeriesName_id = f'{ind}@{tiltSeriesName}'
            tiltSeriesNames.append(tiltSeriesName_id)
            ctfImageName_id = f'{ind}@{ctfImageName}'
            ctfImageNames.append(ctfImageName_id)

            # Get the Tomogram Tilt Parameters from the Alignment File
            tomoYtilt.append(alnDF['TILT'][tiltInd])
            tomoXshift.append(alnDF['TX'][tiltInd] * pixel_size)
            tomoYshift.append(alnDF['TY'][tiltInd] * pixel_size)

            # Get the Defocus Parameters from the CTF Text File
            defocusU.append(ctfText[ind-1, 1])
            defocusV.append(ctfText[ind-1, 2])
            defocusAngle.append(ctfText[ind-1, 3])

            # Get the Total Exposure from the Order List
            acqNum = np.argmin( np.abs(orderList[:,1] - alnDF['TILT'][tiltInd]) )
            offset = 0 # old offset was 1, is this correct?
            totalExposure.append( total_dose / nTilts * (orderList[acqNum,0] - offset) )

        # Get Number of Rows for the STAR file
        num_rows = len(tiltSeriesNames)

        # Save TS_XX_YY starfile
        ts_dict = {}
        ts_dict['rlnMicrographName'] = tiltSeriesNames
        ts_dict['rlnTomoXTilt'] = [0] * num_rows
        ts_dict['rlnTomoYTilt'] = tomoYtilt
        ts_dict['rlnTomoZRot'] = alnDF['ROT'].tolist()
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
        starfile.write({session + '_' + tomoID: pd.DataFrame(ts_dict)}, writeTSpath, overwrite=True)
        tiltSeriesStarNames.append(writeTSpath)

    # Create global STAR file for all aligned tilt series (aligned_tilt_series.star)
    nRows = len(tomoNames)
    aligned_ts = {
        'rlnTomoName': tomoNames,
        'rlnVoltage': [voltage] * nRows,
        'rlnSphericalAberration': [spherical_aberration] * nRows,
        'rlnAmplitudeContrast': [amplitude_contrast] * nRows,
        'rlnMicrographOriginalPixelSize': [pixel_size] * nRows,
        'rlnTomoHand': [-1] * nRows,
        'rlnOpticsGroupName': [optics_group_name] * nRows,
        'rlnTomoTiltSeriesPixelSize': [pixel_size] * nRows,
        'rlnTomoTiltSeriesStarFile': tiltSeriesStarNames,
    }
    fn = os.path.join(tiltSeriesDirectory, "aligned_tilt_series.star")
    starfile.write({"global": pd.DataFrame(aligned_ts)}, fn, overwrite=True)

    # Inform the user that the file has been written successfully
    print(f"\nRelion5 Tomograms STAR file saved to: {fn}\n")    

###########################################################################################

@cli.command(context_settings={"show_default": True})
@click.option( "--input", type=str, required=True, multiple=True,    
               help="StarFiles to Merge for STA Pipeline" )
@click.option( "--output", type=str, required=False,
               default="input/aligned_tilt_series.star",
               help="Output Filename to Write Merged Starfile" )
def combine_star_files_tomograms(
    input: List[str],
    output: str
    ):
    """
    Combine multiple starfiles into a single starfile.
    """

    # Iterate Through all Input StarFiles
    for ii in range(len(input)):

        filename = input[ii]
        print(f'Adding {filename} to the Merged StarFile')
        file = starfile.read(filename)

        if ii == 0:
            merged_alignments = file   
        else:
            merged_alignments = pd.concat([merged_alignments, file], axis=0)

    # TODO: Add All the Starfiles to the input/import.json

    # Write the Merged DataFrame to New StarFile
    # if os.path.exists(output):

    starfile.write({'global': merged_alignments}, output)

    # Inform the user that the file has been written successfully
    print(f"\nRelion5 Particles STAR file Merged to: {output}\n")  

@cli.command(context_settings={"show_default": True})
@click.option("--particles",type=str,required=True,
              help="Path to Particles Starfile")
@click.option("--tomograms",type=str,required=True,
              help="Path to Tomograms Starfile")
def remove_unused_tomograms(particles:str, tomograms:str):
    """
    Remove tomograms that dont contain any particles.
    """
    
    # Check to make sure file exists
    if not os.path.exists(particles):
        raise FileNotFoundError(f"Particles file {particles} does not exist.")
    if not os.path.exists(tomograms):
        raise FileNotFoundError(f"Tomograms file {tomograms} does not exist.")

    # Read the Particles Starfile
    particles = starfile.read(particles)

    # Read the Tomograms Starfile
    tomogramsDF = starfile.read(tomograms)

    # Get the Tomogram Names
    full_tomogram_names = tomogramsDF['rlnTomoName']
    used_tomogram_names = particles['particles']['rlnTomoName']

    # Remove the Unused Tomograms
    tomogramsDF = tomogramsDF[tomogramsDF['rlnTomoName'].isin(used_tomogram_names)]

    # Write the New Tomograms Starfile
    starfile.write({'global': tomogramsDF}, tomograms)

    # Inform the user that the file has been written successfully
    print(f"\nRelion5 Particles STAR file Merged to: {tomograms}\n")  
