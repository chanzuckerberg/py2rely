from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
from scipy.spatial.transform import Rotation as R
import pipeliner.job_manager as job_manager
import json, click, starfile, os
from tqdm import tqdm
import numpy as np 
import copick

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type=str,
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--class-job",
    type=str,
    required=True,
    default="job001",
    help="Job that Classes will Be Extracted",
)
@click.option(
    "--export-classes",
    type=str,
    required=True,
    help="Best 3D Classes for Sub-Sequent Refinement"
)
@click.option(
    "--export-path",
    type=str,
    required=True,
    help="Path to Export New Classes",
)
def starfile(
    parameter_path: str, 
    class_job: str,     
    export_classes: str,
    export_path: str,
    ):
    """
    Export DesiredClasses from Class3D Job to New Starfile
    """

    # Split the comma-separated string into a list of integers
    keep_classes = [int(x) for x in keep_classes.split(',')]

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')    

    print(f'\n[Export Class] Exporting Classes {export_class} from Class3D/{class_job} to {export_path}\n')

    classParticles = utils.find_final_iteration(class_job)

    utils.custom_select(
        classParticles,
        export_classes,
        uniqueExport = export_path
    )

    # Create Symlink for tomograms and any other necessary data

@cli.command(context_settings={"show_default": True})
@click.option(
    "--particles-path",
    type=str,
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--config-paths",
    type=str,
    required=True,
    default="job001",
    help="Comma Separated List of Config Files to Export Particles Too",
)
@click.option(
    "--sessions",
    type=str,
    required=True,
    default="23dec25",
    help="Comma Separated List of Sessions Associated with Particles",
)
@click.option(
    "--particle-name",
    type=str,
    required=True,
    default='ribosome',
    help='Particle Name to Save Copick Query'
)
@click.option(
    "--export-user-id",
    type=str,
    required=False,
    default="relion",
    help="UserID to Export Picks"
)
@click.option(
    "--export-session-id",
    type=str,
    required=False,
    default="99",
    help="SessionID to Export Picks"
)
@click.option(
    "--dim-x",
    type=int,
    required=False,
    default=4096,
    help="Box size along the x-axis in the tomogram."
)
@click.option(
    "--dim-y",
    type=int,
    required=False,
    default=4096,
    help="Box size along the y-axis in the tomogram."
)
@click.option(
    "--dim-z",
    type=int,
    required=False,
    default=1200,
    help="Box size along the z-axis in the tomogram."
)
def copick(
    particles_path: str, 
    config_paths: str,
    sessions: str,
    particle_name: str,
    export_user_id: str, 
    export_session_id: int,
    dim_x: int,
    dim_y: int, 
    dim_z: int    
    ):
    """
    Export Particles Starfile into Corresponding Copick Projects
    """

    # Read Particles from StarFile
    df = starfile.read(particles_path)
    pixel_size = df['optics']['rlnTomoTiltSeriesPixelSize'].iloc[0]
    particles = df['particles']

    configs = config_paths.split(',')
    sessions = sessions.split(',')    

    # Check Possible Export Sessions 
    export_sessions = particles['rlnTomoName'].str.split('_').str[0].unique()

    if len(configs) != len(sessions):
        print(f'Error: The number of config files ({len(configs)}) does not match the number of sessions ({len(sessions)}).')
        exit()

    # Check if sessions are in export_sessions
    missing_sessions = [session for session in sessions if session not in export_sessions]

    # If there are missing sessions, exit and inform the user
    if missing_sessions:
        print(f"Error: The following session(s) are not available: {missing_sessions}")
        print(f"Available sessions are: {export_sessions}")
        # Exit early or raise an error as needed
        exit()

    copick_roots = {}
    for ii in range(len(configs)):
        copick_roots[sessions[ii]] = copick.from_file(configs[ii])

    uniqueRuns = np.unique(particles['rlnTomoName'])   
    for uniqueRun in tqdm(uniqueRuns):
        
        # Get Data Associated with Particle
        data = particles.iloc[ii]
        
        # Extract the Associated Session and Run to Export too
        mysession = uniqueRun.split('_')[0]
        myrun = '_'.join(uniqueRun.split('_')[1:])
        
        # Pull Out All Points with Associated Run
        rlnPoints = particles[particles['rlnTomoName'] == uniqueRun]
        numPoints = rlnPoints.shape[0]
        points = np.zeros([numPoints,3])
        orientations = np.zeros([numPoints, 4, 4])       
        for jj in range(numPoints):

            # Pull Out Coordinates
            # cx = rlnPoints.iloc[jj]['rlnCenteredCoordinateXAngst'] * pixel_size + dim_x / 2
            # cy = rlnPoints.iloc[jj]['rlnCenteredCoordinateYAngst'] * pixel_size + dim_y / 2
            # cz = rlnPoints.iloc[jj]['rlnCenteredCoordinateZAngst'] * pixel_size + dim_z / 2           

            cx = rlnPoints.iloc[jj]['rlnCenteredCoordinateXAngst'] + ( dim_x / 2 ) * pixel_size
            cy = rlnPoints.iloc[jj]['rlnCenteredCoordinateYAngst'] + ( dim_y / 2 ) * pixel_size
            cz = rlnPoints.iloc[jj]['rlnCenteredCoordinateZAngst'] + ( dim_z / 2 ) * pixel_size

            points[jj,] = np.array([cx,cy,cz])

            # Pull Out Orientation
            euler = np.array([rlnPoints.iloc[jj]['rlnAngleRot'], 
                              rlnPoints.iloc[jj]['rlnAngleTilt'], 
                              rlnPoints.iloc[jj]['rlnAnglePsi']])
            rot = R.from_euler('ZYZ', euler, degrees=True)
            orientations[jj,:3,:3] = rot.inv().as_matrix()
        orientations[:,3,3] = 1

        # Write Points to Associated Run
        root = copick_roots[mysession]
        run = root.get_run(myrun + '_Vol')

        picks = run.new_picks(object_name = particle_name, user_id=export_user_id, session_id = export_session_id)
        picks.from_numpy(points, orientations)