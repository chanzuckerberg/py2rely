from py2rely.prepare.common import add_optics_options
from py2rely import cli_context
from typing import List
import rich_click as click

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings=cli_context, no_args_is_help=True)
@click.option("--base-project",type=str,required=False,
              default = "/hpc/projects/group.czii/krios1.processing/aretomo3",
              help="Main Aretomo Project Folder Path" )
@click.option("-s","--session",type=str,required=True, default='23dec21',
              help="Session for Generating Relion Experiment")
@click.option("-r","--run",type=str,required=False, default=None,
              help="Run for Generating Relion Experiment")
@click.option("-o","--output",type=str,required=False, default='input',
              help="Output directory path to write STAR files")
@click.option("-ps","--pixel-size",type=float,required=False, default=1.54,
              help="Unbinned Tilt Tilt Series Pixel Size (Å)")
@click.option("-td","--total-dose",type=float,required=False, default=60,
              help="Total Accumulated Dose (e-/Å^2)")
@click.option("-sym","--symlinks",type=str,required=False, default=None,
              help="Output directory path for the MRCS symlinks")
@add_optics_options
def tilt_series(
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
    Relion5-compatible STAR files for tomograms.

    How does py2rely find my data?
    ------------------------------

    Given --base-project, --session, and optionally --run, py2rely searches
    for alignment and CTF files using the following full search path:

        {base-project}/{session}/{run}/*_CTF.txt

    If --run is omitted, all runs within the session directory are searched:

        {base-project}/{session}/*_CTF.txt

    For each matching tilt series, the corresponding:

        - .mrc (tilt stack)
        - .aln (AreTomo alignment file)
        - _order_list.csv (IMOD acquisition order)
        - _CTF.txt (CTF parameters)

    are parsed to construct Relion5 tilt-series STAR files.
    """

    run_import_tilt_series(
        base_project, session, run, output, pixel_size, total_dose, symlinks, 
        voltage, spherical_aberration, amplitude_contrast, optics_group, optics_group_name
    )


def run_import_tilt_series(
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

    from py2rely.utils.progress import _progress, get_console
    import os, glob, starfile, mrcfile, io
    from py2rely.utils import sta_tools
    from rich.panel import Panel
    import pandas as pd
    import numpy as np

    # Get the rich-click console
    console = get_console()
    
    # Log pipeline parameters
    os.makedirs(output, exist_ok=True)    
    tiltSeriesHeader = f'{session}_tiltSeries'
    console.rule("[bold cyan]Importing Tilt-Series")
    utils = sta_tools.PipelineHelper(None, requireRelion=False)
    utils.print_pipeline_parameters('Importing Tilt-Series', base_project = base_project, session = session, run = run,
                                    output = output, pixel_size = pixel_size, total_dose = total_dose, 
                                    voltage = voltage, spherical_aberration = spherical_aberration,
                                    amplitude_contrast = amplitude_contrast, header = tiltSeriesHeader, 
                                    file_name=os.path.join(output,'import.json'))

    # Locate all CTF parameter files in the project directory
    run = run or ''
    inputPath = os.path.join(base_project, session, run, '*_CTF.txt')
    console.print(Panel.fit(f"[b white]Search path[/b white]\n{inputPath}", border_style="blue"))
    all_tiltSeries = np.array(glob.glob(inputPath), dtype=str)

    # Filter out tiltseries with different pixel size
    tiltSeries = []
    removed_tiltSeries =[]
    for ts_ctf_path in all_tiltSeries:
        tsPath = ts_ctf_path.replace('_CTF.txt', '.mrc')
        with mrcfile.open(tsPath, 'r', header_only=True) as mrc:
            if np.isclose(mrc.voxel_size.x, pixel_size) and np.isclose(mrc.voxel_size.y, pixel_size):
                tiltSeries.append(ts_ctf_path)
            else:
                removed_tiltSeries.append(ts_ctf_path)

    if removed_tiltSeries:
        console.print(f"[yellow]⚠ Removed {len(removed_tiltSeries)} tilt series != {pixel_size} Å.[/yellow]")
    if not tiltSeries:
        console.print(f"[red]❌ No tilt series found with pixel size {pixel_size} Å.[/red]")
        return

    # Ensure the symlink directory exists if specified
    try: 
        if not os.path.isdir(symlinks):
            os.makedirs(symlinks, exist_ok=True)
    except:
        pass

    # Create TiltSeries Sub-Folder
    tiltSeriesDirectory = os.path.join(output, f'{session}_tiltSeries')
    os.makedirs(tiltSeriesDirectory, exist_ok=True)
    
    # Initialize containers for tomogram data
    aln_column_names = ['SEC', 'ROT', 'GMAG', 'TX', 'TY', 'SMEAN', 'SFIT', 'SCALE', 'BASE', 'TILT']
    tomoNames = [] # Names of tomograms
    tiltSeriesStarNames = [] # Paths to individual STAR files for tilt series

    # Process Each Tilt Series
    for tomos in _progress(tiltSeries, description="Importing Tilt Series"):
        
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
        defocusU = []  # Defocus U values
        defocusV = []  # Defocus V values
        defocusAngle = []  # Defocus angle values
        phase_shift = []

        # Handle symlinks for MRC stack files
        if symlinks is None:
            tiltSeriesName = f'{tomoPath}/{tomoID}.mrcs'
            if not os.path.isfile(tiltSeriesName):
                os.symlink(f'{tomoID}.mrc', tiltSeriesName)
        else:
            tiltSeriesName = os.path.join(symlinks, f'{tomoID}.mrcs')

            tiltSeriesNameAbs = os.path.abspath(f'{tomoPath}/{tomoID}.mrc')

            if not os.path.isfile(tiltSeriesName):
                os.symlink(tiltSeriesNameAbs, tiltSeriesName)

        # Iterate Through the Alignment File
        nTilts = orderList.shape[0]
        for tiltInd in range(len(alnDF)):

            # Determine the Tilt Index from the Alignment File
            ind = int(alnDF.iloc[tiltInd]['SEC'])
            tiltSeriesName_id = f'{ind}@{tiltSeriesName}'
            tiltSeriesNames.append(tiltSeriesName_id)

            # Get the Tomogram Tilt Parameters from the Alignment File
            tomoYtilt.append(alnDF['TILT'][tiltInd])
            tomoXshift.append(alnDF['TX'][tiltInd] * pixel_size)
            tomoYshift.append(alnDF['TY'][tiltInd] * pixel_size)

            # Get the Defocus Parameters from the CTF Text File
            defocusU.append(ctfText[ind-1, 1])
            defocusV.append(ctfText[ind-1, 2])
            defocusAngle.append(ctfText[ind-1, 3])

            # Get phase shift information
            phase_shift.append(float(ctfText[ind-1, 4]) * 180.0 / np.pi)  # Convert from radians to degrees

            # Get the Total Exposure from the Order List
            acqNum = np.argmin( np.abs(orderList[:,1] - alnDF['TILT'][tiltInd]) )
            totalExposure.append( total_dose / nTilts * (orderList[acqNum,0] - 1) )

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
        ts_dict['rlnDefocusU'] = defocusU
        ts_dict['rlnDefocusV'] = defocusV
        ts_dict['rlnDefocusAngle'] = defocusAngle
        ts_dict['rlnPhaseShift'] = phase_shift
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
        'rlnTomoSizeX': [0] * nRows, # need 0s at least because of RELION bug.
        'rlnTomoSizeY': [0] * nRows,
        'rlnTomoSizeZ': [0] * nRows,
    }
    fn = os.path.join(tiltSeriesDirectory, "aligned_tilt_series.star")
    starfile.write({"global": pd.DataFrame(aligned_ts)}, fn, overwrite=True)

    # Inform the user that the file has been written successfully
    console.rule("[bold green]Done")
    console.print(f"[b]Relion5 Tilt-Series STAR file saved to:[/b] {fn}\n")  

###########################################################################################

@cli.command(context_settings=cli_context, no_args_is_help=True)
@click.option( "-i","--input", type=str, required=True, multiple=True,    
               help="StarFiles to Merge for STA Pipeline" )
@click.option( "-o","--output", type=str, required=False,
               default="input/aligned_tilt_series.star",
               help="Output Filename to Write Merged Starfile" )
def combine_tilt_series(
    input: List[str],
    output: str
    ):
    """
    Combine multiple starfiles for tilt series.
    """

    run_combine_tilt_series(
        input, output
    )

def run_combine_tilt_series(
    input: List[str],
    output: str
    ):

    from py2rely.utils.progress import get_console
    from py2rely.utils.progress import _progress
    import os, starfile
    import pandas as pd

    console = get_console()
    console.rule("[bold cyan]Combine Tilt-Series")
    console.print(f"[b]Output:[/b] {output}")
    console.print()

    # Iterate Through all Input StarFiles
    for ii in _progress(range(len(input)), description="Combining Tilt-Series"):

        filename = input[ii]
        console.print(f"[b]Adding[/b] {filename} to the Merged StarFile")
        file = starfile.read(filename)

        if ii == 0:
            merged_alignments = file   
        else:
            merged_alignments = pd.concat([merged_alignments, file], axis=0)

    # TODO: Add All the Starfiles to the input/import.json

    # Write the Merged DataFrame to New StarFile
    # if os.path.exists(output):

    if not os.path.exists(os.path.dirname(output)):
        os.makedirs(os.path.dirname(output))

    starfile.write({'global': merged_alignments}, output)

    # Inform the user that the file has been written successfully
    n_files = len(input)
    n_rows = len(merged_alignments)

    input_list = ", ".join([os.path.basename(f) for f in input])
    console.rule("[bold green]Merged")
    console.print(
        f"[green]Successfully merged {n_files} tilt-series starfile(s):[/green]\n"
        f"   {input_list}\n"
        f"→ Combined [b]{n_rows:,.0f}[/b] total entries into '[b]{output}[/b]'.\n"
    )
    
@cli.command(context_settings=cli_context, no_args_is_help=True)
@click.option("-p","--particles",type=str,required=True,
              help="Path to Particles Starfile")
@click.option("-t","--tomograms",type=str,required=True,
              help="Path to Tomograms Starfile")
def filter_unused_tilts(particles:str, tomograms:str):
    """
    Remove tomograms that dont contain any particles.
    """

    run_filter_unused_tilts(
        particles, tomograms
    )

def run_filter_unused_tilts(
    particles: str,
    tomograms: str
    ):
    from py2rely.utils.progress import get_console
    from rich.panel import Panel
    import os, starfile

    console = get_console()
    console.rule("[bold cyan]Filter Unused Tilts")

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
    initial_count = len(tomogramsDF)
    tomogramsDF = tomogramsDF[tomogramsDF['rlnTomoName'].isin(used_tomogram_names)]
    removed_count = initial_count - len(tomogramsDF)

    # Write the New Tomograms Starfile
    starfile.write({'global': tomogramsDF}, tomograms)

    # Inform the user that the file has been written successfully
    console.print(Panel.fit(
        f"[b]Removed:[/b] {removed_count}\n[b]Remaining:[/b] {len(tomogramsDF)}\n[b]File:[/b] {tomograms}",
        title="[bold green]Completed",
        border_style="green"
    ))
