from pipeliner.api.manage_project import PipelinerProject
from scipy.spatial.transform import Rotation as R
import pipeliner.job_manager as job_manager
from pyrelion.utils import relion5_tools
import json, click, starfile, os, copick
from tqdm import tqdm
import numpy as np 

@click.group()
@click.pass_context
def export(ctx):
    """
    Export Coordinates from Relion5 to New Destination
    """
    pass

@export.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path", type=str, required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--class-job", type=str, required=True, default="job001",
    help="Job that Classes will Be Extracted",
)
@click.option(
    "--export-classes", type=str, required=True,
    help="Best 3D Classes for Sub-Sequent Refinement"
)
@click.option(
    "--export-path", type=str, required=True,
    help="Path to Export New Classes",
)
def class2star(
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

@export.command(context_settings={"show_default": True})
@click.option(
    "--particles", type=str, required=True, default="particles.star",
    help="Particles Starfile",
)
@click.option(
    "--configs", type=str, required=True, default="config1.json,config2.json",
    help="Comma Separated List of Config Files to Export Particles Too",
)
@click.option(
    "--sessions", type=str, required=True, default="24aug07a,24jul29c",
    help="Comma Separated List of Sessions Associated with Particles",
)
@click.option(
    "--particle-name", type=str, required=True, default='ribosome',
    help='Particle Name to Save Copick Query'
)
@click.option(
    "--export-user-id", type=str,required=False, default="relion",
    help="UserID to Export Picks"
)
@click.option(
    "--export-session-id", type=str,required=False, default="99",
    help="SessionID to Export Picks"
)
@click.option(
    "--dim-x", type=int, required=False, default=4096,
    help="Box size along the x-axis in the tomogram."
)
@click.option(
    "--dim-y", type=int, required=False, default=4096,
    help="Box size along the y-axis in the tomogram."
)
@click.option(
    "--dim-z", type=int, required=False, default=1200,
    help="Box size along the z-axis in the tomogram."
)
def star2copick(
    particles: str, 
    configs: str,
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

    # Parse User Inputs
    configs = configs.split(',')
    sessions = sessions.split(',')    

    # Check that the number of user provided configs matches the number of sessions
    if len(configs) != len(sessions):
        print(f'[Error]: The number of config files ({len(configs)}) does not match the number of sessions ({len(sessions)}).')
        exit()

    # Read Particles from StarFile
    df = starfile.read(particles)
    pixel_size = df['optics']['rlnTomoTiltSeriesPixelSize'].iloc[0]
    particles = df['particles']

    # Check Possible Export Sessions 
    available_sessions = particles['rlnTomoName'].str.split('_').str[0].unique()

    # Find which requested sessions are actually available
    valid_sessions = [s for s in sessions if s in available_sessions]
    missing_sessions = [s for s in sessions if s not in available_sessions]
    
    # Warn about missing sessions 
    if missing_sessions:
        print('[Warning]: Some specified sessions are not present in the particles star file.')
        print(f'Missing sessions: {missing_sessions}')
        export_sessions = np.array([s for s in export_sessions if s not in missing_sessions])

    # Error if no valid sessions
    if not valid_sessions:
        print(f'[Error]: None of the specified sessions {sessions} are present in the particles star file.')
        print(f'Available sessions: {list(available_sessions)}')
        exit()

    # Create copick roots only for valid sessions
    print('[Info]: Creating copick roots for valid sessions:', valid_sessions)
    copick_roots = {}
    for session, config in zip(sessions, configs):
        if session in valid_sessions:
            copick_roots[session] = copick.from_file(config)

    # Process Only runs from Valid Sessions 
    uniqueRuns = np.unique(particles['rlnTomoName'])   
    for uniqueRun in tqdm(uniqueRuns):
        
        # Extract the Associated Session and Run to Export too
        mysession = uniqueRun.split('_')[0]

        # Skip if this session wasn't requested by the user
        if mysession not in valid_sessions:
            continue

        myrun = '_'.join(uniqueRun.split('_')[1:])
        
        # Pull Out All Points with Associated Run
        rlnPoints = particles[particles['rlnTomoName'] == uniqueRun]
        numPoints = rlnPoints.shape[0]
        points = np.zeros([numPoints,3])
        orientations = np.zeros([numPoints, 4, 4])       
        for jj in range(numPoints):      

            # Pull Out Coordinates
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

        # Save Picks - Overwrite if exists
        picks = run.get_picks(
            object_name = particle_name, 
            user_id=export_user_id, 
            session_id = export_session_id)
        if len(picks) == 0:
            picks = run.new_picks(
                object_name = particle_name, 
                user_id=export_user_id, 
                session_id = export_session_id)
        picks.from_numpy(points, orientations)


# @export.command(context_settings={"show_default": True})
# @click.option(
#     "--particles", type=str, required=True, default="particles.star",
#     help="Particles Starfile",
# )
# @click.option(
#     "--config", type=str, required=True, default="config.json",
#     help="Copick Config File to Export Particles Too",
# )
# @click.option(
#     "--particle-name", type=str, required=True, default='ribosome',
#     help='Particle Name to Save Copick Query'
# )
# @click.option(
#     "--user-id", type=str,required=False, default="pyrelion",
#     help="UserID to Export Picks"
# )   
# @click.option(
#     "--session-id", type=str,required=False, default="1",
#     help="SessionID to Export Picks"
# )
# @click.option(
#     "--pixel-size", type=float, required=True, default=1.0,
#     help="Pixel Size of the Tilt Series [Angstroms]"
# )
# def relion4tocopick(
#     particles: str,
#     config: str,
#     particle_name: str,
#     user_id: str,
#     session_id: int,
#     pixel_size: float,
#     ):
#     """
#     Export Relion4 Particles into Corresponding Copick Project
#     """

#     # Read Particles from StarFile
#     df = starfile.read(particles)
#     try:
#         particles = df['particles']
#     except:
#         particles = df

#     # Main Loop, Go Through all Particles and Export
#     root = copick.from_file(config)
#     for uniqueRun in tqdm(np.unique(particles['rlnTomoName'])):
        
#         # Get Data Associated with Particle
#         rlnPoints = particles[particles['rlnTomoName'] == uniqueRun]
#         numPoints = rlnPoints.shape[0]
#         points = np.zeros([numPoints,3])
#         orientations = np.zeros([numPoints, 4, 4])       
#         for jj in range(numPoints):

#             # Pull Out Coordinates
#             cx = rlnPoints.iloc[jj]['rlnCoordinateX'] * pixel_size
#             cy = rlnPoints.iloc[jj]['rlnCoordinateY'] * pixel_size
#             cz = rlnPoints.iloc[jj]['rlnCoordinateZ'] * pixel_size           
#             points[jj,] = np.array([cx,cy,cz])

#             # Pull Out Orientation
#             euler = np.array([rlnPoints.iloc[jj]['rlnAngleRot'], 
#                             rlnPoints.iloc[jj]['rlnAngleTilt'], 
#                             rlnPoints.iloc[jj]['rlnAnglePsi']])
#             rot = R.from_euler('ZYZ', euler, degrees=True)
#             orientations[jj,:3,:3] = rot.inv().as_matrix()
#         orientations[:,3,3] = 1

#         # Get Run and Picks 
#         run = root.get_run(uniqueRun)
#         if run is None:
#             run = root.new_run(uniqueRun)
#         picks = run.new_picks(
#             object_name = particle_name, 
#             user_id = user_id, session_id = session_id, 
#             exist_ok=True)
#         picks.from_numpy(points, orientations)