# -*- coding: utf-8 -*-
"""
Run network analyst tools via command line.

Assumes an already-created network dataset. (See NetworkAnalyst-Setup.txt for instructions)

Created on Mon Oct 23 11:44:44 2017

@author: David Bucklin
Edited by: Kirsten Hazler, 2017-10-25
"""
# Import Helper module and functions
import Helper
from Helper import *

#import arcpy
#import time
#import os
from arcpy import env

# Check out the Network Analyst extension license
arcpy.CheckOutExtension("Network")

# working folder for input facilities and outputs
wf = r'C:\Testing\ConsVisionRecMod\Subsets'

# output name for a service area run
outNALayerName = "ServAreaTrailheadsNoOverlap30"

# definition query for facilities
defQuery = '"src_table" = \'trailheads\''

# environment settings
env.workspace = wf + os.sep + 'RCL_Network.gdb'
env.overwriteOutput = True

# output files/folders (creates new folder with outputNALayerName in outputFolder)
outputFolder = wf + "/na_final/output"
newdir = outputFolder + "/" + outNALayerName
if not os.path.exists(newdir):
    os.makedirs(newdir)
else: 
    print('Folder ' + outNALayerName + ' already exists in the output folder.')
    exit()

outputFolder = newdir
outLayerFile = outputFolder + "/" + outNALayerName + ".lyr"

# name of network dataset
inNetworkDataset = "RCL_ND"

# input facilities shapefile
inFacilities = wf + os.sep + 'all_facil_subset10.shp'

# definition query for facilities layer
arcpy.MakeFeatureLayer_management(inFacilities,"fac")
fac_lyr = arcpy.mapping.Layer("fac")
fac_lyr.definitionQuery = defQuery

# how many sources?
print 'Facilities count: ' + str(arcpy.GetCount_management("fac"))

# some options for making the service area layer; change others directly in function calls
impedanceAttribute = "DriveTime"
to_from = "TRAVEL_TO" #["TRAVEL_TO"|"TRAVEL_FROM"]
serviceAreaBreaks = "30"
poly_type = "DETAILED_POLYS" #["SIMPLE_POLYS"|"NO_POLYS"]
merge_polys = "MERGE" #["NO_MERGE"|"NO_OVERLAP"|"MERGE"]

# distance within roads to search for facilities
searchTolerance = 500
# add new features or clear 
appendclear = "CLEAR" # ["APPEND"/"CLEAR"]

# Make service area layer 
outNALayer = arcpy.na.MakeServiceAreaLayer(in_network_dataset=inNetworkDataset,
      out_network_analysis_layer=outNALayerName,
      impedance_attribute=impedanceAttribute,
      travel_from_to=to_from, 
      default_break_values=serviceAreaBreaks,
      polygon_type=poly_type,
      merge=merge_polys, 
      nesting_type="RINGS", 
      line_type="TRUE_LINES",
      overlap="NON_OVERLAP", 
      split="SPLIT",
      # excluded_source_name="[]",
      accumulate_attribute_name="DriveTime",
      UTurn_policy="ALLOW_UTURNS",
      # restriction_attribute_name="[]",
      polygon_trim="NO_TRIM_POLYS",
      poly_trim_value=100,
      lines_source_fields="NO_LINES_SOURCE_FIELDS",
      hierarchy = "#") # only use if hierarchy defined in dataset
      # time_of_day="#"
      # )

#Get the layer object from the result object. The service area layer can 
#now be referenced using the layer object.
outNALayer = outNALayer.getOutput(0)

#Get the names of all the sublayers within the service area layer.
subLayerNames = arcpy.na.GetNAClassNames(outNALayer)
#Stores the layer names that we will use later
facilitiesLayerName = subLayerNames["Facilities"]

# add facilities to network analysis layer
arcpy.na.AddLocations(in_network_analysis_layer=outNALayer,
      sub_layer=facilitiesLayerName,
      in_table="fac",
      # field_mappings="",
      search_tolerance=searchTolerance,
      sort_field="",
      search_criteria=[["Roads","SHAPE"]],
      match_type="MATCH_TO_CLOSEST",
      append=appendclear,
      snap_to_position_along_network="NO_SNAP",
      snap_offset=0,
      exclude_restricted_elements="INCLUDE")
      # search_query=""
      # )
  
#Solve the service area layer
# print 'Starting solve at ' + str(time.ctime())
t1 = datetime.now()
printMsg('Starting solve at %s.' % str(t1))
SolveResult = arcpy.na.Solve(outNALayer,
               ignore_invalids="SKIP",
               terminate_on_solve_error="TERMINATE",
               simplification_tolerance="100 meters")
t2 = datetime.now()
printMsg('Finished solve at %s.' % str(t2))
try:
   s = SolveResult.getOutput(1)
   printMsg('Solve result: %s' % str(s))
except:
   pass
printMsg('Warnings: %s' % arcpy.GetMessages(1))
printMsg('Errors: %s' % arcpy.GetMessages(2))

# print 'Finished solve at ' + str(time.ctime())
deltaString = GetElapsedTime(t1, t2)
printMsg('Elapsed time for solve: %s.' % deltaString)

# To save the solved layer as a layer file on disk with relative paths
printMsg('Exporting solved layer to disk...')
t3 = datetime.now()
arcpy.management.SaveToLayerFile(outNALayer,outLayerFile,"RELATIVE")
t4 = datetime.now()
deltaString = GetElapsedTime(t3, t4)
printMsg('Finished export at %s.' % str(t4))
printMsg('Elapsed time for export: %s.' % deltaString)

# Save the facilities, lines, and polygons features to disk
printMsg('Copying features to disk...')
arcpy.CopyFeatures_management(in_features=arcpy.mapping.ListLayers(outNALayer, 'Facilities')[0],out_feature_class=outputFolder + "/" + outNALayerName + "_Facilities.shp")
arcpy.CopyFeatures_management(in_features=arcpy.mapping.ListLayers(outNALayer, 'Lines')[0],out_feature_class=outputFolder + "/" + outNALayerName + "_Lines.shp")
arcpy.CopyFeatures_management(in_features=arcpy.mapping.ListLayers(outNALayer, 'Polygons')[0],out_feature_class=outputFolder + "/" + outNALayerName + "_Polygons.shp")

#print 'Finished exporting all features at ' + str(time.ctime())
