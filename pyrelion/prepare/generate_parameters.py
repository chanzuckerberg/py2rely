import pyrelion.routines.submit_slurm as my_slurm
import pyrelion.prepare.parameters as parameters
from pyrelion.utils import sta_tools
from typing import List
import json, click, os

@click.group()
@click.pass_context
def cli(ctx):
    pass

# Create the boilerplate JSON file with a default file path
@cli.command(context_settings={"show_default": True})
@click.option("--output",type=str,required=False,default='sta_parameters.json',
              help="The Saved Parameter Path",)
@click.option("--input-tilt-series",type=str,required=False,default="input/tiltSeries/aligned_tilt_series.star",
              help="Path to Starfile with Tilt Series Alignments")
@click.option("--input-particles",type=str,required=False,default="input/full_picks.star",
              help="Path to Starfile with Particle Coordinates")
@click.option("--tilt-series-pixel-size",type=float,required=False,default=1.54,
              help="Pixel Size for the Tilt Series (in Angstroms)")
@click.option("--symmetry",type=str,required=False,default="C1",
              help="Protein Symmetry")
@click.option("--low-pass", type=float, required=False,default=50,
              help="Low-Pass Filter for the Reference Template (in Angstroms)")
@click.option("--protein-diameter",type=float,required=False,default=290,
              help="Protein Diameter")
@click.option("--denovo-generation",type=bool,required=False,default=False,
              help="Create Template Parameters for Denovo Model Generation")
@click.option("--box-scaling",type=float,required=False,default=2.0,
              help="Default Padding for Sub-Tomogram Averaging")
@click.option("--binning-list", type=str, required=False, default="4,2,1",
              callback=my_slurm.parse_int_list,
              help="List of Binning Factors to Process the Refinement Steps (provided as a comma-separated list)")
def relion5_parameters(
    output: str,
    input_tilt_series: str,
    input_particles: str, 
    tilt_series_pixel_size: float,
    symmetry: str,
    low_pass: float,
    protein_diameter: float,
    denovo_generation: bool,
    box_scaling: float,
    binning_list: List[int]
    ):
    """
    Generate a JSON file with the default parameters for the pyrelion.
    """

    default_config = parameters.ProcessingConfigRelion5(
        resolutions=parameters.ResolutionParameters(
            angpix=tilt_series_pixel_size,
            box_scaling=box_scaling,
            binning_list=str(binning_list)
        ),
        initial_model=parameters.InitialModel(
            in_tomograms=input_tilt_series,            
            use_direct_entries="yes",
            nr_iter=70,
            nr_classes=1,
            tau_fudge=4,
            particle_diameter=protein_diameter,
            sym_name=symmetry,
            do_run_C1="yes",
            nr_pool=16,
            use_gpu="yes",
            gpu_ids="",
            nr_threads=8
        ) if denovo_generation else None,
        reconstruct=parameters.Reconstruct(
            in_tomograms=input_tilt_series,
            in_particles= input_particles,
            do_use_direct_entries="yes",
            do_from2d="yes",
            crop_size=-1,
            point_group=symmetry,
            nr_threads=16,
            mpi_command="mpirun"
        ),
        pseudo_subtomo=parameters.PseudoSubtomo(
            in_tomograms=input_tilt_series,
            in_particles=input_particles,  
            do_use_direct_entries="yes",
            crop_size=-1,
            do_float16="yes",
            do_output_2dstacks="yes",            
            nr_threads=16,
            mpi_command="mpirun"
        ),
        refine3D=parameters.Refine3D(
            in_tomograms=input_tilt_series,   
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
            nr_threads= 16,
            mpi_command="mpirun",
            other_args="" # --maxsig 3000
        ),
        class3D=parameters.Class3D(
            in_tomograms=input_tilt_series,   
            use_direct_entries="yes",
            ref_correct_greyscale="yes",
            ini_high=int(low_pass/2),
            sym_name=symmetry,
            do_ctf_correction= "yes",
            ctf_intact_first_peak= "no",
            nr_classes= 5,
            tau_fudge= 3,
            nr_iter= 25,
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
            nr_threads= 16,
            mpi_command="mpirun",
            sigma_tilt= 0
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
            in_tomograms=input_tilt_series,
            use_direct_entries="yes",
            do_defocus="yes",
            focus_range=3000,
            do_reg_def="yes",
            lambda_param=0.1,
            do_scale="yes",
            do_frame_scale="yes",
            nr_threads=16
        ) if 1 in binning_list else None,
        bayesian_polish=parameters.BayesianPolish(
            in_tomograms=input_tilt_series,
            use_direct_entries="yes",
            max_error=5,
            do_motion="yes",
            sigma_vel=0.2,
            sigma_div=5000,
            nr_threads=16
        ) if 1 in binning_list else None
    )

    # Save the parameters to a JSON file
    with open(output, "w") as f:
        json.dump(default_config.model_dump(by_alias=True), f, indent=4)
        # json.dump(default_config.dict(), f, indent=4)
    print(f'\nWrote Pipeline Parameters JSON File To: {output}\n')         

    # Print the Box Sizes after the parameters are saved
    utils = sta_tools.PipelineHelper(None, requireRelion=False)
    utils.read_json_params_file(output)


@cli.command(context_settings={"show_default": True})
@click.option("--parameter",type=str,required=True,default='sta_parameters.json',
              help="The Saved Parameter Path")
@click.option("--reference-template",type=str,required=False,default=None,
              help="Provided Template for Preliminary Refinment (Optional)")
@click.option("--run-denovo-generation",type=bool,required=False, default=False,
              help="Generate Initial Reconstruction with Denovo")
@click.option("--run-class3D",type=bool,required=False,default=False, 
              help="Run 3D-Classification Job After Refinement")
@click.option("--new-pipeline", type=bool, required=False, default=True,
              help="Create a new pipeline trajectory")
@my_slurm.add_compute_options
def relion5_pipeline(
    parameter: str,
    reference_template: str,
    run_denovo_generation: bool,
    run_class3d: bool,
    num_gpus: int, 
    gpu_constraint: str, 
    new_pipeline: bool
    ):
    """
    Prepare pyRelion pipeline for submission.
    """

    # Delete Existing Output Directories for a fresh new pipeline run
    if new_pipeline and os.path.exists('output_directories.json'):
        print('\nDeleting Existing Output Directories for a fresh new pipeline run')
        os.remove('output_directories.json')
    if new_pipeline and os.path.exists('output_directories_history.json'):
        print('Deleting Existing Output Directories-History for a fresh new pipeline run')
        os.remove('output_directories_history.json')

    command = f"""
pyrelion pipelines sta \\
    --parameter {parameter} \\
    --run-denovo-generation {run_denovo_generation} --run-class3D {run_class3d} \\
    """
    # Only add reference template if it is provided
    if reference_template is not None:
        command += f"--reference-template {reference_template}"
    
    my_slurm.create_shellsubmit(
        job_name='relion5',
        output_file="relion5_pipeline.out",
        shell_name="pipeline.sh",
        command=command,
        num_gpus=num_gpus,
        gpu_constraint=gpu_constraint,
        total_time='72:00:00'
    )

if __name__ == "__main__":
    cli()