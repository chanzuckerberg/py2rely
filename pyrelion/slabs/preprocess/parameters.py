from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import json, click

class ImportMicrographs(BaseModel):
    fn_in_raw: str
    is_multiframe: str
    angpix: int
    kV: int
    Cs: float
    Q0: float

class ExtractParticles(BaseModel):
    coords_suffix: str
    extract_size: int
    bg_diameter: int
    
class Class2D(BaseModel):
    do_ctf_correction: str
    ctf_intact_first_peak: str
    particle_diameter: int
    do_zero_mask: str
    highres_limit: int 
    dont_skip_align: str
    psi_sampling: int 
    offset_range: int 
    offset_step: int 
    allow_coarser: str
    nr_pool: int
    do_preread_images: str
    use_gpu: str
    gpu_ids: str
    nr_threads: int
    
class SelectParticles(BaseModel):
    do_select_values: str
    select_label: str
    
class ProcessingConfig(BaseModel):
    import_micrographs: Optional[ImportMicrographs]
    extract: Optional[ExtractParticles]
    class2D: Class2D
    select: SelectParticles

class ClassAverageConfig(BaseModel):
    class2D: Class2D
    select: SelectParticles

def write_extraction_pipeline(
    write_path: str,
    pixel_size: float,
    extraction_size: int,
    bg_diameter: int,
    protein_diameter: float,
    require_extraction: bool,
    ):
    default_config = ProcessingConfig(
        import_micrographs=ImportMicrographs(
            fn_in_raw="input/*.mrc",
            is_multiframe="no",
            angpix=pixel_size,
            kV=300,
            Cs=2.7,
            Q0=0.07
        ) if require_extraction else None,
        extract=ExtractParticles(
            coords_suffix="input/particles.star",
            extract_size=extraction_size,
            bg_diameter=bg_diameter
        ) if require_extraction else None,
        class2D=Class2D(
            do_ctf_correction= "no",
            ctf_intact_first_peak= "no",
            particle_diameter= protein_diameter,
            do_zero_mask= "yes",   
            highres_limit= -1,
            dont_skip_align= "yes",
            psi_sampling= 6,
            offset_range= 5,
            offset_step= 1,
            allow_coarser= "no",
            nr_pool= 30,
            do_preread_images= "no",        
            use_gpu= "yes",
            gpu_ids= "",
            nr_threads= 8,
        ),
        select=SelectParticles(
            do_select_values="yes",
            select_label="rlnClassNumber"
        )
    )

    print(require_extraction)

    with open(write_path, "w") as f:
        json.dump(default_config.dict(), f, indent=4)  

    print(f"\nPipeline Parameters script has been created successfully as '{write_path}'\n")  

def write_classification_pipeline(
    write_path: str,
    protein_diameter: float,
    ):

    default_config = ClassAverageConfig(
        class2D=Class2D(
            do_ctf_correction= "no",
            ctf_intact_first_peak= "no",
            particle_diameter= protein_diameter,
            do_zero_mask= "yes",   
            highres_limit= -1,
            dont_skip_align= "yes",
            psi_sampling= 6,
            offset_range= 5,
            offset_step= 1,
            allow_coarser= "no",
            nr_pool= 30,
            do_preread_images= "no",        
            use_gpu= "yes",
            gpu_ids= "",
            nr_threads= 8,
        ),
        select=SelectParticles(
            do_select_values="yes",
            select_label="rlnClassNumber"
        )
    )
    
    with open(write_path, "w") as f:
        json.dump(default_config.dict(), f, indent=4)  

    print(f"\nPipeline Parameters script has been created successfully as '{write_path}'\n")
