from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import json, click

@click.group()
@click.pass_context
def cli(ctx):
    pass

class ResolutionParameters(BaseModel):
    angpix: float
    box_scaling: float 
    binning_list: str

class ReconstructTomograms(BaseModel):
    tilt_series: str
    width: float
    height: float
    thickness: float
    binned_pixel_size: float
    do_fourierinversion_filter: str 
    do_need_denoising: str
    do_write_centralslices: str 
    nr_threads: int

class ImportTomograms(BaseModel):
    in_tomograms: str
    angpix: float
    kV: int
    Cs: float
    Q0: float
    do_flip_yz: str
    do_flip_z: str

class ImportCoordinates(BaseModel):
    particle_star: str
    tomogram_star: str
    do_flip_z: str

class InitialModel(BaseModel):
    nr_iter: int
    nr_classes: int
    tau_fudge: float
    particle_diameter: float
    point_group: str
    do_run_C1: str
    nr_pool: int
    use_gpu: str
    gpu_ids: str
    nr_threads: int

class Reconstruct(BaseModel):
    in_particles: Optional[str] = None
    crop_size: int
    point_group: str
    nr_threads: int
    mpi_command: str
    
class PseudoSubtomo(BaseModel):
    in_particles: str
    crop_size: int
    do_float16: str
    do_output_2dstacks: Optional[str] = None
    nr_threads: int
    mpi_command: str

class Refine3D(BaseModel):
    ref_correct_greyscale: str
    ini_high: int
    sym_name: str
    do_ctf_correction: str
    ctf_intact_first_peak: str
    particle_diameter: int
    do_zero_mask: str
    do_solvent_fsc: str
    sampling: str
    offset_range: int 
    offset_step: int 
    auto_local_sampling: str
    relax_sym: str
    auto_faster: str
    nr_pool: int
    use_gpu: str
    gpu_ids: str
    nr_threads: int
    mpi_command: str

class Class3D(BaseModel):
    ref_correct_greyscale: str
    ini_high: int
    sym_name: str
    do_ctf_correction: str
    ctf_intact_first_peak: str
    nr_classes: int
    tau_fudge: int 
    nr_iter: int
    do_fast_subsets: str
    particle_diameter: int
    do_zero_mask: str
    highres_limit: int 
    dont_skip_align: str
    offset_range: int 
    offset_step: int 
    do_local_ang_searches: str
    allow_coarser: str
    nr_pool: int
    use_gpu: str
    gpu_ids: str
    nr_threads: int
    mpi_command: str
    
class SelectParticles(BaseModel):
    do_select_values: str
    select_label: str

class MaskCreate(BaseModel):
    lowpass_filter: int
    extend_inimask: int
    width_mask_edge: int
    
class ProcessingConfigRelion4(BaseModel):
    resolutions: ResolutionParameters
    import_tomograms: ImportTomograms
    import_coords: ImportCoordinates
    initial_model: Optional[InitialModel]
    reconstruct: Reconstruct
    pseudo_subtomo: PseudoSubtomo
    refine3D: Refine3D
    class3D: Class3D
    select: SelectParticles
    mask_create: MaskCreate

class ProcessingConfigRelion5(BaseModel):
    resolutions: ResolutionParameters
    reconstruct_tomograms: ReconstructTomograms
    reconstruct: Reconstruct
    initial_model: Optional[InitialModel]
    pseudo_subtomo: PseudoSubtomo
    refine3D: Refine3D
    class3D: Class3D
    select: SelectParticles
    mask_create: MaskCreate

# Create the boilerplate JSON file with a default file path
@cli.command(context_settings={"show_default": True})
@click.option(
    "--file-path",
    type=str,
    required=False,
    default='sta_parameters.json',
    help="The Saved Parameter Path",
)
@click.option(
    "--tilt-series-pixel-size",
    type=float,
    required=False,
    default=1.54,
    help="Pixel Size for the Tilt Series (in Angstroms)",
)
@click.option(
    "--symmetry",
    type=str,
    required=False,
    default="C1",
    help="Protein Symmetry",
)
@click.option(
    "--protein-diameter",
    type=float,
    required=False,
    default=290,
    help="Protein Diameter",
)
@click.option(
    "--denovo-generation/--no-denovo-generation",
    type=bool,
    required=False,
    default=False,
    help="Create Template Parameters for Denovo Model Generation"
)
@click.option(
    "--box-scaling",
    type=float,
    required=False,
    default=2.0,
    help="Default Padding for Sub-Tomogram Averaging"
)
@click.option(
    "--binning-list",
    type=str,
    required=False,
    default="[4,2,1]",
    help="List of Binning Factors to Process the Refinement Steps"
)
def relion4_parameters(
    file_path: str,
    tilt_series_pixel_size: float,
    symmetry: str,
    protein_diameter: float,
    denovo_generation: bool,
    box_scaling: float,
    binning_list: str
    ):
    default_config = ProcessingConfigRelion4(
        resolutions=ResolutionParameters(
            box_scaling=box_scaling,
            binning_list = binning_list
        ),
        import_tomograms=ImportTomograms(
            in_tomograms="input/tomogram_description.star",
            angpix=tilt_series_pixel_size,
            kV=300,
            Q0=0.07,
            Cs=2.7,
            do_flip_yz="yes",
            do_flip_z="yes"
        ),
        import_coords=ImportCoordinates(
            particle_star="input/particles.star",
            tomogram_star="None",
            do_flip_z="no"
        ),
        initial_model=InitialModel(
            nr_iter=70,
            nr_classes=3,
            tau_fudge=2.0,
            particle_diameter=protein_diameter,
            point_group=symmetry,
            do_run_C1="yes",
            nr_pool=16,
            use_gpu="yes",
            gpu_ids="",
            nr_threads=8
        ) if denovo_generation else None,
        reconstruct=Reconstruct(
            crop_size=-1,
            point_group=symmetry,
            nr_threads=16,
            mpi_command="srun"
        ),
        pseudo_subtomo=PseudoSubtomo(
            crop_size=-1,
            do_float16="yes",
            nr_threads=16,
            mpi_command="srun"
        ),
        refine3D=Refine3D(
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
            mpi_command="srun"
        ),
        class3D=Class3D(
            ref_correct_greyscale="yes",
            ini_high=30,
            sym_name=symmetry,
            do_ctf_correction= "yes",
            ctf_intact_first_peak= "no",
            nr_classes= 10,
            tau_fudge= 2,
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
            use_gpu= "yes",
            gpu_ids= "",
            nr_threads= 8,
            mpi_command="srun"
        ),
        select=SelectParticles(
            do_select_values="yes",
            select_label="rlnClassNumber"
        ),
        mask_create=MaskCreate(
            lowpass_filter=20,
            extend_inimask=3,
            width_mask_edge=5
        )
    )

    with open(file_path, "w") as f:
        json.dump(default_config.dict(), f, indent=4)

# Create the boilerplate JSON file with a default file path
@cli.command(context_settings={"show_default": True})
@click.option(
    "--write-path",
    type=str,
    required=False,
    default='sta_parameters.json',
    help="The Saved Parameter Path",
)
@click.option(
    "--input-tilt-series",
    type=str,
    required=False,
    default="input/tiltSeries/aligned_tilt_series.star",
    help="Path to Starfile with Tilt Series Alignments"
)
@click.option(
    "--input-particles",
    type=str,
    required=False,
    default="input/full_picks.star",
    help="Path to Starfile with Particle Coordinates"
)
@click.option(
    "--tilt-series-pixel-size",
    type=float,
    required=False,
    default=1.54,
    help="Pixel Size for the Tilt Series (in Angstroms)",
)
@click.option(
    "--tomo-width",
    type=float,
    required=False,
    default=4096,
    help="Unbinned Tomogram Width (voxels)"
)
@click.option(
    "--tomo-height",
    type=float,
    required=False,
    default=4096,
    help="Unbinned Tomogram Height (voxels)"    
)
@click.option(
    "--tomo-thickness",
    type=float,
    required=False,
    default=1200,
    help="Unbinned Tomogram Thickness (voxels)"    
)
@click.option(
    "--tomo-voxel-size",
    type=float,
    required=False,
    default=10,
    help="Binned Tomogram Voxel Size"    
)
@click.option(
    "--symmetry",
    type=str,
    required=False,
    default="C1",
    help="Protein Symmetry",
)
@click.option(
    "--protein-diameter",
    type=float,
    required=False,
    default=290,
    help="Protein Diameter",
)
@click.option(
    "--denovo-generation/--no-denovo-generation",
    type=bool,
    required=False,
    default=False,
    help="Create Template Parameters for Denovo Model Generation"
)
@click.option(
    "--box-scaling",
    type=float,
    required=False,
    default=2.0,
    help="Default Padding for Sub-Tomogram Averaging"
)
@click.option(
    "--binning-list",
    type=str,
    required=False,
    default="[4,2,1]",
    help="List of Binning Factors to Process the Refinement Steps"
)
def relion5_parameters(
    write_path: str,
    input_tilt_series: str,
    input_particles: str, 
    tilt_series_pixel_size: float,
    tomo_width: float,
    tomo_height: float,
    tomo_thickness: float,
    tomo_voxel_size: float,
    symmetry: str,
    protein_diameter: float,
    denovo_generation: bool,
    box_scaling: float,
    binning_list: str
    ):
    default_config = ProcessingConfigRelion5(
        resolutions=ResolutionParameters(
            angpix=tilt_series_pixel_size,
            box_scaling=box_scaling,
            binning_list = binning_list
        ),
        reconstruct_tomograms=ReconstructTomograms(
            tilt_series=input_tilt_series,
            width=tomo_width,
            height=tomo_height,
            thickness=tomo_thickness,
            binned_pixel_size=tomo_voxel_size,
            do_fourierinversion_filter="no",
            do_need_denoising="no",
            do_write_centralslices="no",            
            nr_threads=16
        ),
        initial_model=InitialModel(
            nr_iter=70,
            nr_classes=3,
            tau_fudge=10.0,
            particle_diameter=protein_diameter,
            point_group=symmetry,
            do_run_C1="yes",
            nr_pool=16,
            use_gpu="yes",
            gpu_ids="",
            nr_threads=8
        ) if denovo_generation else None,
        reconstruct=Reconstruct(
            in_particles= input_particles,
            do_from2d="yes",
            crop_size=-1,
            point_group=symmetry,
            nr_threads=16,
            mpi_command="mpirun"
        ),
        pseudo_subtomo=PseudoSubtomo(
            in_particles= input_particles,            
            crop_size=-1,
            do_float16="yes",
            do_output_2dstacks="yes",            
            nr_threads=16,
            mpi_command="mpirun"
        ),
        refine3D=Refine3D(
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
            max_sig=5000,
            mpi_command="mpirun"
        ),
        class3D=Class3D(
            ref_correct_greyscale="yes",
            ini_high=30,
            sym_name=symmetry,
            do_ctf_correction= "yes",
            ctf_intact_first_peak= "no",
            nr_classes= 10,
            tau_fudge= 2,
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
            use_gpu= "yes",
            gpu_ids= "",
            nr_threads= 8,
            mpi_command="mpirun"
        ),
        select=SelectParticles(
            do_select_values="yes",
            select_label="rlnClassNumber"
        ),
        mask_create=MaskCreate(
            lowpass_filter=20,
            extend_inimask=3,
            width_mask_edge=5
        )
    )

    with open(write_path, "w") as f:
        json.dump(default_config.dict(), f, indent=4)

    print(f'Wrote Pipeline Parameters JSON File To: {write_path}\n')

def validate_num_gpus(ctx, param, value):
    if value is not None and (value < 1 or value > 4):
        raise click.BadParameter("Number of GPUs must be between 1 and 4.")
    return value

@cli.command(context_settings={"show_default": True})
@click.option(
    "--shell-path",
    type=str,
    required=False,
    default='pipeline_sta.sh',
    help="The Saved Parameter Path",
)
@click.option(
    "--job-name",
    type=str,
    required=False,
    default="sta_relion",
    help="Job Name Displayed by Slurm Scheduler"
)
@click.option(
    "--output-file",
    type=str,
    required=False,
    default="outputs_sta_relion.out",
    help="Output Text File that Results"
)
@click.option(
    "--num-gpus",
    type=int,
    required=False,
    default=2,
    callback=validate_num_gpus,
    help="Number of GPUs for Processing"
)
@click.option(
    "--gpu-constraint",
    type=str,
    required=False,
    default="h100",
    help=""
)
def shell_submit(
    shell_path: str,
    job_name: str,
    output_file: str,
    num_gpus: int,
    gpu_constraint: str,
    ):

    shell_script_content = f"""#!/bin/bash

#SBATCH --gpus={num_gpus}
#SBATCH --ntasks={num_gpus+1}
#SBATCH --constraint="{gpu_constraint}"
#SBATCH --time=18:00:00
#SBATCH --cpus-per-task=24
#SBATCH --mem-per-cpu=16G
#SBATCH --partition=gpu
#SBATCH --job-name={job_name}
#SBATCH --output={output_file}

# Read the GPU names into an array
IFS=$'\\n' read -r -d '' -a gpu_names <<< "$(nvidia-smi --query-gpu=name --format=csv,noheader)"

# Access the first GPU name
first_gpu_name="${{gpu_names[0]}}"

# Figure Out which Relion Module to Load
echo "Detected GPU: $first_gpu_name"
if [ "$first_gpu_name" = "NVIDIA A100-SXM4-80GB" ]; then
    echo "Loading relion/CU80"
    module load relion/ver5.0-12cf15de-CU80    
elif [ "$first_gpu_name" = "NVIDIA A100-SXM4-40GB" ]; then
    echo "Loading relion/CU80"
    module load relion/ver5.0-12cf15de-CU80
elif [ "$first_gpu_name" = "NVIDIA RTX A6000" ]; then
    echo "Loading relion/CU86"
    module load relion/ver5.0-12cf15de-CU86
else
    echo "Loading relion/CU90"
    module load relion/ver5.0-12cf15de-CU90 
fi

# Generate Template (Optional)
# conda activate /hpc/projects/group.czii/krios1.processing/software/pipeline-3D-template-match/pyMatch
# pytom_create_template.py -i /hpc/projects/group.czii/krios1.processing/pytom/scripts/model_templates/ribo80S_emd_3883.map \\
# -o ribosome-template-flipped.mrc --input-voxel-size 0.85 --output-voxel-size 9.48 --low-pass 40 -b 64 -m

# Run Relion Pipeline
conda activate /hpc/projects/group.czii/krios1.processing/software/relion-sub-tomogram-pipelines/pyRelion/
run_relion5 sta-pipeline --parameter-path sta_parameters.json --reference-template ribosome-template-flipped.mrc
"""

    # Save to file
    with open(shell_path, "w") as file:
        file.write(shell_script_content)

    print(f"\nShell script has been created successfully as '{shell_path}'\n")


if __name__ == "__main__":
    cli()