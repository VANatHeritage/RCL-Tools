# -*- coding: utf-8 -*-
"""
Run network analyst tools via command line.

Assumes an already-created network dataset. (See NetworkAnalyst-Setup.txt for instructions)

Created on Mon Oct 23 11:44:44 2017

@author: David Bucklin
"""

import arcpy
import time
import os
from arcpy import env

# Check out the Network Analyst extension license
arcpy.CheckOutExtension("Network")

# working folder for input facilities and outputs
wf = "C:/David/projects/rec_model"

# output name for a service area run
outNALayerName = "ServAreaAllBWTSites"

# definition query for facilities
defQuery = '"src_table" = \'bwt_sites\''

# environment settings
env.workspace = wf + '/na_final/RCL_Network.gdb'
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
inFacilities = wf + "/model_input_recfacilities/all_facil.shp"

# definition query for facilities layer
arcpy.MakeFeatureLayer_management(inFacilities,"fac")
fac_lyr = arcpy.mapping.Layer("fac")
fac_lyr.definitionQuery = defQuery

# how many sources?
print 'Facilities count: ' + str(arcpy.GetCount_management("fac"))

# some options for making the service area layer; change others directly in function calls
impedanceAttribute = "DriveTime"
to_from = "TRAVEL_TO" #["TRAVEL_TO"|"TRAVEL_FROM"]
serviceAreaBreaks = "10 30 60 120"
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

#Get the layer object from the result object. The closest facility layer can 
#now be referenced using the layer object.
outNALayer = outNALayer.getOutput(0)

#Get the names of all the sublayers within the closest facility layer.
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
  
#Solve the closest facility layer
print 'Starting solve at ' + str(time.ctime())
arcpy.na.Solve(outNALayer,
               ignore_invalids="SKIP",
               terminate_on_solve_error="CONTINUE",
               simplification_tolerance="100 meters")
print 'Finished solve at ' + str(time.ctime())

# To save the solved layer as a layer file on disk with relative paths
# arcpy.management.SaveToLayerFile(outNALayer,outLayerFile,"RELATIVE")
# print 'Exported NA layer at ' + str(time.ctime())

# Save the facilities, lines, and polygons features to disk
arcpy.CopyFeatures_management(in_features=arcpy.mapping.ListLayers(outNALayer, 'Facilities')[0],out_feature_class=outputFolder + "/" + outNALayerName + "_Facilites.shp")
arcpy.CopyFeatures_management(in_features=arcpy.mapping.ListLayers(outNALayer, 'Lines')[0],out_feature_class=outputFolder + "/" + outNALayerName + "_Lines.shp")
arcpy.CopyFeatures_management(in_features=arcpy.mapping.ListLayers(outNALayer, 'Polygons')[0],out_feature_class=outputFolder + "/" + outNALayerName + "_Polygons.shp")
print 'Finished exporting all features at ' + str(time.ctime())