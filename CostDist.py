# ---------------------------------------------------------------------------
# CostDist.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creator: Kirsten R. Hazler
# Creation Date: 2017-10-24 
# Last Edit: 2017-10-24

# Summary:
# A collection of functions for running cost distance analysis based on road speeds.

# Usage tips:
# Prior to running the functions in this module, use the following function sequence from ProcRoads.py to prepare roads for travel time analysis:
# - PrepRoadsVA (to prepare Virginia RCL data)
# - PrepRoadsTIGER (to prepare TIGER roads data from adjacent states)
# - MergeRoads (to merge the RCL and TIGER datasets into a seamless dataset, with a limited set of critical fields in the output)
# 
# The following functions are helper functions called by the above functions:
# - printMsg (shortcut for informative progress messaging)
# - ProjectToMatch (to project one dataset to match the coordinate system of another)
# ---------------------------------------------------------------------------