library("stringr")


# Notes ----
#
# This script will make AFNI-styled timing files from
# <proj_dir>/dset/**/func events.tsv files. Output files 
# will be written to <write_dir>.
#
# Output file named tf_<task>_<behavior>.txt. Non-responses
# are titled tf_<task>_NR.txt. If a certain timing file contains
# only asterisks (no behaviors of that type occurred), it will
# be removed.
#
# Written to test pipeline on ses-S2 O|T vs N|T, but could be updated
# to incorporate all unique behavior (ref switch_string).
#
# Positional Arguments:
#   [1] = BIDS project directory
#   [2] = BIDS subject string
#   [3] = BIDS session string
#   [4] = BIDS task string
#   [5] = subject output directory
#   [6-8] = events files for runs 1-3


# Set Up -----
#
# Receive wrapped variables, set lists, and make switches.

tsv_list <- vector()
args <- commandArgs()
proj_dir <- args[6]
subj <- args[7]
sess <- args[8]
task <- args[9]
write_dir <- args[10]
tsv_list[1] <- args[11]
tsv_list[2] <- args[12]
tsv_list[3] <- args[13]

source_dir <- paste(proj_dir, subj, sess, "func", sep = "/")
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
    "targ_ht" = "stimTH",
    "targ_ms" = "stimTM",
    "lure_cr" = "stimLC",
    "lure_fa" = "stimLF",
    "foil_cr" = "stimFC",
    "foil_fa" = "stimFF"
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
    row_out <- round(df_run[ind_nan,]$onset, 1)
  }
  out_file <- paste0(write_dir, "/", "tf_", task, "_NR.txt")
  cat(row_out, "\n", file = out_file, append = h_append, sep = "\t")

  # each stimulus type x behavior
  for(stim in sim_list){
    beh_list <- switch_behavior(stim)
    for(beh in beh_list){

      # find behavior
      ind_beh <- which(
        df_run$trial_type == paste0("neg_", beh) |
          df_run$trial_type == paste0("neu_", beh) |
          df_run$trial_type == paste0("pos_", beh)
        )
      if(length(ind_beh) == 0){
        row_out <- "*"
      }else{
        row_out <- round(df_run[ind_beh,]$onset, 1)
      }

      # write
      h_str <- switch_string(beh)
      out_file <- paste0(write_dir, "/", "tf_", task, "_", h_str, ".txt")
      cat(row_out, "\n", file = out_file, append = h_append, sep = "\t")
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
