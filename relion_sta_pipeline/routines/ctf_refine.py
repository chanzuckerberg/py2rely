from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import pipeliner.job_manager as job_manager
import json, click, starfile

@click.group()
@click.pass_context
def cli(ctx):
    pass

# CTF-Correct
@cli.command(context_settings={"show_default": True})
@click.option(
    "--parameter-path",
    type=str,
    required=True,
    default="sta_parameters.json",
    help="Sub-Tomogram Refinement Parameter Path",
)
@click.option(
    "--particles-path",
    type=str,
    required=True,
    default="Refine3D/job001/run_data.star",
    help="Input particle STAR file."
)
@click.option(
    "--mask-path",
    type=str,
    required=False,
    default=None,
    help="Input reference mask."
)
@click.option(
    "--half-map-path",
    type=str,
    required=True,
    help="Provide one of the two reference half-reconstructions."
)
@click.option(
    "--post-process-path",
    type=str,
    required=True,
    help="Input STAR file from a relion_postprocess job."
)
@click.option(
    "--defocus-search-range",
    type=str,
    required=False,
    default=750,
    help="Defocus search range (in A)."
)
@click.option(
    "--defocus-lambda",
    type=float,
    required=False,
    default=0.1,
    help="Defocus regularisation scale."
)
@click.option(
    "--do-scale-per-frame",
    type=bool,
    required=False,
    default=False,
    help="Estimate the signal-scale parameter independently for each tilt"
)
def ctf_refine(
    parameter_path: str,
    particles_path: str, 
    mask_path: str, 
    half_map_path: str, 
    post_process_path: str, 
    defocus_search_range: float,
    defocus_lambda: float,
    do_scale_per_frame: bool = False,
    tomogram_path: str = False
    ): 

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # Print Input Parameters
    utils.print_pipeline_parameters('CTF_Refine', Parameter_Path=parameter_path,Particles_Path=particles_path,
                                    Mask_path=mask_path, Half_map_path=half_map_path, post_process_path=post_process_path,
                                    defocus_search_range=defocus_search_range, defocus_lambda=defocus_lambda, 
                                    do_scale_per_frame=do_scale_per_frame)    

    # Update the Resolution with Given Binning Factor
    particlesdata = starfile.read(particles_path)
    currentBinning = int(particlesdata['optics']['rlnTomoSubtomogramBinning'].values[0])
    binIndex = utils.binningList.index(currentBinning) 

    # Initialize Box Size Option
    utils.initialize_ctf_refine()

    # Provide Input Paths
    utils.ctf_refine_job.joboptions['in_particles'].value = particles_path
    utils.ctf_refine_job.joboptions['fn_mask'].value = mask_path
    utils.ctf_refine_job.joboptions['fn_half_map'].value = half_map_path
    utils.ctf_refine_job.joboptions['fn_postprocess'].value = post_process_path

    # Update the Box Size Based On Reference
    utils.ctf_refine_job.joboptions['boxsize'].value = mrcfile.read(mask_path).shape[0]

    # Provide Additional Processing Parameters
    utils.ctf_refine_job.joboptions['defocus_search_range'].value = defocus_search_range
    utils.ctf_refine_job.joboptions['lambda'].value = defocus_lambda
    utils.ctf_refine_job.joboptions['do_scale_per_frame'].value = do_scale_per_frame    
    utils.ctf_refine_job.joboptions['mpi_command'].value = 'mpirun'

    utils.run_ctf_refine(rerunCtfRefine = True)