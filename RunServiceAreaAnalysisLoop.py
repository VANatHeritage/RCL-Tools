# -*- coding: utf-8 -*-
"""
Run network analyst tools via command line.

Assumes an already-created network dataset. (See NetworkAnalyst-Setup.txt for instructions)

Created on Mon Oct 23 11:44:44 2017

@author: David Bucklin and Kirsten Hazler
Last edit: 2017-11-13 (krh)
"""


# Import Helper module and functions
import Helper
from Helper import *
from arcpy import env

# Check out the Network Analyst extension license
arcpy.CheckOutExtension("Network")

def RecServiceAreas(inNetworkDataset, inFacilities, fld_facID, fld_grpID, outDirectory, outNALayerName):
   '''Creates a set of Service Areas based on 30-minute drive time to recreation facilities.
   inNetworkDataset = The network dataset used to determine drive times
   inFacilities = The point feature class representing access points to recreational opportunities
   fld_facID = The field in inFacilities containing a unique ID for each point
   fld_grpID = The field in inFacilities used to identify grouped clusters of recreational opportunities
   outDirectory = The directory in which outputs will be stored
   outNALayerName = The name of the output Network Analyst layer'''

   # Options for creating Service Area analysis layer - these may need to be tweaked in future
   impedanceAttribute = "DriveTime"
   to_from = "TRAVEL_TO" #["TRAVEL_TO"|"TRAVEL_FROM"]
   serviceAreaBreaks = "30"
   poly_type = "DETAILED_POLYS" #["SIMPLE_POLYS"|"NO_POLYS"]
   merge_polys = "MERGE" #["NO_MERGE"|"NO_OVERLAP"|"MERGE"]
   lines = "TRUE_LINES" #["NO_LINES"|"TRUE_LINES"|"TRUE_LINES_WITH_MEASURES"]
   merge_lines = "NON_OVERLAP" #["OVERLAP"|"NON_OVERLAP"]
   split_lines = "SPLIT" #["SPLIT"|"NO_SPLIT"]

   # Options for adding facilities to Service Area analysis layer - these may need to be tweaked in future
   searchTolerance = 500 # How far can facility be from network to be included in analysis?
   appendclear = "CLEAR" # ["APPEND"/"CLEAR"] # Add to existing features (append) or overwrite with new features (clear)?

   # Initialize variables and settings for analysis
   # Output files/folders (creates new folder with outputNALayerName in outputFolder)
   outputFolder = outDirectory + os. sep + "na_ServArea" 
   newdir = outputFolder + os.sep + outNALayerName
   if not os.path.exists(newdir):
       os.makedirs(newdir)
   else: 
       print('Folder ' + outNALayerName + ' already exists in the output folder.')
       exit()

   outputFolder = newdir
   outLayerFile = outputFolder + os.sep + outNALayerName + ".lyr"
   outGDB = outputFolder + os.sep + outNALayerName + ".gdb"
   arcpy.CreateFileGDB_management(outputFolder, outNALayerName + ".gdb")

   # Field map for facilities (to assign unique ID from source data)
   fldMap = "Name %s #" % fld_facID

   # How many facilities?
   num_fac = countFeatures(inFacilities)
   printMsg('Facilities count: %s' % str(num_fac))

   # Start the timer
   t0 = datetime.now()
   printMsg('Processing started: %s' % str(t0))

   # Make service area layer 
   outNALayer = arcpy.na.MakeServiceAreaLayer(in_network_dataset=inNetworkDataset,
         out_network_analysis_layer=outNALayerName,
         impedance_attribute=impedanceAttribute,
         travel_from_to=to_from, 
         default_break_values=serviceAreaBreaks,
         polygon_type=poly_type,
         merge=merge_polys, 
         nesting_type="RINGS", 
         line_type=lines,
         overlap=merge_lines, 
         split=split_lines,
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

   #Get the layer object from the result object. The service area layer can now be referenced using the layer object.
   outNALayer = outNALayer.getOutput(0)

   #Get the names of all the sublayers within the service area layer.
   subLayerNames = arcpy.na.GetNAClassNames(outNALayer)
   #Stores the layer names that we will use later
   facilitiesLayerName = subLayerNames["Facilities"]

   # Set up a loop to process one facility at a time
   # Facilities with the same unique ID are processed together as a group.

   # Get the set of unique IDs, and count
   id_List = unique_values(inFacilities, fld_grpID)
   id_Count = len(id_List)
   printMsg('There are %s facility groups to process' % str(id_Count))

   # Initialize counter
   myIndex = 1 

   # Initialize empty list to store IDs of facility groups that fail to get processed
   myFailList = []

   # Loop through the individual facilities
   for id in id_List:
      printMsg("\nWorking on facility group %s, with ID = %s" %(myIndex, str(id)))

      try: 
         # Select the facilities
         arcpy.env.workspace = outGDB # Don't use in_memory or scratchGDB to avoid write conflicts
         if isinstance(id, str):
            selQry = fld_grpID + " = '%s'" % id 
         else:
            selQry = fld_grpID + " = %s" % str(id) 
         arcpy.Select_analysis (inFacilities, "tmp_fac", selQry)
         num_pts = countFeatures("tmp_fac")
         printMsg('There are %s location points in this group.' % str(num_pts))
         
         # add facilities to network analysis layer
         arcpy.na.AddLocations(in_network_analysis_layer=outNALayer,
               sub_layer = facilitiesLayerName,
               in_table = "tmp_fac",
               field_mappings = fldMap,
               search_tolerance = searchTolerance,
               sort_field = "",
               search_criteria = [["Roads","SHAPE"]],
               match_type = "MATCH_TO_CLOSEST",
               append = appendclear,
               snap_to_position_along_network = "NO_SNAP",
               snap_offset = 0,
               exclude_restricted_elements = "INCLUDE")
               # search_query=""
               # )
     
         #Solve the service area layer
         t1 = datetime.now()
         printMsg('Solving...')
         arcpy.na.Solve(outNALayer,
            ignore_invalids="SKIP",
            terminate_on_solve_error="CONTINUE")
         t2 = datetime.now()
         
         # Messaging
         if len(arcpy.GetMessages(1)) > 0:
            printMsg('Warnings: %s' % arcpy.GetMessages(1))

         deltaString = GetElapsedTime(t1, t2)
         printMsg('Solve complete. Elapsed time: %s.' % deltaString)

         # Save the facilities, lines, and polygons features to disk
         arcpy.env.workspace = outGDB
         printMsg('Copying output features to disk...')
         arcpy.CopyFeatures_management(in_features=arcpy.mapping.ListLayers(outNALayer, 'Facilities')[0],out_feature_class="Facilities_" + str(id))
         arcpy.CopyFeatures_management(in_features=arcpy.mapping.ListLayers(outNALayer, 'Lines')[0],out_feature_class="Lines_" + str(id))
         arcpy.CopyFeatures_management(in_features=arcpy.mapping.ListLayers(outNALayer, 'Polygons')[0],out_feature_class="Polygons_" + str(id))
         t3 = datetime.now()
         printMsg('Finished copy at %s. Process complete.' % str(t3))
      except:
         printMsg('Failed for %s' % str(id))
         tbackInLoop()
         myFailList.append(id)
      finally:
         myIndex += 1

   if len(myFailList) > 0:
      num_Fails = len(myFailList)
      printMsg('\nProcess complete, but the following %s facility groups failed: %s.' % (str(num_Fails), str(myFailList)))

   # End the timer
   t4 = datetime.now()
   deltaString = GetElapsedTime(t0, t4)
   printMsg('All features completed: %s' % str(t4))
   printMsg('Total processing time: %s.' % deltaString)



##################################################################################################################
# Use the main function below to run a function directly from Python IDE or command line with hard-coded variables

def main():
   # Set up variables
   inNetworkDataset = r'E:\ConsVision_RecMod\RCL_Network.gdb\RCL\RCL_ND'
   inFacilities = r'E:\ConsVision_RecMod\Terrestrial\Input\TerrestrialFacilities2501_3000.shp'
   fld_facID = 'FID'
   fld_grpID = 'grpID_500m'
   outDirectory = r'E:\ConsVision_RecMod\Terrestrial\Output2501_3000'
   outNALayerName = "terrestrial"
   
   # Specify function to run
   RecServiceAreas(inNetworkDataset, inFacilities, fld_facID, fld_grpID, outDirectory, outNALayerName)

if __name__ == '__main__':
   main()
