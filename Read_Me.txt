FEBio Material Parameter Optimization (Python)
--------------------------------------------------
    Purpose

This repository implements an automated material parameter optimization workflow for FEBio models.

The system replaces manual parameter tuning or MATLAB-based loops with a Python-driven optimization framework that:

    Modifies FEBio input files

    Executes FEBio

    Extracts simulation results

    Compares them against experimental data

    Iteratively updates material parameters to minimize error

The code is modular by design to allow straightforward extension to:

    Multiple material parameters

    Alternative error metrics

    Different FEBio output quantities
--------------------------------------------------
Conceptual Overview

At a high level, the optimization proceeds as follows:

Parameter guess
   ↓
Modify FEBio model
   ↓
Run FEBio
   ↓
Extract reaction forces
   ↓
Compare to experiment
   ↓
Compute error
   ↓
Update parameter


Only one scalar value (error) is returned to the optimizer at each iteration.
--------------------------------------------------
Repository Structure
Febio_optimizer/
│
├── optimize.py          # Optimization driver (run this)
├── objective.py         # Defines objective function
├── edit_feb.py          # Modifies FEBio input files
├── run_febio.py         # Executes FEBio
├── parsing.py           # Reads and processes output data
│
├── Simple Shear Cube_120525_modelrun.feb
├── shear_Sample35_.csv
│
└── run_log.csv           # Generated automatically
--------------------------------------------------
Execution Entry Point
optimize.py

This is the only file most users need to run.

It calls SciPy’s bounded scalar optimizer to minimize the objective function.

python optimize.py
--------------------------------------------------
Output Example
success: True
x: 1.058
fun: 117.30


x → optimized material coefficient (c1)

fun → final error value

FEBio is run once per evaluation
--------------------------------------------------
Core Components
1. objective.py — Optimization Objective

Defines the mapping:

material coefficient → scalar error


For each trial value:

A temporary working directory is created

The FEBio input file is modified

FEBio is executed

Output force data are parsed

Simulation and experiment are aligned

Percent error is computed

Results are logged

All temporary files are deleted

Inputs

Material coefficient(s)

FEBio template file

Experimental CSV file

Output

Single scalar error returned to the optimizer

Persistent logging to run_log.csv

This file contains no optimizer logic.
--------------------------------------------------
2. edit_feb.py — FEBio File Modification

Responsible for modifying the <Material> block in the FEBio XML file.

Reads the template .feb

Updates specified coefficients (e.g., c1)

Writes a new .feb file

This module does no numerical computation and does not run FEBio.
--------------------------------------------------
3. run_febio.py — FEBio Execution Interface

Provides a thin wrapper around FEBio’s command-line interface.

Calls febio4.exe

Runs in an isolated working directory

Captures stdout/stderr

Returns execution status

All FEBio-generated files remain local to the temporary directory and are removed after parsing.
--------------------------------------------------
4. parsing.py — Data Extraction and Error Metrics

Handles all data parsing and comparison:

Reads experimental CSV data

Reads FEBio-generated text output

Aligns simulation and experiment by step

Computes error metrics

Currently implemented error metric:

Percent error

This module is the correct place to:

Change error definitions

Add RMS or norm-based metrics

Introduce filtering or smoothing
--------------------------------------------------
Data Logging

Each FEBio run records:

c1,percent_error


in run_log.csv.

This allows:

Post-hoc statistical analysis

Visualization

Debugging convergence behavior

Optimization does not depend on this file.
--------------------------------------------------
Design Principles (Important)

Optimization returns scalars only

FEBio I/O is isolated per run

Temporary files are always deleted

Experimental data are loaded once

Code is modular by responsibility

This structure mirrors typical MATLAB optimization workflows, but with stricter separation of concerns.
--------------------------------------------------
Extending the Framework
Multiple Parameters

Add parameters to objective.py and switch from minimize_scalar to minimize.

Alternative FEBio Outputs

Modify:

parse_reaction_text()

Alternative Error Metrics

Modify:

percent_error()

Visualization

Use run_log.csv in a separate analysis script.
--------------------------------------------------
Intended Usage Contract

To avoid breaking the pipeline:

Do not modify optimize.py unless changing optimization strategy

Modify FEBio output definitions only in the .feb file

Modify error definitions only in parsing.py

Modify material coefficients only in edit_feb.py
--------------------------------------------------
Typical User Workflow

Place FEBio template in repository

Place experimental CSV in repository

Adjust paths in objective.py

Run:

python optimize.py


Inspect optimized parameters and run_log.csv
--------------------------------------------------
Notes for MATLAB Users

objective.py ≈ MATLAB objective function

optimize.py ≈ fminbnd

parsing.py ≈ data preprocessing scripts

Temporary directories replace MATLAB’s global workspace
--------------------------------------------------
Final Remarks

This repository is intended for research use, not as a general-purpose FEBio package.
Users are encouraged to read objective.py before modifying any behavior.