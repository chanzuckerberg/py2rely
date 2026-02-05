from py2rely import cli_context
import rich_click as click

@click.group()
@click.pass_context
def export(ctx):
    """
    Export Coordinates from Relion5 to New Destination
    """
    pass

@export.command(context_settings=cli_context)
@click.option(
    "-p","--parameter", type=str, required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "-cj","--class-job", type=str, required=True, default="job001",
    help="Job that Classes will Be Extracted",
)
@click.option(
    "--export-classes", type=str, required=True, default="1,2",
    help="Best 3D Classes for Sub-Sequent Refinement (Provided as Comma Separated List)"
)
@click.option(
    "--export-path", type=str, required=True,
    help="Path to Export New Classes",
)
def class2star(
    parameter: str, 
    class_job: str,     
    export_classes: str,
    export_path: str,
    ):
    """
    Export DesiredClasses from Class3D Job to New Starfile
    """

    run_class2star(
        parameter, class_job, export_classes, export_path
    )


def run_class2star(
    parameter: str, 
    class_job: str,     
    export_classes: str,
    export_path: str,
    ):
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.utils import relion5_tools

    # Split the comma-separated string into a list of integers
    keep_classes = [int(x) for x in export_classes.split(',')]

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
    utils.read_json_directories_file('output_directories.json')    

    print(f'\n[Export Class] Exporting Classes {export_classes} from Class3D/{class_job} to {export_path}\n')

    classParticles = utils.find_final_iteration(class_job)

    utils.custom_select(
        classParticles,
        export_classes,
        uniqueExport = export_path
    )

    # Create Symlink for tomograms and any other necessary data

@export.command(context_settings=cli_context)
@click.option(
    "-p","--particles", type=str, required=True, default="particles.star",
    help="Path to RELION particles star file containing particle coordinates and orientations",
)
@click.option(
    "-c","--configs", type=str, required=True, default="config1.json,config2.json",
    help="Comma-separated list of Copick config files (one per session, in order)",
)
@click.option(
    "-s","--sessions", type=str, required=True, default="24aug07a,24jul29c",
    help="Comma-separated list of session identifiers matching those in rlnTomoName field",
)
@click.option(
    '--suffix', type=str, required=False, default='_Vol',
    help='Suffix to append to run names. Use --suffix="" for no suffix.',
)
@click.option(
    "-n","--name", type=str, required=True, default='ribosome',
    help='Particle object name for Copick picks (e.g., "ribosome", "membrane")'
)
@click.option(
    "-uid","--user-id", type=str,required=False, default="relion",
    help="UserID for Exported Picks"
)
@click.option(
    "-sid","--session-id", type=str,required=False, default="99",
    help="SessionID for Exported Picks"
)
@click.option(
    "-x","--dim-x", type=int, required=False, default=4096,
    help="Tomogram dimension along x-axis in pixels (for coordinate conversion)."
)
@click.option(
    "-y","--dim-y", type=int, required=False, default=4096,
    help="Tomogram dimension along y-axis in pixels (for coordinate conversion)."
)
@click.option(
    "-z","--dim-z", type=int, required=False, default=1200,
    help="Tomogram dimension along z-axis in pixels (for coordinate conversion)."
)
def star2copick(
    particles: str, 
    configs: str,
    sessions: str,
    name: str,
    user_id: str, 
    session_id: int,
    suffix: str,
    dim_x: int,
    dim_y: int, 
    dim_z: int    
    ):
    """
    Export Particles Starfile into Corresponding Copick Projects
    """

    run_star2copick(
        particles, configs, sessions, name, 
        user_id, session_id, suffix, dim_x, dim_y, dim_z
    )

def run_star2copick(
    particles: str,
    configs: str,
    sessions: str,
    particle_name: str,
    user_id: str,
    session_id: int,
    suffix: str,
    dim_x: int,
    dim_y: int,
    dim_z: int,
    ):
    """
    Export Particles Starfile into Corresponding Copick Projects
    """
    from scipy.spatial.transform import Rotation as R
    import starfile, copick, threading, os
    from py2rely.utils import map
    import numpy as np

    # Parse User Inputs
    configs = configs.split(',')
    sessions = sessions.split(',')

    # Check that the number of user provided configs matches the number of sessions
    if len(configs) != len(sessions):
        raise ValueError(
            f"The number of config files ({len(configs)}) does not match the number of sessions ({len(sessions)})."
        )

    # Read Particles from StarFile
    df = starfile.read(particles)
    pixel_size = df['optics']['rlnTomoTiltSeriesPixelSize'].iloc[0]
    particles_df = df['particles']

    # Check Possible Export Sessions
    available_sessions = particles_df['rlnTomoName'].str.split('_').str[0].unique()
    valid_sessions = [s for s in sessions if s in available_sessions]
    missing_sessions = [s for s in sessions if s not in available_sessions]

    # One lock per session/root to keep writes safe
    session_locks = {s: threading.Lock() for s in valid_sessions}    

    if missing_sessions:
        print('[Warning]: Some specified sessions are not present in the particles star file.')
        print(f'Missing sessions: {missing_sessions}')

    if not valid_sessions:
        raise ValueError(
            f"None of the specified sessions {sessions} are present in the particles star file. "
            f"Available sessions: {list(available_sessions)}"
        )

    # Create copick roots only for valid sessions
    print('[Info]: Opening copick roots for valid sessions:', valid_sessions)
    copick_roots: dict[str, object] = {}
    for session, config in zip(sessions, configs):
        if session in valid_sessions:
            copick_roots[session] = copick.from_file(config)

    # Pre-group rows by unique run to avoid repeated boolean indexing in each worker
    # (This is usually faster and cleaner than filtering inside threads.)
    grouped = dict(tuple(particles_df.groupby('rlnTomoName', sort=False)))
    unique_runs = list(grouped.keys())

    # Constants for coordinate shift
    shift = np.array([dim_x / 2, dim_y / 2, dim_z / 2], dtype=np.float64) * float(pixel_size)

    def process_one_run(unique_run: str):
        # Extract session / run
        mysession = unique_run.split('_')[0]
        if mysession not in valid_sessions:
            return ("skipped_session", unique_run)

        myrun = '_'.join(unique_run.split('_')[1:])

        rlnPoints = grouped[unique_run]

        # ---- Vectorized coordinates ----
        cx = rlnPoints['rlnCenteredCoordinateXAngst'].to_numpy(dtype=np.float32) + shift[0]
        cy = rlnPoints['rlnCenteredCoordinateYAngst'].to_numpy(dtype=np.float32) + shift[1]
        cz = rlnPoints['rlnCenteredCoordinateZAngst'].to_numpy(dtype=np.float32) + shift[2]
        points = np.stack([cx, cy, cz], axis=1)

        # ---- Vectorized orientations ----
        # Euler angles (Rot, Tilt, Psi) -> ZYZ
        eulers = np.stack([
            rlnPoints['rlnAngleRot'].to_numpy(dtype=np.float32),
            rlnPoints['rlnAngleTilt'].to_numpy(dtype=np.float32),
            rlnPoints['rlnAnglePsi'].to_numpy(dtype=np.float32),
        ], axis=1)

        rot = R.from_euler('ZYZ', eulers, degrees=True)
        mats = rot.inv().as_matrix()  # (N, 3, 3)

        n = points.shape[0]
        orientations = np.zeros((n, 4, 4), dtype=np.float32)
        orientations[:, :3, :3] = mats
        orientations[:, 3, 3] = 1.0

        # ---- Write to CoPick (guarded) ----
        root = copick_roots[mysession]
        with session_locks[mysession]:
            run = root.get_run(myrun + suffix)
            if run is None:
                return "missing_run"

            picks = run.get_picks(
                object_name=particle_name,
                user_id=user_id,
                session_id=session_id
            )
            if len(picks) == 0:
                picks = run.new_picks(
                    object_name=particle_name,
                    user_id=user_id,
                    session_id=session_id
                )
            else:
                picks = picks[0]

            picks.from_numpy(points, orientations)

        return "ok"

    # Run workers
    max_workers = max(4, os.cpu_count() // 2)
    results = map.run_threaded(
        unique_runs,
        process_one_run,
        max_workers=max_workers,
        description="Exporting Particles (threaded)",
        get_status=lambda r: r,      # result IS the status
        on_status=map.warn_missing_run,
    )

    print("[Info]: Done. Summary:", results)    

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
#     "--user-id", type=str,required=False, default="py2rely",
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