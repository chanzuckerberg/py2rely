from py2rely import cli_context
import click

@click.command(context_settings=cli_context, name='extract')
@click.option(
    '--parameter', type=str,
    help='Path to Parameters starfile'
)
@click.option(
    '--tiltseries', type=str,
    help='Path to tiltseries starfile file'
)
@click.option(
    '--particles', type=str,
    help='Path to particles starfile'
)
@click.option(
    '--aretomopath', type=str,
    help='Path to aretomo directory with the reconstructed tomgorams'
)
def extracter(
    parameter,
    tiltseries,
    particles,
    aretomopath,
    ):

    run_extracter(parameter, tiltseries, particles, aretomopath)


def run_extracter(
    parameter,
    tiltseries,
    particles,
    aretomopath,
    ):
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.utils import relion5_tools
    import starfile, glob, os

    # Generate tomograms.starfile
    volumes = [
        f for f in glob.glob(os.path.join(aretomopath, '*.mrc'))
        if "EVN" not in os.path.basename(f) and "ODD" not in os.path.basename(f)
    ]
    sfile = starfile.read(tiltseries)
    binnings, tomo_paths = [], []
    for ii in range(sfile.shape[0]):

        name = sfile['rlnTomoName'][ii]
        matches = get_mrc_path(name, volumes)

        if len(matches) > 0:
            tomo_paths.append(matches[0])
            binnings.append(get_tomo_stats(matches[0], sfile, ii))
    sfile['rlnTomoTomogramBinning'] = binnings
    sfile['rlnTomoReconstructedTomogram'] = tomo_paths
    starfile.write({'global': sfile}, 'input/tomograms.star')

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter)
    utils.read_json_directories_file('output_directories.json')
    utils.binning = 1

    # Initialize and Run Sub-Tomo Extraction
    utils.params['resolutions']['angpix'] = sfile['rlnTomoTiltSeriesPixelSize'][0] * sfile['rlnTomoTomogramBinning'][0]
    utils.initialize_pseudo_tomos()
    box_size = utils.pseudo_subtomo_job.joboptions['box_size'].value
    utils.pseudo_subtomo_job.joboptions['crop_size'].value = box_size * 1.5
    utils.pseudo_subtomo_job.joboptions['box_size'].value = box_size * 3
    utils.pseudo_subtomo_job.joboptions['do_extract_reproject'].value = "yes"
    utils.pseudo_subtomo_job.joboptions['in_tomograms'].value = 'input/tomograms.star'
    utils.pseudo_subtomo_job.joboptions['binfactor'].value = sfile['rlnTomoTomogramBinning'][0]
    utils.run_pseudo_subtomo(rerunPseudoSubtomo=True)

def get_tomo_stats(tomo_path, sfile, index):
    import mrcfile

    with mrcfile.mmap(tomo_path, mode='r') as mrc:
        voxel_size = float(mrc.voxel_size['x'])  # Assuming isotropic
        nx = mrc.header.nx 
        ny = mrc.header.ny 
        nz = mrc.header.nz 

    binning = voxel_size / sfile['rlnTomoTiltSeriesPixelSize'][index]
    sfile.loc[index, 'rlnTomoSizeX'] = int(nx * binning)
    sfile.loc[index, 'rlnTomoSizeY'] = int(ny * binning)
    sfile.loc[index, 'rlnTomoSizeZ'] = int(nz * binning)

    return binning

def get_mrc_path(name, volumes):
    import os

    # Split name like "25jul16a_Position_1" into parts
    parts = name.split('_', 1)  # Split on first underscore
    if len(parts) == 2:
        dataset, position = parts[0], parts[1]  # position is "Position_1"
        
        # Create pattern that ensures Position_1 is followed by _ or .
        # This prevents Position_1 from matching Position_10, Position_11, etc.
        matches = [
            p for p in volumes 
            if dataset.lower() in p.lower() 
            and f'{position}_'.lower() in os.path.basename(p).lower()
        ]
    return matches

