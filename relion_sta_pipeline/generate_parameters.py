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
    in_tomograms: Optional[str] = None
    in_particles: Optional[str] = None
    crop_size: int
    point_group: str
    nr_threads: int
    mpi_command: str
    
class PseudoSubtomo(BaseModel):
    in_tomograms: str
    in_particles: str
    crop_size: int
    do_float16: str
    do_output_2dstacks: Optional[str] = None
    nr_threads: int
    mpi_command: str

class Refine3D(BaseModel):
    tomograms_star: str
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
    other_args: str

class Class3D(BaseModel):
    tomograms_star: str
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
    prior_tiltang_width: int
    
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
            nr_classes=1,
            tau_fudge=4.0,
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
            nr_classes= 5,
            tau_fudge= 4,
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
        initial_model=InitialModel(
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
        reconstruct=Reconstruct(
            in_tomograms=input_tilt_series,            
            in_particles= input_particles,
            do_from2d="yes",
            crop_size=-1,
            point_group=symmetry,
            nr_threads=16,
            mpi_command="mpirun"
        ),
        pseudo_subtomo=PseudoSubtomo(
            in_tomograms=input_tilt_series,
            in_particles= input_particles,            
            crop_size=-1,
            do_float16="yes",
            do_output_2dstacks="yes",            
            nr_threads=16,
            mpi_command="mpirun"
        ),
        refine3D=Refine3D(
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
        class3D=Class3D(
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


if __name__ == "__main__":
    cli()