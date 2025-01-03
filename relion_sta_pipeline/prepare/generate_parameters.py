import relion_sta_pipeline.prepare.parameters as parameters
import json, click

@click.group()
@click.pass_context
def cli(ctx):
    pass

# Create the boilerplate JSON file with a default file path
@cli.command(context_settings={"show_default": True})
@click.option("--write-path",type=str,required=False,default='sta_parameters.json',
              help="The Saved Parameter Path",)
@click.option("--input-tilt-series",type=str,required=False,default="input/tiltSeries/aligned_tilt_series.star",
              help="Path to Starfile with Tilt Series Alignments")
@click.option("--input-particles",type=str,required=False,default="input/full_picks.star",
              help="Path to Starfile with Particle Coordinates")
@click.option("--tilt-series-pixel-size",type=float,required=False,default=1.54,
              help="Pixel Size for the Tilt Series (in Angstroms)")
@click.option("--symmetry",type=str,required=False,default="C1",
              help="Protein Symmetry")
@click.option("--protein-diameter",type=float,required=False,default=290,
              help="Protein Diameter")
@click.option("--denovo-generation/--no-denovo-generation",type=bool,required=False,default=False,
              help="Create Template Parameters for Denovo Model Generation")
@click.option("--box-scaling",type=float,required=False,default=2.0,
              help="Default Padding for Sub-Tomogram Averaging")
@click.option("--binning-list",type=str,required=False,default="[4,2,1]",
              help="List of Binning Factors to Process the Refinement Steps")
def relion5_parameters(
    write_path: str,
    input_tilt_series: str,
    input_particles: str, 
    tilt_series_pixel_size: float,
    symmetry: str,
    protein_diameter: float,
    denovo_generation: bool,
    box_scaling: float,
    binning_list: str
    ):
    """
    Generate a JSON file with the default parameters for the relion_sta_pipeline.
    """
    default_config = parameters.ProcessingConfigRelion5(
        resolutions=parameters.ResolutionParameters(
            angpix=tilt_series_pixel_size,
            box_scaling=box_scaling,
            binning_list=binning_list
        ),
        initial_model=parameters.InitialModel(
            in_tomograms=input_tilt_series,            
            nr_iter=70,
            nr_classes=1,
            tau_fudge=4,
            particle_diameter=protein_diameter,
            point_group=symmetry,
            do_run_C1="yes",
            nr_pool=16,
            use_gpu="yes",
            gpu_ids="",
            nr_threads=8
        ) if denovo_generation else None,
        reconstruct=parameters.Reconstruct(
            in_tomograms=input_tilt_series,            
            in_particles= input_particles,
            do_from2d="yes",
            crop_size=-1,
            point_group=symmetry,
            nr_threads=16,
            mpi_command="mpirun"
        ),
        pseudo_subtomo=parameters.PseudoSubtomo(
            in_tomograms=input_tilt_series,
            in_particles=input_particles,            
            crop_size=-1,
            do_float16="yes",
            do_output_2dstacks="yes",            
            nr_threads=16,
            mpi_command="mpirun"
        ),
        refine3D=parameters.Refine3D(
            tomograms_star=input_tilt_series,            
            ref_correct_greyscale="yes",
            ini_high=50,
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
            nr_threads= 8,
            mpi_command="mpirun",
            other_args="--maxsig 3000"
        ),
        class3D=parameters.Class3D(
            tomograms_star=input_tilt_series,            
            ref_correct_greyscale="yes",
            ini_high=30,
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
            nr_pool= 16, 
            use_gpu= "no",
            gpu_ids= "",
            nr_threads= 8,
            mpi_command="mpirun",
            prior_tiltang_width= 0
        ),
        select=parameters.SelectParticles(
            do_select_values="yes",
            select_label="rlnClassNumber"
        ),
        mask_create=parameters.MaskCreate(
            lowpass_filter=20,
            extend_inimask=3,
            width_mask_edge=5
        )
    )

    with open(write_path, "w") as f:
        json.dump(default_config.dict(), f, indent=4)

    print(f'\nWrote Pipeline Parameters JSON File To: {write_path}\n')

def validate_num_gpus(ctx, param, value):
    if value is not None and (value < 1 or value > 4):
        raise click.BadParameter("Number of GPUs must be between 1 and 4.")
    return value            

@cli.command(context_settings={"show_default": True})
@click.option("--parameter-path",type=str,required=True,default='sta_parameters.json',
              help="The Saved Parameter Path")
@click.option("--reference-template",type=str,required=False,default=None,
              help="Provided Template for Preliminary Refinment (Optional)")
@click.option("--run-denovo-generation",type=bool,required=False, default=False,
              help="Generate Initial Reconstruction with Denovo")
@click.option("--run-class3D",type=bool,required=False,default=False, 
              help="Run 3D-Classification Job After Refinement")
@click.option("--num-gpus",type=int,required=False,default=1,
              help="Number of GPUs to Use")
@click.option("--gpu-constraint",type=str,required=False,default=None,
              help="GPU Constraint")
def relion5_pipeline(
    parameter_path: str,
    reference_template: str,
    run_denovo_generation: bool,
    run_class3D: bool,
    num_gpus: int, 
    gpu_constraint: str):
    """
    Prepare pyRelion pipeline for submission.
    """
    
    command = f"""
run-relion5 \\
    --parameter-path {parameter_path} \\
    --reference-template {reference_template} \\
    --run-denovo-generation {run_denovo_generation} \\
    --run-class3D {run_class3D}
    """
    
    create_shellsubmit(
        job_name='relion5',
        output_file="pipeline.out",
        shell_name="pipeline.sh",
        command=command,
        num_gpus=num_gpus,
        gpu_constraint=gpu_constraint
    )

if __name__ == "__main__":
    cli()