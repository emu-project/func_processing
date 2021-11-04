"""Title.

Desc.
"""
# %%
import os


# %%
def run_ashs(subj, t1_file, t2_file, work_dir):
    """Run automatic hippocampal subfield segmentation.

    Use ASHS singularity to generate HC subfield labels.

    Parameters
    ----------

    Returns
    -------

    """

    try:
        os.environ["ASHS_ROOT"]
    except KeyError:
        print("$ASHS_ROOT not detected, please activate ashs_env.")

    h_cmd = f"""
        ashs_main.sh \
            -I {subj} \
            -a /home/data/madlab/atlases/ashs_atlas_magdeburg \
            -g {t1_file} \
            -f {t2_file} \
            -w {work_dir}
    """
