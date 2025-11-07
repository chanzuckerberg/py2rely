from py2rely import cli_context
import click

@click.group(context_settings=cli_context, name='utils')
@click.pass_context
def converters(ctx):
    """
    Convert between different formats
    """
    pass

@converters.command(context_settings=cli_context)
@click.option('-i','--input', type=str, required=True, 
              help='Path to the original star file.')
@click.option('-c','--config', type=str, required=True, 
              help='Path to the copick config file.')
@click.option('-n','--particle-name', type=str, required=True, 
              help='Name of the particle to export.')
@click.option('--user-id', type=str, required=True, 
              help='UserID for the export.')
@click.option('--session-id', type=str, required=True, 
              help='Session ID for the export.')
@click.option('--voxel-size', type=float, required=True, 
              help='Voxel size for the export.')
@click.option('--export-tag', type=str, required=True, 
              help='Tag for the export. We need to remove the .tomostar extension and replace it with the suffix Warp provides for the tomograms.')
def warp_tm2copick(
    input: str,
    config: str, 
    particle_name: str, 
    user_id: str, 
    session_id: int,   
    voxel_size: float,
    export_tag: str,
    ):
    """
    Converts Coordinates from Warp Template Matching to Copick format.
    """

    run_warp_tm_to_copick(
        input, config, particle_name, user_id, session_id, voxel_size, export_tag
    )

def run_warp_tm_to_copick(
    input: str,
    config: str,
    particle_name: str,
    user_id: str,
    session_id: int,
    voxel_size: float,
    export_tag: str):
    from scipy.spatial.transform import Rotation as R
    import starfile, copick
    from tqdm import tqdm
    import numpy as np

    # Read the input file
    particles = starfile.read(input)

    # Read the copick project
    root = copick.from_file(config)
    
    uniqueRuns = np.unique(particles['rlnMicrographName']) 
    for uniqueRun in tqdm(uniqueRuns):
    
        rlnPoints = particles[particles['rlnMicrographName'] == uniqueRun]
        numPoints = rlnPoints.shape[0]
        points = np.zeros([numPoints,3])
        orientations = np.zeros([numPoints, 4, 4])       
        for jj in range(numPoints):
            points[jj,] = np.array([rlnPoints.iloc[jj]['rlnCoordinateX'], rlnPoints.iloc[jj]['rlnCoordinateY'], rlnPoints.iloc[jj]['rlnCoordinateZ']])
            points[jj,] = points[jj,] * voxel_size
            
            # Pull Out Orientation
            euler = np.array([rlnPoints.iloc[jj]['rlnAngleRot'], 
                            rlnPoints.iloc[jj]['rlnAngleTilt'], 
                            rlnPoints.iloc[jj]['rlnAnglePsi']])
            rot = R.from_euler('ZYZ', euler, degrees=True)
            orientations[jj,:3,:3] = rot.inv().as_matrix()
        orientations[:,3,3] = 1

        myrun = uniqueRun.replace('.tomostar', export_tag)
        try:
            root.add_run(myrun)
        except:
            pass

        
        # Get Run and Picks 
        run = root.get_run(myrun)
        # import pdb; pdb.set_trace()
        picks = run.new_picks(object_name = particle_name, user_id = user_id, session_id = session_id)
        picks.from_numpy(points, orientations)

@converters.command(context_settings=cli_context)
@click.option('-i','--input', type=str, required=True, 
    help='Path to the original star file.')
@click.option('-o','--output', type=str, required=True, 
    help='Path to the new star file.')
def ts2position(
    input: str, 
    output: str):
    """
    Converts tomography names in a STAR file:
    1. Replace 'TS_' with 'Position_'.
    2. Remove '_1' if it is at the end of the string.

    Args:
        input (str): Path to the original STAR file.
        output (str): Path to the new STAR file to save the updated data.
    """    

    run_ts_to_position(
        input, output
    )

def run_ts_to_position(
    input: str,
    output: str):
    import starfile, os

    # Check if File Exists, if so Read the original STAR file
    if not os.path.exists(input):
        raise FileNotFoundError(f"Input file {input} does not exist.")
    particles = starfile.read(input)

    # Apply the transformations
    particles['particles']['rlnTomoName'] = particles['particles']['rlnTomoName'].str.replace('TS_', 'Position_')
    particles['particles']['rlnTomoName'] = particles['particles']['rlnTomoName'].str.replace(r'_1$', '', regex=True)
    
    # Write the updated STAR file
    starfile.write(particles, output)