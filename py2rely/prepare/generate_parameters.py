from py2rely.routines.submit_slurm import validate_even_gpus
import py2rely.routines.submit_slurm as my_slurm
from py2rely.utils import common
from py2rely import cli_context
import rich_click as click
from typing import List

@click.group()
@click.pass_context
def cli(ctx):
    pass

# Create the boilerplate JSON file with a default file path
@cli.command(context_settings=cli_context, no_args_is_help=True)
@click.option("-o","--output",type=str,required=False,default='sta_parameters.json',
              help="The Saved Parameter Path",)
@click.option("-ts","--tilt-series",type=str,required=False,default="input/tiltSeries/aligned_tilt_series.star",
              help="Path to Starfile with Tilt Series Alignments")
@click.option("-p","--particles",type=str,required=False,default="input/full_picks.star",
              help="Path to Starfile with Particle Coordinates")
@click.option("-ps","--tilt-series-pixel-size",type=float,required=False,default=1.54,
              help="Pixel Size for the Tilt Series (in Angstroms)")
@click.option("-s","--symmetry",type=str,required=False,default="C1",
              help="Protein Symmetry")
@click.option("-lp","--low-pass", type=float, required=False,default=50,
              help="Low-Pass Filter for the Reference Template (in Angstroms)")
@click.option("-pd","--protein-diameter",type=float,required=False,default=290,
              help="Protein Diameter")
@click.option("-dg","--denovo-generation",type=bool,required=False,default=False,
              help="Create Template Parameters for Denovo Model Generation")
@click.option("-bs","--box-scaling",type=float,required=False,default=2.0,
              help="Default Padding for Sub-Tomogram Averaging")
@click.option("--nclasses", '-nc', type=int, required=False, default=1,
              help="Number of Classes for 3D Auto Classification")
@click.option('--ninit-models', '-nim', type=int, required=False, default=1,
              help="Number of Classes for Initial Model (Denovo) Generation")
@click.option("-bl","--binning-list", type=str, required=False, default="4,2,1",
              callback=my_slurm.parse_int_list,
              help="List of Binning Factors to Process the Refinement Steps (provided as a comma-separated list)")
@click.option('--nthreads', '-nj', type=int, required=False, default=8,
              help="Number of Threads for the Pipeline.")
@click.option("--nprocesses", "-np", type=int, required=False, default=None,
              help="Number of Processes for the Pipeline. This is required if the job is not submitted through SLURM cluster.")
def relion5_parameters(
    output: str,
    tilt_series: str,
    particles: str, 
    tilt_series_pixel_size: float,
    symmetry: str,
    low_pass: float,
    protein_diameter: float,
    denovo_generation: bool,
    box_scaling: float,
    binning_list: List[int],
    nclasses: int,
    ninit_models: int,
    nthreads: int,
    nprocesses: int
    ):
    """
    Generate a JSON file with the default parameters for the py2rely.
    """

    create_relion5_parameters(
        output, tilt_series, particles, 
        tilt_series_pixel_size, symmetry, low_pass, 
        protein_diameter, denovo_generation, box_scaling, 
        binning_list, nclasses, ninit_models, nthreads, nprocesses
    )

def create_relion5_parameters(
    output: str,
    tilt_series: str,
    particles: str, 
    tilt_series_pixel_size: float,
    symmetry: str,
    low_pass: float,
    protein_diameter: float,
    denovo_generation: bool,
    box_scaling: float,
    binning_list: List[int],
    nclasses: int,
    ninit_models: int,
    nthreads: int,
    nprocesses: int
    ):
    import py2rely.prepare.parameters as parameters
    from py2rely.utils import sta_tools
    from rich.console import Console
    from rich.table import Table
    import json, os

    console = Console()
    console.rule("[bold cyan]Generate Relion5 Pipeline Parameters")

    if not os.path.exists(particles):
        raise FileNotFoundError(f"Input particles file not found: {particles}")

    if not os.path.exists(tilt_series):
        raise FileNotFoundError(f"Input tiltseries file not found: {tilt_series}")

    # --- parameter summary table ---
    table = Table(title="[bold blue]Configuration Summary", header_style="bold magenta")
    table.add_column("Parameter", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Tilt Series File", tilt_series)
    table.add_row("Particles File", particles)
    table.add_row("Pixel Size (Å)", str(tilt_series_pixel_size))
    table.add_row("Symmetry", symmetry)
    table.add_row("Low-Pass Filter (Å)", str(low_pass))
    table.add_row("Protein Diameter (Å)", str(protein_diameter))
    table.add_row("Box Scaling", str(box_scaling))
    table.add_row("Binning List", str(binning_list))
    table.add_row("Number of Classes", str(nclasses))
    table.add_row("Denovo Generation", str(denovo_generation))
    table.add_row("Nthreads", str(nthreads))
    table.add_row("Nprocesses", str(nprocesses))
    console.print(table)

    my_mpi_command = f"mpirun -n {nprocesses}" if nprocesses else "mpirun"

    # TODO: validate:
    # - each job that can use mpi has parameters set to use mpi
    # - the mpi parameters set are actual being applied to the job
    # - pass in the ntasks value and cpus-per-task value into here and use that instead of hard coded numbers(or ensure they align somehow)
    default_config = parameters.ProcessingConfigRelion5(
        resolutions=parameters.ResolutionParameters(
            angpix=tilt_series_pixel_size,
            box_scaling=box_scaling,
            binning_list=str(binning_list)
        ),
        initial_model=parameters.InitialModel(
            in_tomograms=tilt_series,            
            use_direct_entries="yes",
            nr_iter=70,
            nr_classes=ninit_models,
            tau_fudge=4,
            particle_diameter=protein_diameter,
            sym_name=symmetry,
            do_run_C1="yes",
            nr_pool=16,
            use_gpu="yes",
            gpu_ids="",
            nr_threads=nthreads
        ) if denovo_generation else None,
        reconstruct=parameters.Reconstruct(
            in_tomograms=tilt_series,
            in_particles= particles,
            do_use_direct_entries="yes",
            do_from2d="yes",
            crop_size=-1,
            point_group=symmetry,
            nr_threads=nthreads,
            mpi_command=my_mpi_command
        ),
        pseudo_subtomo=parameters.PseudoSubtomo(
            in_tomograms=tilt_series,
            in_particles=particles,
            do_use_direct_entries="yes",
            crop_size=-1,
            do_float16="yes",
            do_output_2dstacks="yes",
            nr_threads=nthreads,
            nr_mpi=3,
        ),
        refine3D=parameters.Refine3D(
            in_tomograms=tilt_series,   
            use_direct_entries="yes",
            ref_correct_greyscale="yes",
            ini_high=low_pass,
            sym_name=symmetry,
            do_ctf_correction= "yes",
            ctf_intact_first_peak= "no",
            particle_diameter= protein_diameter,
            do_zero_mask= "yes",   
            do_solvent_fsc="no",
            sampling="7.5 degrees",
            offset_range= 5,
            offset_step= 1,
            auto_local_sampling="1.8 degrees",
            relax_sym= "",
            auto_faster="no",
            nr_pool= 30,   
            use_gpu= "yes",
            gpu_ids= "",
            nr_threads=nthreads,
            mpi_command=my_mpi_command,
            other_args="" # --maxsig 3000
        ),
        class3D=parameters.Class3D(
            in_tomograms=tilt_series,   
            use_direct_entries="yes",
            ref_correct_greyscale="yes",
            ini_high=int(low_pass/2),
            sym_name=symmetry,
            do_ctf_correction= "yes",
            ctf_intact_first_peak= "no",
            nr_classes= nclasses,
            tau_fudge= 3,
            nr_iter= 15,
            do_fast_subsets="no",
            particle_diameter= protein_diameter,
            do_zero_mask= "yes",   
            highres_limit= -1,
            dont_skip_align= "no",
            sampling="7.5 degrees",
            offset_range= 5,
            offset_step= 1,
            do_local_ang_searches="yes",
            allow_coarser= "no",
            nr_pool= 30, 
            use_gpu= "no",
            gpu_ids= "",
            nr_threads=nthreads,
            mpi_command=my_mpi_command,
            sigma_tilt= 0,
            other_args=""
        ),
        select=parameters.SelectParticles(
            do_select_values="yes",
            select_label="rlnClassNumber"
        ),
        mask_create=parameters.MaskCreate(
            lowpass_filter=20,
            extend_inimask=3,
            width_mask_edge=5
        ),
        ctf_refine=parameters.CtfRefine(
            in_tomograms=tilt_series,
            use_direct_entries="yes",
            do_defocus="yes",
            focus_range=3000,
            do_reg_def="yes",
            lambda_param=0.1,
            do_scale="yes",
            do_frame_scale="yes",
            nr_threads=nthreads
        ) if 1 in binning_list else None,
        bayesian_polish=parameters.BayesianPolish(
            in_tomograms=tilt_series,
            use_direct_entries="yes",
            max_error=5,
            do_motion="yes",
            sigma_vel=0.2,
            sigma_div=5000,
            nr_threads=nthreads
        ) if 1 in binning_list else None
    )

    # Save the parameters to a JSON file
    with open(output, "w") as f:
        json.dump(default_config.model_dump(by_alias=True), f, indent=4)
        # json.dump(default_config.dict(), f, indent=4)
    console.print(f"[green]Parameters JSON saved to[/green] [b]{output}[/b]")    

    # Print the Box Sizes after the parameters are saved
    utils = sta_tools.PipelineHelper(None, requireRelion=False)
    utils.read_json_params_file(output)


@cli.command(context_settings=cli_context, no_args_is_help=True)
@common.add_sta_options
@click.option('-ndays', '--num-days', type=int, required=False, default=3,
              help='Number of days to request for the SLURM job')
@click.option("--new-pipeline", type=bool, required=False, default=True,
              help="Create a new pipeline trajectory")
@common.add_submitit_options
def relion5_pipeline(
    parameter: str,
    reference_template: str,
    run_denovo_generation: bool,
    run_class3d: bool,
    num_gpus: int, 
    num_days: int,
    new_pipeline: bool,
    extract3d: bool,
    manual_masking: bool,
    submitit: bool,
    cpu_constraint: str,
    gpu_constraint: str,
    timeout: int
    ):
    """
    Prepare py2rely pipeline for submission.
    """    

    run_relion5_pipeline(
        parameter, reference_template, run_denovo_generation, 
        run_class3d, num_gpus, num_days, gpu_constraint, new_pipeline,
        extract3d, manual_masking, submitit, cpu_constraint, timeout
    )

def run_relion5_pipeline(
    parameter: str,
    reference_template: str,
    run_denovo_generation: bool,
    run_class3d: bool,
    num_gpus: int, 
    num_days: int,
    gpu_constraint: str, 
    new_pipeline: bool,
    extract3d: bool,
    manual_masking: bool,
    submitit: bool,
    cpu_constraint: str,
    timeout: int
    ):
    from rich.console import Console
    import os

    console = Console()
    console.rule("[bold cyan]Generate Relion5 Slurm Submission")

    # Delete Existing Output Directories for a fresh new pipeline run
    if new_pipeline and os.path.exists('output_directories.json'):
        print('\nDeleting Existing Output Directories for a fresh new pipeline run')
        os.remove('output_directories.json')
    if new_pipeline and os.path.exists('output_directories_history.json'):
        print('Deleting Existing Output Directories-History for a fresh new pipeline run')
        os.remove('output_directories_history.json')

    # Check the provided parameter file to 

    command = f"""
py2rely pipelines sta \\
    --parameter {parameter} \\
    --run-denovo-generation {run_denovo_generation} --run-class3D {run_class3d} \\
    --extract3D {extract3d} --manual-masking {manual_masking} \\
    """
    # Only add reference template if it is provided
    if reference_template is not None:
        command += f"--reference-template {reference_template}"

    if submitit:
        command += f" --submitit True --cpu-constraint {cpu_constraint} --timeout {timeout} --ngpus {num_gpus}"
        num_gpus = 0  # submitit will handle gpu requests
    
    my_slurm.create_shellsubmit(
        job_name='relion5',
        output_file="relion5_pipeline.out",
        shell_name="pipeline.sh",
        command=command,
        num_gpus=num_gpus,
        gpu_constraint=gpu_constraint,
        total_time=f'{num_days}-00:00:00' # request ndays
    )

    console.rule("[bold green]Submission Ready")
    console.print(f"[green]SLURM shell script written as[/green] [b]pipeline.sh[/b]\n")


# def validate_parameters(parameters: str, ngpus: int):

    # load the parameters and check if nprocesses are requested, if so, 

if __name__ == "__main__":
    cli()
