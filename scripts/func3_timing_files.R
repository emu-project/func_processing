library("stringr")


# Notes ----
#
# This script will make AFNI-styled timing files from
# dset/func events.tsv files. Output files will be written
# to project_dir/derivatives/afni/subj/sess/timing_files.
#
# Output file named tf_<task>_<behavior>.txt. Non-responses
# are titled tf_<task>_NR.txt. If a certain timing file contains
# only asterisks (no behaviors of that type occurred), it will
# be removed.
#
# Currently only onset is written, but merely commented out.
# Perhaps this could be toggled in the future.
#
# Usage:
#
#   Rscript func3_timing_files.R \
#     proj_dir subj sess task
#
# Example Usage:
#
#   Rscript func3_timing_files.R \
#     /scratch/madlab/emu_UNC \
#     sub-4005 \
#     ses-S2 \
#     test 


# Set Up -----
#
# Receive wrapped variables, set lists, and make switches.
#
# Possible valences are neg, neu, and pos. Possible stimulus
# similarities are targ, lure, foil. So, 3 * 3 * 2 + 1 timing
# files will be written (valence * similarity * in/correct + NR).
#
# A unique behavior string will be made for each via switch_string
# for tf_<task>_<behavior>.txt.

args <- commandArgs()
proj_dir <- args[6]
subj <- args[7]
sess <- args[8]
task <- args[9]

# # For testing
# proj_dir <- "~/Desktop"
# subj <- "sub-4005"
# sess <- "ses-S2"
# task <- "test"

write_dir <- paste0(
  proj_dir, "derivatives/afni", subj, sess, "timing_files", sep = "/"
)
source_dir <- paste(proj_dir, "dset", subj, sess, "func", sep = "/")
tsv_list <- list.files(source_dir, pattern = "\\.tsv$", full.names = T)

val_list <- c("neg", "neu", "pos")
sim_list <- c("targ", "lure", "foil")

switch_behavior <- function(h_type) {
  beh_type <- switch(
    h_type,
    "targ" = c("targ_ht", "targ_ms"),
    "lure" = c("lure_cr", "lure_fa"),
    "foil" = c("foil_cr", "foil_fa")
  )
  return(beh_type)
}

switch_string <- function(h_str) {
  out_str <- switch(
    h_str,
    "neg_targ_ht" = "negTH",
    "neg_targ_ms" = "negTM",
    "neg_lure_cr" = "negLC",
    "neg_lure_fa" = "negLF",
    "neg_foil_cr" = "negFC",
    "neg_foil_fa" = "negFF",
    "neu_targ_ht" = "neuTH",
    "neu_targ_ms" = "neuTM",
    "neu_lure_cr" = "neuLC",
    "neu_lure_fa" = "neuLF",
    "neu_foil_cr" = "neuFC",
    "neu_foil_fa" = "neuFF",
    "pos_targ_ht" = "posTH",
    "pos_targ_ms" = "posTM",
    "pos_lure_cr" = "posLC",
    "pos_lure_fa" = "posLF",
    "pos_foil_cr" = "posFC",
    "pos_foil_fa" = "posFF",
  )
  return(out_str)
}


# Make timing files -----
#
# Iterate through each tsv, build run rows for
# each behavior. Lack of behavior yields "*" written to row.
# Onset married with duration.

for(run in 1:length(tsv_list)){

  # determine whether to append, read in data
  h_append <- ifelse(run == 1, F, T)
  df_run <- read.delim(tsv_list[run], sep = "\t", header = T)

  # deal with non responses
  ind_nan <- which(df_run$trial_type == "NaN")
  if(length(ind_nan) == 0){
    row_out <- "*"
  }else{
    # row_out <- paste(
    #   round(df_run[ind_nan,]$onset, 1),
    #   df_run[ind_nan,]$duration,
    #   sep = ":"
    # )
    row_out <- round(df_run[ind_nan,]$onset, 1)
  }
  out_file <- paste0(write_dir, "/", "tf_", task, "_NR.txt")
  cat(row_out, "\n", file = out_file, append = h_append, sep = "\t")

  # each valence x stimulus type x beahvior
  for(val in val_list){
    for(stim in sim_list){
      beh_list <- switch_behavior(stim)
      for(beh in beh_list){

        # find behavior
        ind_beh <- which(df_run$trial_type == paste(val, beh, sep = "_"))

        # marry, write
        if(length(ind_beh) == 0){
          row_out <- "*"
        }else{
          # row_out <- paste(
          #   round(df_run[ind_beh,]$onset, 1),
          #   df_run[ind_beh,]$duration,
          #   sep = ":"
          # )
          row_out <- round(df_run[ind_beh,]$onset, 1)
        }
        # h_str <- str_replace(beh, "[_]", "")
        # out_file <- paste0(write_dir, "/", "tf_", task, "_", val, h_str, ".txt")
        h_str <- switch_string(paste(val, beh, sep = "_"))
        out_file <- paste0(write_dir, "/", "tf_", task, "_", h_str, ".txt")
        cat(row_out, "\n", file = out_file, append = h_append, sep = "\t")
      }
    }
  }
}


# Remove empty timing files -----
#
# Remove files containing only asterisks, since 
# AFNI will have a cow with those. Technically,
# I actually check to make sure there is more than
# one unique value in the first column. Surely this
# will always work.

tf_list <- list.files(write_dir, pattern = "\\.txt$", full.names = T)
for(h_tf in tf_list){
  h_check <- read.delim(h_tf, header = F)
  if(length(unique(h_check$V1)) == 1){
    file.remove(h_tf)
  }
}
