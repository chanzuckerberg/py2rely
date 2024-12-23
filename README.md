# relion-sub-tomogram-pipelines
Tools for Running Relion Refinements Through CLI

## Installation
To create, first we need to generate a conda environment:

`conda create --prefix=/path/to/pyRelion python=3.10` 

Once the environment is created, activate it:
`conda activate /path/to/pyRelion`

Then install the code with:
`pip install -e .`

## Usage

To run the CLI tools, there's a few commands this package offers. There's several entry points to run this pipeline. In all cases, the relion requires for the data to be available inside of the project. We can symlink the data and generate a STAR file containing the particle coordinates with the following command:

We can generate a sample JSON file which provides all the necessary input parameters with the following command:

`create_parameters relion5 --file-path <class_averages_parameters.json>`

The first step is composed of importing tomograms, 
