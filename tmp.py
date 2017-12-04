# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# tmp.py
# Created on: 2017-12-04 12:28:00.00000
#   (generated by ArcGIS/ModelBuilder)
# Usage: tmp <Input_Road_Centerlines> <Output_Road_Centerlines_Subset> 
# Description: 
# Selects road centerlines that are being considered 'valid'. 
# This tool selects those attribute that are not 
# alleys
# parking lot roads
# walkways
# service vehicle private drives
# bike paths 

# ---------------------------------------------------------------------------

# Import arcpy module
import arcpy

# Script arguments
Input_Road_Centerlines = arcpy.GetParameterAsText(0)
if Input_Road_Centerlines == '#' or not Input_Road_Centerlines:
    Input_Road_Centerlines = "VA_CENTERLINE" # provide a default value if unspecified

Output_Road_Centerlines_Subset = arcpy.GetParameterAsText(1)

# Local variables:

# Process: Select Roads
arcpy.Select_analysis(Input_Road_Centerlines, Output_Road_Centerlines_Subset, "MTFCC NOT IN ( 'S1730', 'S1780', 'S9999', 'S1710', 'S1720', 'S1740', 'S1820', 'S1830', 'S1500' )")

