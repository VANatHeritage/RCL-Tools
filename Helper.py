"""
Helper.py
Version:  ArcGIS Pro / Python 3.x
Creator: Kirsten R. Hazler / David Bucklin
Creation Date: 2017-10-24
Last Edit: 2022-07-07

Summary:
As of 2022-07-07, generic helper functions are imported from external modules (https://github.com/VANatHeritage/pyHelper).
This script should contain only objects, functions, and settings specific to this repo.
"""

# Import modules
from helper_arcpy import *
from datetime import datetime as datetime
arcpy.CheckOutExtension("Spatial")

scratchGDB = arcpy.env.scratchGDB
arcpy.env.overwriteOutput = True
