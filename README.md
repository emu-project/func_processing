# func_processing
Pipeline used to take functional data from DICOMs through group-level analyses. 

## Entry Points
Following `python setup.py install` or `python setup.py develop`, use the following entry points to trigger cli.

- `check` : print help, run `cli.checks`, used to determine which participants have which preprocessed files.
- `ashs` : trigger help of `cli.ashs`, for running Automated Hippocampal Subfield Segmentation.
- `reface` : trigger help of `cli.reface`, for de/refacing participant T1w files.
- `fmriprep` : trigger help of `cli.fmriprep`, for moving data found in `dset` through FreeSurfer and fMRIPrep.
- `task_subj` : trigger help of `cli.afni_task_subj`, move task EPI output of `fmriprep` through extra preprocessing, deconvolution.
- `rs_subj` : trigger help of `cli.afni_resting_subj`, move resting EPI output of `fmriprep` through extra preprocessing, deconvolution.
- `task_group` : trigger help of `cli.afni_task_group`, conduct group-level task EPI analyses.
- `rs_group` : trigger help of `cli.afni_resting_group`, conduct group-level resting EPI analyses.

## Project organization

Top Level

- dockerfiles : Dockerfile, shell script backup
- docs : Project documentation, for [ReadTheDocs](https://emu-func-processing.readthedocs.io/en/latest/), assuming sphinx is cooperative. Build instruction found in build_docs.txt. 
- func_processing : Main package

func_processing

- cli : Contains scripts to start AFNI, ASHS, fMRIprep, FreeSurfer, refacing, and data checking workflows.
- examples : Contains example scripts and files.
- logs : Mainly for completed_preprocessing.tsv, other output logs written here.
- resources : Location of modules for AFNI, ASHS, FreeSurfer, fMRIprep, and reports.
- tests : Scripts for testing resources and workflows.
- tools : Location for auxiliary/shell scripts. Currently contains (outdated) cron scripts
- workflow : Manages resources, controlled by cli.

See [Wiki](https://github.com/emu-project/func_processing/wiki) for details and description, now a little outdated due to refactoring.
