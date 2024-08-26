import os, glob, argparse
import starfile, click
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
    tomoNames = [];
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

        tomoNames.append(tomoID)

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
    print(f"Relion5 Tomograms STAR file saved to: {fn}")    

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
def import_particles(
    input: str,
    output: str,
    x: float,
    y: float,
    z: float,
    pixel_size: float,
    voltage: float, 
    spherical_aberration: float, 
    amplitude_contrast: float
    ):

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
    # inputDF['rlnTomoName'] = inputDF['rlnTomoName'].str.replace('_Vol', '')

    # Assign a default optics group value to all particles
    inputDF['rlnOpticsGroup'] = [1] * len(inputDF['rlnTomoName'])

    # Set default output file name if not provided
    if output is None: 
        output = 'input/full_picks.star'

    # Create optics group metadata as a dictionary
    optics = {
        'rlnOpticsGroup': '1',
        'rlnOpticsGroupName': 'opticsGroup1',
        'rlnSphericalAberration': spherical_aberration,
        'rlnVoltage': voltage,
        'rlnAmplitudeContrast': amplitude_contrast,
        'rlnTomoTiltSeriesPixelSize': [pixel_size]
    }    

    # Write the optics and particles data to a new STAR file
    starfile.write({'optics': pd.DataFrame(optics), "particles": inputDF}, output)

    # Inform the user that the file has been written successfully
    print(f"Relion5 Particles STAR file saved to: {output}")

if __name__ == "__main__":
    cli()