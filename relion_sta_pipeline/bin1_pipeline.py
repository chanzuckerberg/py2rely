from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import click

def high_resolution_options(func):
    """Decorator to add shared options for high-resolution commands."""
    options = [
        click.option("--parameter-path", type=str, required=True, default='sta_parameters.json', 
                      help="The Saved Parameter Path",),
        click.option("--tomograms", type=str, required=True, default='tomograms.star', 
                      help="The Tomograms Star File to Start Refinement",),
        click.option("--particles", type=str, required=True, default='particles.star', 
                      help="The Particles Star File to Start Refinement",),
        click.option("--mask", type=str, required=True, default='mask.mrc', 
                      help="The Mask to Use for Refinement, if none provided a new mask will be created.",),
        click.option("--low-pass", type=float, required=True, default=10, 
                      help="The Low-Pass Filter to Use for Refinement",),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  

def high_resolution(
    parameter_path: str,
    tomograms: str,
    particles: str,
    mask: str,
    low_pass: float,
    ):  
    """
    Run the high-resolution refinement.
    """
    
    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # If a Path for Refined Tomograms is Provided, Assign it 
    if tomograms is not None:
        utils.set_new_tomograms_star_file(tomograms)    

    # Initialize the Processes
    utils.initialize_auto_refine()
    utils.initialize_pseudo_tomos()
    utils.initialize_reconstruct_particle()    

    # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
    utils.update_job_binning_box_size(utils.reconstruct_particle_job,
                                      utils.pseudo_subtomo_job,
                                      None,
                                      binningFactor = 1)     
    
    # Generate Pseudo Sub-Tomograms at Bin = 1
    utils.run_pseudo_subtomo() 

    # Reconstruct the Particle at Bin = 1
    utils.reconstruct_particle_job.joboptions['in_particles'].value = particles
    utils.run_reconstruct_particle()

    # Create Mask if None if Provided
    if mask is None:
        utils.initialize_mask_create()
        utils.run_mask_create(utils.tomo_refine3D_job, utils.tomo_class3D_job)

    # Run the Auto Refine
    utils.run_auto_refine()

    # Run Post Process
    utils.post_process_job.joboptions['fn_in'].value = os.path.join(reconstruction_path, 'half1.mrc')
    utils.post_process_job.joboptions['low_pass'].value = low_pass
    utils.run_post_process(rerunPostProcess=True)    

@click.command(context_settings={"show_default": True})
@high_resolution_options
def high_resolution_cli(
    parameter_path: str,
    tomograms: str,
    particles: str,
    mask: str,
    low_pass: float,
    ):    
    """
    Run the high-resolution refinement through cli.
    """

    high_resolution(parameter_path, tomograms, particles, mask, low_pass)

@click.command(context_settings={"show_default": True})
@high_resolution_options
@my_slurm.add_compute_options
def high_resolution_slurm(
    parameter_path: str,
    tomograms: str,
    particles: str,
    mask: str,
    low_pass: float,
    num_gpus: int,
    gpu_constraint: str,
    ):
    """
    Run the high-resolution refinement through slurm.
    """

    # Create Refine3D Command
    command = f"""
pyrelion high-res-pipeline \\
    --parameter-path {parameter_path} \\
    --tomograms {tomograms} \\
    --particles {particles} \\
    """

    if mask is not None:
        command += f" --mask {mask}"

    if low_pass is not None:
        command += f" --low-pass {low_pass}"

    # Create Slurm Submit Script
    my_slurm.create_shellsubmit(
        job_name="high-res-pipeline",
        output_file="bin1_pipeline.out",
        shell_name="high-res-pipeline.sh",
        command=command,
        num_gpus=num_gpus,
        gpu_constraint=gpu_constraint
    )