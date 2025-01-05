from relion_sta_pipeline.prepare.common import add_optics_options
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
    default = "/hpc/projects/group.czii/krios1.processing/aretomo3",
    help="Main Aretomo Project Folder Path"
)
@click.option(
    "--session",
    type=str,
    required=True,
    default='23dec21',
    help="Session for Generating Relion Experiment",
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
    default='input',
    help="Output directory path to write STAR files",
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
    help="Total Accumulated Dose (e-/Å^2)",
)
@click.option(
    "--symlinks",
    type=str,
    required=False,
    default=None,
    help="Output directory path for the MRCS symlinks",
)
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
    utils.print_pipeline_parameters('Importing Tilt-Series', base_project = base_project, session = session, 
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

        # Read IMOD *.xf alignment Parameters 
        xfPath = os.path.join(tomoPath, tomoID + '_Imod', tomoID + '_st.xf')
        xfDF = np.loadtxt(xfPath)

        if len(xfDF.shape) < 2 or xfDF.shape[1] < 6:
            continue

        # Add session and tomogram ID to the list
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
    default="input/aligned_tilt_series.star",
    help="Output Filename to Write Merged Starfile"
)
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