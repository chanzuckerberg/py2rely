import rich_click as click

# Configure rich-click
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True

# click.rich_click.COMMAND_GROUPS = {
# }

click.rich_click.OPTION_GROUPS = {
    "py2rely prepare particles": [
        {
            "name": "I/O",
            "options": ["--config", "--session", "--pixel-size", "--output"]
        },
        {
            "name": "Copick Query",
            "options": ["--name", "--user-id", "--session-id", "--authors"]
        },
        {
            "name": "Query Filters",
            "options": ["--run-ids", "--voxel-size"]
        },
        {
            "name": "Tomogram Dimensions",
            "options": ["--x", "--y", "--z"]
        },
        {
            "name": "Optic Groups",
            "options": ['--voltage', '--spherical-aberration', '--amplitude-contrast', "--optics-group", "--optics-group-name", "--relion5"]
        }
    ],
    "py2rely prepare tilt-series": [
        {
            "name": "I/O",
            "options": ["--base-project", "--session", "--run", "--output"]
        },
        {
            "name": "Experimental Parameters",
            "options": ["--pixel-size", "--total-dose"]
        },
        {
            "name": "Optic Groups",
            "options": ['--voltage', '--spherical-aberration', '--amplitude-contrast', "--optics-group", "--optics-group-name", "--relion5"]
        }
    ],
    "py2rely prepare relion5-parameters": [
        {
            "name": "I/O",
            "options": ["--tilt-series", "--particles", "--tilt-series-pixel-size", "--output"]
        },
        {
            "name": "Particle",
            "options": ["--symmetry", "--protein-diameter", "--low-pass"]
        },
        {
            "name": "Pipeline",
            "options": ['--denovo-generation', '--box-scaling', '--nclasses', "--ninit-models", "--binning-list"]
        },
        {
            "name": "Compute",
            "options": ['--nthreads', '--nprocesses']
        }
    ],
    "py2rely prepare relion5-pipeline": [
        {
            "name": "Pipeline",
            "options": ["--parameter", "--reference-template", "--run-denovo-generation", 
                        "--extract3D", "--run-class3D", "--manual-masking"],
        },
        {
            "name": "Compute and Submitit Resources",
            "options": ["--num-days", "--num-gpus", "--gpu-constraint", "--submitit", "--cpu-constraint", "--timeout"],
        }
    ],
    "py2rely prepare template": [
        {
            "name": "Input Map",
            "options": ["--input", "--input-voxel-size"],
        },
        {
            "name": "Processing",
            "options": ["--center", "--low-pass", "--invert", "--mirror"],
        },
        {
            "name": "Output",
            "options": ["--output", "--output-voxel-size", "--box-size"],
        }
    ],
    "py2rely pipelines sta": [
        {
            "name": "Pipeline Options",
            "options": ["--parameter", "--extract3D", "--run-class3D", "--manual-masking"],
        },
        {
            "name": "Initial Model Generation",
            "options": ["--run-denovo-generation", "--reference-template"],
        },
        {
            "name": "Submitit Options",
            "options": ["--submitit", "--cpu-constraint", "--gpu-constraint", "--timeout"],
        }
    ],
    "py2rely slab class2d": [
        {
            "name": "Input",
            "options": ["--particles"],
        },
        {
            "name": "Class2D",
            "options": [
                "--nr-classes",
                "--nr-iter",
                "--tau-fudge",
                "--class-algorithm",
                "--particle-diameter",
                "--highres-limit",
                "--do-ctf-correction",
                "--ctf-intact-first-peak",
                "--dont-skip-align",
            ],
        },
        {
            "name": "Compute Resources",
            "options": [
                "--use-gpu",
                "--nr-threads",
            ],
        },
    ],
    "py2rely-slurm slab class2d": [
        {
            "name": "Class2D",
            "options": [
                "--particle-diameter",
                "--tau-fudge",
                "--num-classes",
                "--highres-limit",
                "--class-algorithm",
            ],
        },
        {
            "name": "Slurm",
            "options": [
                "--num-gpus",
                "--gpu-constraint",
                "--num-threads",
                "--bootstrap-ntrials"                
            ],
        },
    ],
    "py2rely-slurm slab slabpick": [
        {
            "name": "I/O",
            "options": ["--in-coords", "--in-vols", "--out-dir"],
        },
        {
            "name": "Copick Query",
            "options": ["--tomo-alg", "--user-id", "--particle-name", "--session-id"],
        },
        {
            "name": "Extraction",
            "options": ["--extract-shape", "--voxel-spacing", "--pixel-size"],
        },
    ]    
}