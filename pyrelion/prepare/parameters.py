from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

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
    in_tomograms: str
    use_direct_entries: str
    nr_iter: int
    nr_classes: int
    tau_fudge: float
    particle_diameter: float
    sym_name: str
    do_run_C1: str
    nr_pool: int
    use_gpu: str
    gpu_ids: str
    nr_threads: int

class Reconstruct(BaseModel):
    in_tomograms: Optional[str] = None
    in_particles: Optional[str] = None
    do_use_direct_entries: str
    crop_size: int
    point_group: str
    nr_threads: int
    mpi_command: str

class PseudoSubtomo(BaseModel):
    in_tomograms: str
    in_particles: str
    do_use_direct_entries: str
    crop_size: int
    do_float16: str
    do_output_2dstacks: Optional[str] = None
    nr_threads: int
    nr_mpi: int

class Refine3D(BaseModel):
    in_tomograms: str
    ref_correct_greyscale: str
    use_direct_entries: str
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
    in_tomograms: str
    use_direct_entries: str
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
    sigma_tilt: int
    other_args: str

class SelectParticles(BaseModel):
    do_select_values: str
    select_label: str

class MaskCreate(BaseModel):
    lowpass_filter: int
    extend_inimask: int
    width_mask_edge: int

class CtfRefine(BaseModel):
    model_config = {"populate_by_name": True}
    in_tomograms: str
    use_direct_entries: str
    do_defocus: str
    focus_range: float
    do_reg_def: str
    lambda_param: float = Field(alias="lambda") 
    do_scale: str
    do_frame_scale: str
    nr_threads: int    

class BayesianPolish(BaseModel):
    in_tomograms: str
    use_direct_entries: str
    max_error: float
    do_motion: str
    sigma_vel: float
    sigma_div: float
    nr_threads: int    

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
    ctf_refine: Optional[CtfRefine]
    bayesian_polish: Optional[BayesianPolish]
