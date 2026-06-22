import rich_click as click

# Configure rich-click
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True

click.rich_click.COMMAND_GROUPS = {
    "py2rely": [
        {
            "name": "Setup & Configuration",
            "commands": ["config", "mcp"],
        },
        {
            "name": "Data Preparation",
            "commands": ["prepare", "utils", "export"],
        },
        {
            "name": "Run Jobs",
            "commands": ["pipelines", "routines", "slab", "ui"],
        },
    ],
}

click.rich_click.OPTION_GROUPS = {
    "py2rely ui": [
        {
            "name": "Server",
            "options": ["--port", "--host", "--no-browser"],
        },
        {
            "name": "Monitoring",
            "options": ["--poll-interval"],
        },
    ],
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
                        "--extract3D", "--run-class3D", "--class-selection", "--manual-masking"],
        },
        {
            "name": "Compute and Submitit Resources",
            "options": ["--num-days", "--num-gpus", "--gpu-constraint",  "--cpu-constraint", "--timeout"],
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
    "py2rely pipelines bin1": [
        {
            "name": "Pipeline Options",
            "options": ["--parameter", "--tomograms", "--particles", "--mask", "--low-pass", '--rerun'],
        },
        {
            "name": "Submitit Options",
            "options": ["--submitit", "--cpu-constraint", "--gpu-constraint", "--num-gpus", "--timeout"],
        }
    ],
    "py2rely pipelines sta": [
        {
            "name": "Pipeline Options",
            "options": ["--parameter", "--manual-masking", "--extract3D", "--run-class3D", "--class-selection"],
        },
        {
            "name": "Initial Model Generation",
            "options": ["--run-denovo-generation", "--reference-template"],
        },
        {
            "name": "Submitit Options",
            "options": ["--submitit", "--cpu-constraint", "--gpu-constraint", "--num-gpus", "--timeout"],
        }
    ],
    "py2rely pipelines polish": [
        {
            "name": "Polishing Options",
            "options": ["--parameter", "--particles", "--mask", "--tomograms", "--motion", "--num-iterations"],
        },
        {
            "name": "Submitit Options",
            "options": ["--submitit", "--cpu-constraint", "--gpu-constraint", "--num-gpus", "--timeout"],            
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
                "--center-class"
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
    ],
    "py2rely routines extract": [
        {
            "name": "I/O",
            "options": ["--tomogram", "--particles", "--motion", "--parameter"],
        },
        {
            "name": "Parameters",
            "options": ["--binfactor", "--boxsize", "--cropsize"],
        },
        {
            "name": "Compute Resources",
            "options": ["--nthreads", "--nprocesses"],
        },
    ], 
    "py2rely routines reconstruct": [
        {
            "name": "I/O",
            "options": ["--particles", "--tomograms", "--motion", "--parameter"],
        },
        {
            "name": "Parameters",
            "options": ["--binfactor", "--boxsize", "--cropsize", "--symmetry"],
        },
        {
            "name": "Compute Resources",
            "options": ["--nthreads", "--nprocesses"],
        },
    ],
    "py2rely routines class3d": [
        {
            "name": "I/O",
            "options": ["--particles", "--parameter", "--reference", "--mask"],
        },
        {
            "name": "Parameters",
            "options": ["--ini-high", "--tau-fudge", "--nr-classes", "--nr-iter", "--ref-correct-greyscale", "--align-particles", "--nr-classes"],
        },
    ],
    "py2rely routines refine3d": [
        {
            "name": "I/O",
            "options": ["--parameter", "--particles", "--reference", "--mask", "--motion", "--tomogram", "--continue-iter"],
        },
        {
            "name": "Parameters",
            "options": ["--diameter", "--symmetry", "--low-pass", "--ref-correct-greyscale"],
        },
        {
            "name": "Sampling Angles",
            "options": ["--sampling-angle", "--local-sampling-angle"],
        },
        {
            "name": "Compute Resources",
            "options": ["--nthreads", "--nprocesses", "--use-gpu", "--nr-pool"],
        },
    ],
}