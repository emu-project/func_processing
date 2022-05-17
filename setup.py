# develop: python setup.py develop
# install: python setup.py install
from setuptools import setup, find_packages

setup(
    name="func_processing",
    version="1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "check=func_processing.cli.checks:main",
            "ashs=func_processing.cli.ashs:main",
            "reface=func_processing.cli.reface:main",
            "fmriprep=func_processing.cli.fmriprep:main",
            "task_subj=func_processing.cli.afni_task_subj:main",
            "task_group=func_processing.cli.afni_task_group:main",
            "rs_subj=func_processing.cli.afni_resting_subj:main",
            "rs_group=func_processing.cli.afni_resting_group:main",
        ]
    },
)
