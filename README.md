# py2rely - Python 2 Rely On
**Py**thonic **RELION** interface for streamlined sub-tomogram averaging on SLURM HPC clusters.

## Introduction

py2rely simplifies and accelerates the execution of RELION-based sub-tomogram averaging (STA) workflows on SLURM-based high-performance computing (HPC) systems. Designed for rapid iteration and evaluation of particle picking strategies, py2rely integrates with existing tilt series alignment from AreTomo and particle coordinate storage from [copick](https://github.com/copick/copick), making it ideal for automated benchmarking and structure validation.

## 💫 Key Features

* ⚙️ Automated job preparation: One-command setup of RELION STA workflows including particle extraction, classification, and refinement.
* 🔄 Copick integration: Seamless import of particle coordinates from copick metadata storage.
* 🧭 Tilt series-aware: Direct input of alignment and metadata from AreTomo processing pipelines.
* 🚀 SLURM-native execution: Jobs are launched, monitored, and managed directly on HPC SLURM environments.
* 🧠 Validation-ready: Quickly test new particle picking algorithms and assess their reconstruction outcomes with minimal setup.

## Installation
To create, first we need to generate a conda environment:

`conda create --prefix=/path/to/py2rely -c conda-forge gcc_linux-64 cupy python=3.10` 

Once the environment is created, activate it:
`conda activate pyRely`

Then install the code with:
`pip install -e .`

## 📚 Documentation 

For comprehensive guides, usage examples, and API references, visit the py2rely documentation.

## 🤝 Contributing 

This project adheres to the Contributor Covenant code of conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to opensource@chanzuckerberg.com.

## 🔒 Security

If you believe you have discovered a security vulnerability, please report it responsibly to security@chanzuckerberg.com.
