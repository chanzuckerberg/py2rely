from py2rely.prepare import common
from py2rely import cli_context
from typing import List
import click

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings=cli_context)
@click.option("-i","--input", type=str, required=True, help="Input STAR-file with coordinates")
@click.option("-o","--output", type=str, default='full_picks.star', help="Output STAR-file")
@common.add_common_options
@common.add_optics_options
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
    """
    Import particles from STAR files.
    """

    run_import_particles(
        input, output, x, y, z, pixel_size, 
        voltage, spherical_aberration, amplitude_contrast, 
        optics_group, optics_group_name
    )


def run_import_particles(
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
    """
    Import particles from STAR files.

    Args:   
        -i, --input: Input STAR-file with coordinates
        -o, --output: Output STAR-file
        -x: X dimension of the tomogram
        -y: Y dimension of the tomogram
        -z: Z dimension of the tomogram
        -pixel_size: Pixel size of the tomogram
        -voltage: Voltage of the tomogram
        -spherical_aberration: Spherical aberration of the tomogram
        -amplitude_contrast: Amplitude contrast of the tomogram
    """
    from py2rely.utils import sta_tools
    import os, starfile
    import pandas as pd

    utils = sta_tools.PipelineHelper(None, requireRelion=False)
    utils.print_pipeline_parameters(
        'Importing Particles', input = input, output = output, 
        x = x, y = y, z = z, pixel_size = pixel_size, voltage = voltage, 
        spherical_aberration = spherical_aberration, amplitude_contrast = amplitude_contrast,
        header = f'particles', file_name=os.path.join(output,'import.json')
    )                               

    # Read the input STAR file into a DataFrame
    inputDF = starfile.read(input)
    inputDF = common.process_coordinates(inputDF, x, y, z, pixel_size)

    # if name is not None:
    #     inputDF["rlnTomoName"] = name

    # Set default output file name if not provided
    if output is None: 
        output = 'input/full_picks.star'

    # Create optics group metadata as a dictionary
    optics = common.create_optics_metadata(pixel_size, voltage, spherical_aberration, amplitude_contrast, optics_group, optics_group_name)

    # Write the optics and particles data to a new STAR file
    starfile.write({'optics': pd.DataFrame(optics), "particles": inputDF}, output)

    # Inform the user that the file has been written successfully
    print(f"\nRelion5 Particles STAR file saved to: {output}\n")

###########################################################################################

@cli.command(context_settings=cli_context)
@click.option("-c","--config", type=str, required=True, help="Path to Copick Config")
@click.option("-s","--session", type=str, required=True, help="Experiment Session")
@click.option("-o","--output", type=str, default="input", help="Path to write STAR file")
@click.option("-n","--name", type=str, required=True, help="Protein Name")
@click.option("-sid","--session-id", type=str, default=None, help="Session ID")
@click.option("-uid","--user-id", type=str, default=None, help="User ID")
@click.option("-rids","--run-ids", type=str, default=None, help="Run IDs to filter (comma-separated)")
@click.option("-vs","--voxel-size", type=float, default=None, help="Voxel Size of Picked Particles' Tomograms")
@common.add_common_options
@common.add_optics_options
@click.option('--relion5', type=bool, required=False, default=True, help='Use Relion5 Centered Coordinate format for the output STAR file')
def particles(
    config: str, session: str, name: str, output: str, pixel_size: float,
    voxel_size: float, session_id: str, user_id: str, run_ids: str, x: float,
    y: float, z: float, voltage: float, spherical_aberration: float, amplitude_contrast: float,
    optics_group: int, optics_group_name: str, relion5: bool
    ):
    """Import particles from Copick project.
    """    

    run_import_particles(
        config, session, name, output, pixel_size, voxel_size, 
        session_id, user_id, run_ids, x, y, z, voltage, 
        spherical_aberration, amplitude_contrast, optics_group, optics_group_name, relion5
    )

def run_import_particles(
    config: str,  session: str,
    name: str, output: str, pixel_size: float, voxel_size: float, 
    session_id: str, user_id: str, run_ids: str, x: float, y: float, 
    z: float, voltage: float, spherical_aberration: float, amplitude_contrast: float,
    optics_group: int, optics_group_name: str, relion5: bool
    ):
    """
    Import particles from Copick project.
    
    Args:
        -c, --config: Path to Copick Config
        -s, --session: Experiment Session
        -n, --name: Protein Name
        -o, --output: Path to write STAR file
        -sid, --session-id: Session ID
        -uid, --user-id: User ID
        -rids, --run-ids: Run IDs to filter (comma-separated)
        -vs, --voxel-size: Voxel Size of Picked Particles' Tomograms
        -x, --x: X Dimension of Tomograms
        -y, --y: Y Dimension of Tomograms
        -z, --z: Z Dimension of Tomograms
        -pixel-size: Pixel Size of Tilt Series
        -voltage: Voltage of Tomograms
        -spherical-aberration: Spherical Aberration
        -amplitude-contrast: Amplitude Contrast
        -optics-group: Optics Group Number
        -optics-group-name: Optics Group Name
        -relion5: Use Relion5 Centered Coordinate format for the output STAR file
    """    
    from scipy.spatial.transform import Rotation as R
    from py2rely.utils import sta_tools
    from tqdm import tqdm
    import os, starfile
    import pandas as pd
    import numpy as np
    import copick

    # Provide warning if userID and sessionID are not provided
    if session_id is None and user_id is None:
        print(f"\n[WARNING]: No sessionID or userID provided, using a random entry for {copick_name}!")
        print('Please consider providing a sessionID or userID to ensure proper importing of the coordinates.\n')

    # Determine Which Write Path Based On Copick Query
    if session_id is not None and user_id is not None:
        fname = f'{user_id}_{session_id}_{name}'
    elif user_id is not None:
        fname = f'{user_id}_{name}'
    elif session_id is not None: # Assume user_id is not None
        fname = f'{session_id}_{name}'
    else:
        fname = copick_name
    fname =  session + '_' + fname

    # Specify Output Path
    os.makedirs(output, exist_ok=True)
    writePath = os.path.join( output, f'{fname}.star' )          

    utils = sta_tools.PipelineHelper(None, requireRelion=False)
    utils.print_pipeline_parameters(
        'Gathering Copick Particles', config = config, output_path = writePath, 
        copick_name = name, copick_session_id = session_id, copick_user_id = user_id, 
        pixel_size = pixel_size, voxel_size = voxel_size, tomo_dim_x = x, tomo_dim_y = y, tomo_dim_z = z, voltage = voltage, 
        spherical_aberration = spherical_aberration, amplitude_contrast = amplitude_contrast, 
        optics_group = optics_group, optics_group_name = optics_group_name, 
        header = fname, file_name=f'{output}/import.json'
    )       

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
    if run_ids is None:
        run_ids = [run.name for run in root.runs]
    else:
        run_ids = run_ids.split(',')
        run_ids = [run_id.strip() for run_id in run_ids]

    if voxel_size is not None:
        run_ids = [run_id for run_id in run_ids if root.get_run(run_id).get_voxel_spacing(voxel_size) is not None]
        skipped_run_ids = [run_id for run_id in run_ids if root.get_run(run_id).get_voxel_spacing(voxel_size) is None]
        if skipped_run_ids: 
                print(f"Warning: skipping runs with no voxel spacing {voxel_size}: {skipped_run_ids}")

    for runID in tqdm(run_ids):

        # Query CopickRun and Picks
        run = root.get_run(runID)
        picks = run.get_picks(object_name = name, session_id = session_id, user_id = user_id)

        if picks is None or len(picks) == 0:
            print(f"Warning: no picks found for {runID}")
            continue

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
    if relion5:
        myStarFile["rlnCenteredCoordinateXAngst"] = (np.array(myStarFile["rlnCoordinateX"]) - x / 2) * pixel_size
        myStarFile["rlnCenteredCoordinateYAngst"] = (np.array(myStarFile["rlnCoordinateY"]) - y / 2) * pixel_size
        myStarFile["rlnCenteredCoordinateZAngst"] = (np.array(myStarFile["rlnCoordinateZ"]) - z / 2) * pixel_size

    # Make sure that there are particles to import
    if all(
        isinstance(v, (list, np.ndarray, pd.Series)) and len(v) == 0 
        for v in myStarFile.values()
    ):
        print("\n[WARNING]: No Particles Found for that Given Query\n")
        return

    # Convert From Dictionary to DataFrame
    myStarFile = pd.DataFrame(myStarFile)

    # Remove '_Vol' substring
    myStarFile['rlnTomoName'] = myStarFile['rlnTomoName'].str.replace('_Vol', '')

    # Assign a default optics group value to all particles
    myStarFile['rlnOpticsGroup'] = [optics_group] * len(myStarFile['rlnTomoName'])

    # Create optics group metadata as a dictionary
    optics = common.create_optics_metadata(pixel_size, voltage, spherical_aberration, amplitude_contrast, optics_group, optics_group_name)

    # Write the optics and particles data to a new STAR file
    starfile.write({'optics': pd.DataFrame(optics), "particles": myStarFile}, writePath)

    # # Inform the user that the file has been written successfully
    print(f"\n✅ Relion5 Particles STAR file saved to: {writePath}\n")      

@cli.command(context_settings={"show_default": True})
@click.option(
    "-i","--input",
    type=str,
    required=True,
    multiple=True,    
    help="StarFiles to Merge for STA Pipeline"
)
@click.option(
    "-o","--output",
    type=str,
    required=False,
    default="input/full_picks.star",
    help="Output Filename to Write Merged Starfile"
)
def combine_particles(
    input: List[str],
    output: str
    ):
    """Combine multiple starfiles for particles."""

    run_combine_particles(
        input, output
    )

def run_combine_particles(
    input: List[str],
    output: str
    ):
    import pandas as pd
    import os, starfile

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
    # if os.path.exists(output):

    if not os.path.exists(os.path.dirname(output)):
        os.makedirs(os.path.dirname(output))

    starfile.write({'optics': merged_optics, 'particles': merged_particles}, output)

    # Inform the user that the merge is complete
    n_files = len(input)
    n_particles = len(merged_particles)
    n_optics = len(merged_optics)
    input_list = ", ".join([os.path.basename(f) for f in input])

    if n_files == 1:
        print(f"\nℹ️ Only one input file provided. '{input_list}' copied to '{output}'.\n")
    else:
        print(
            f"\n✅ Successfully merged {n_files} particle starfile(s):\n"
            f"   {input_list}\n"
            f"→ Combined {n_particles:,} total particles across {n_optics:,} optics groups into '{output}'.\n"
        )


###########################################################################################

@cli.command(context_settings=cli_context)
@click.option("-i","--input", type=str, required=True, help="Input STAR-file with coordinates")
@click.option("-o","--output", type=str, default='input', help="Output folder to save STAR-file as 'picks.star'")
@click.option("-b","--binning-factor", type=float, default=4, required=True, help='Binning factor for the tomogram')
@common.add_common_options
@common.add_optics_options
def import_pytom_particles(
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
    optics_group_name: str,
    binning_factor: float
    ):
    run_import_pytom_particles(
        input, output, x, y, z, pixel_size, 
        voltage, spherical_aberration, amplitude_contrast, 
        optics_group, optics_group_name, binning_factor
    )

def run_import_pytom_particles(
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
    optics_group_name: str,
    binning_factor: float
    ):

    from py2rely.utils import sta_tools
    from tqdm import tqdm
    import os, starfile
    import pandas as pd
    import glob

    # Create output directory if it doesn't exist
    os.makedirs(output, exist_ok=True)

    """Import particles from STAR files (e.g, PyTom)."""
    utils = sta_tools.PipelineHelper(None, requireRelion=False)
    utils.print_pipeline_parameters(
        'Importing Particles', input = input, output = output, 
        x = x, y = y, z = z, pixel_size = pixel_size, voltage = voltage, 
        spherical_aberration = spherical_aberration, amplitude_contrast = amplitude_contrast,
        header = f'particles', file_name=f'{output}/import.json')    
    output = os.path.join(output, 'picks.star')                  

    # Read and concatenate all input STAR files into a single DataFrame
    all_particles = []
    star_files = glob.glob(os.path.join(input, '*.star'))
    
    if not star_files:
        raise ValueError(f"No STAR files found in {input}")
        
    for fname in tqdm(star_files):
        print(f"Processing {fname}")
        # Read the input STAR file into a DataFrame
        df = starfile.read(fname)

        # Replace 'rlnMicrograph' column with 'rlnTomoName'
        df['rlnTomoName'] = df['rlnMicrographName']
        df = df.drop(columns=['rlnMicrographName'])
        df['rlnCoordinateX'] = df['rlnCoordinateX'] * binning_factor
        df['rlnCoordinateY'] = df['rlnCoordinateY'] * binning_factor
        df['rlnCoordinateZ'] = df['rlnCoordinateZ'] * binning_factor

        # Process the coordinates
        df = common.process_coordinates(df, x, y, z, pixel_size)
        
        # Add to our list of dataframes
        all_particles.append(df)
    
    # Concatenate all dataframes into a single dataframe
    if all_particles:
        inputDF = pd.concat(all_particles, ignore_index=True)
        print(f"Total particles: {len(inputDF)}")
    else:
        print("No particles found in any STAR file")
        return

    # Create optics group metadata as a dictionary
    optics = common.create_optics_metadata(pixel_size, voltage, spherical_aberration, amplitude_contrast, optics_group, optics_group_name)

    # Write the optics and particles data to a new STAR file
    starfile.write({'optics': pd.DataFrame(optics), "particles": inputDF}, output)

    # Inform the user that the file has been written successfully
    print(f"\nRelion5 Particles STAR file saved to: {output}\n")