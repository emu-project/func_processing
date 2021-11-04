"""Generate and run deconvolution.

Uses AFNI's 3dDeconvolve and 3dREMLfit to deconvolve
EPI data. Uses 3dDeconvolve to write X.files and
generate foo_stats.REML_cmd script. REML script
is then executed. Nuissance signal is also generated
via a blurred white matter timeseries.

Notes
-----
Requires AFNI

Json file for -t option should have the following format:

{"Decon Tile": {
    "BehA": "/path/to/timing_behA.txt",
    "BehB": "/path/to/timing_behB.txt",
    "BehC": "/path/to/timing_behC.txt",
    }
}

{"NegNeuPosTargLureFoil": {
    "negTH": "/path/to/negative_target_hit.txt",
    "negTM": "/path/to/negative_target_miss.txt",
    "negLC": "/path/to/negative_lure_cr.txt",
    }
}
"""
# %%
import os
import sys
import json
from argparse import ArgumentParser, RawTextHelpFormatter

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from resources.afni import deconvolve


# %%
# For testing
deriv_dir = "/scratch/madlab/emu_test/derivatives"
subj = "sub-4002"
sess = "ses-S2"
timing_dir = os.path.join(deriv_dir, "timing_files", subj, sess)

# setup directories
afni_dir = os.path.join(deriv_dir, "afni")
work_dir = os.path.join(afni_dir, subj, sess)

# with open(os.path.join(work_dir, decon_json)) as jf:
#     decon_plan = json.load(jf)

afni_json = "afni_data.json"
with open(os.path.join(work_dir, afni_json)) as jf:
    afni_data = json.load(jf)

# write deconvolution
dur = 2
# for decon_str in decon_plan:
#     tf_dict = decon_plan[decon_str]
#     afni_data = deconvolve.write_decon(dur, decon_str, tf_dict, afni_data, work_dir)

# make tf_dict
time_list = [x for x in os.listdir(timing_dir)]
time_list.sort()
decon_str = time_list[0].split("_")[2]
tf_dict = {}
for time_file in time_list:
    beh = time_file.split("_")[-1].split(".")[0]
    tf_dict[beh] = os.path.join(timing_dir, time_file)
afni_data = deconvolve.write_decon(dur, decon_str, tf_dict, afni_data, work_dir)

# run deconvolution
afni_data = deconvolve.run_reml(work_dir, afni_data)
with open(os.path.join(work_dir, "afni_data.json"), "w") as jf:
    json.dump(afni_data, jf)
