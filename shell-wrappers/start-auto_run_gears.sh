#!/usr/bin/env bash

#
# Place any cluster-specific commands here...
#

#
# End cluster-specific block
#

# Logfile location
logfile="auto_run_gears.log"

#source flywheel environment
source /curc/sw/anaconda3/latest
conda activate flywheel

# Launch auto-gear set (uses gear template stored in flywhel project)
# Using "timeout" prevents the script hanging when launched automatically.
# This time limit may need to be adjusted based on the speed of your system.
timeout 300m python run_autoworkflow.py "$@" 2>&1 | tee -a "$logfile"
