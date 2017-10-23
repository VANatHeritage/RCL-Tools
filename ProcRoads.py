# ---------------------------------------------------------------------------
# ProcRoads.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creator: Kirsten R. Hazler
# Creation Date: 2017-10-17 
# Last Edit: 2017-10-23

# Summary:
# A collection of functions for processing roads data and using them for various analyses.

# Usage tips:
# Use the following function sequence to do a travel time analysis based on a cost surface (raster):
# - PrepRoadsVA
# - PrepRoadsTIGER
# - MergeRoads
# - 

# ---------------------------------------------------------------------------

# Import modules
import arcpy, os
scratchGDB = arcpy.env.scratchGDB
arcpy.env.overwriteOutput = True

def printMsg(msg):
   arcpy.AddMessage(msg)
   print msg
   return

def ProjectToMatch (fcTarget, csTemplate):
   """Project a target feature class to match the coordinate system of a template dataset"""
   # Get the spatial reference of your target and template feature classes
   srTarget = arcpy.Describe(fcTarget).spatialReference # This yields an object, not a string
   srTemplate = arcpy.Describe(csTemplate).spatialReference 

   # Get the geographic coordinate system of your target and template feature classes
   gcsTarget = srTarget.GCS # This yields an object, not a string
   gcsTemplate = srTemplate.GCS

   # Compare coordinate systems and decide what to do from there. 
   if srTarget.Name == srTemplate.Name:
      printMsg('Coordinate systems match; no need to do anything.')
      return fcTarget
   else:
      printMsg('Coordinate systems do not match; proceeding with re-projection.')
      if fcTarget[-3:] == 'shp':
         fcTarget_prj = fcTarget[:-4] + "_prj.shp"
      else:
         fcTarget_prj = fcTarget + "_prj"
      if gcsTarget.Name == gcsTemplate.Name:
         printMsg('Datums are the same; no geographic transformation needed.')
         arcpy.Project_management (fcTarget, fcTarget_prj, srTemplate)
      else:
         printMsg('Datums do not match; re-projecting with geographic transformation')
         # Get the list of applicable geographic transformations
         # This is a stupid long list
         transList = arcpy.ListTransformations(srTarget,srTemplate) 
         # Extract the first item in the list, assumed the appropriate one to use
         geoTrans = transList[0]
         # Now perform reprojection with geographic transformation
         arcpy.Project_management (fcTarget, fcTarget_prj, srTemplate, geoTrans)
      printMsg("Re-projected data is %s." % fcTarget_prj)
      return fcTarget_prj
   
def PrepRoadsVA(inRCL):
   """Prepares a Virginia Road Centerlines (RCL) feature class to be used for travel time analysis. This function assumes that there already exist some specific fields, including:
 - LOCAL_SPEED_MPH 
 - MTFCC
 - SEGMENT_EXISTS
 - RCL_ID
 If any of the assumed fields do not exist, have been renamed, or are in the wrong format, the script will fail.
 
This function was adapted from a ModelBuilder tool created by Kirsten R. Hazler and Tracy Tien for the Development Vulnerability Model (2015)"""
 
   # Process: Create "SPEED_cmnt" field.
   # This field can be used to store QC comments related to speed, if needed.
   printMsg("Adding 'SPEED_cmt' field...")
   arcpy.AddField_management (inRCL, "SPEED_cmnt", "TEXT", "", "", 50)
   
   # Process: Create and calculate "FlgFld"
   # This field is used to flag records with suspect LOCAL_SPEED_MPH values
   # 1 = Flagged: need to update speed based on MTFCC field
   # -1 = Flagged: need to set speed to 3 (walking pace)
   # 0 = Unflagged: record assumed to be fine as is
   printMsg("Adding and populating 'FlgFld' field...")
   arcpy.AddField_management(inRCL, "FlgFld", "LONG")
   codeblock = """def Flg (exists, speed):
      if exists == "Y":
         if (speed == 0):
            return 1
         elif (speed % 5 != 0):
            return 1
         else:
            return 0
      else:
         return -1"""
   expression = "Flg(!SEGMENT_EXISTS!,!LOCAL_SPEED_MPH!)"
   arcpy.CalculateField_management(inRCL, "FlgFld", expression, "PYTHON_9.3", codeblock)

   # Process: Create and calculate "SPEED_upd" field.
   # This field is used to store speed values to be used in later processing. It allows for altering speed values according to QC criteria, without altering original values in the  existing "LOCAL_SPEED_MPH" field. 
   printMsg("Adding and populating 'SPEED_upd' field...")
   arcpy.AddField_management(inRCL, "SPEED_upd", "LONG")
   codeblock = """def SpdUpd(flgfld, mtfcc, speed):
      if flgfld == 1:
         if mtfcc == 'S1100':
            return 55
         elif mtfcc in ['S1200', 'S1300', 'S1640']:
            return 45
         elif mtfcc == 'S1630':
            return 30
         elif mtfcc in ['C3061', 'C3062', 'S1400', 'S1740']:
            return 25
         elif mtfcc in ['S1500', 'S1730', 'S1780']:
            return 15
         elif mtfcc == 'S1820':
            return 10
         else:  
            return 3
      elif flgfld == -1:
         return 3
      else:
         return speed"""
   expression = "SpdUpd(!FlgFld!, !MTFCC!, !LOCAL_SPEED_MPH!)"
   arcpy.CalculateField_management(inRCL, "SPEED_upd", expression, "PYTHON_9.3",codeblock)

   # Process: Create and calculate "TravTime" field
   # This field is used to store the travel time, in minutes, required to travel 1 meter, based on the road speed designation.
   printMsg("Adding and populating 'TravTime' field...")
   arcpy.AddField_management(inRCL, "TravTime", "DOUBLE")
   expression = "0.037/ !SPEED_upd!"
   arcpy.CalculateField_management(inRCL, "TravTime", expression, "PYTHON_9.3")

   # Process: Create and calculate the "RmpHwy" field
   # This field indicates if a road is a limited access highway (2), a ramp (1), or any other road type (0)
   printMsg("Adding and populating 'RmpHwy' field...")
   arcpy.AddField_management(inRCL, "RmpHwy", "SHORT")
   codeblock = """def RmpHwy (mtfcc):
      if mtfcc in ("S1100", "S1100HOV"):
         return 2
      elif mtfcc == "S1630":
         return 1
      else:
         return 0"""
   expression = "RmpHwy(!MTFCC!)"
   arcpy.CalculateField_management(inRCL, "RmpHwy", expression, "PYTHON_9.3", codeblock)

   # Process: Create and calculate the "UniqueID" field
   # This field stores a unique ID with a state prefix for ease of merging data from different states.
   printMsg("Adding and populating 'UniqueID' field...")
   arcpy.AddField_management(inRCL, "UniqueID", "TEXT", "", "", "16")
   expression = "'VA_' +  str(int(!RCL_ID!))"
   arcpy.CalculateField_management(inRCL, "UniqueID", expression, "PYTHON_9.3")
   
   printMsg("Finished prepping %s." % inRCL)
   return inRCL

def PrepRoadsTIGER(inList, inBnd, outRoads):
   """Prepares a set of TIGER line shapefiles representing roads to be used for travel time analysis. This function assumes that there already exist some specific fields, including:
- MTFCC
- RTTYP
If any of the assumed fields do not exist, have been renamed, or are in the wrong format, the script will fail.
 
This function was adapted from a ModelBuilder tool created by Kirsten R. Hazler and Tracy Tien for the Development Vulnerability Model (2015)"""

   # Process: Merge all roads
   printMsg("Merging TIGER roads datasets...")
   mergeRds = scratchGDB + os.sep + "mergeRds"
   arcpy.Merge_management(inList, mergeRds)
   
   # Process: Project the merged roads to match the input boundary
   printMsg("Re-projecting roads to match boundary...")
   prjRds = ProjectToMatch(mergeRds, inBnd)
   
   # Process: Clip to boundary
   printMsg("Clipping roads to boundary...")
   arcpy.Clip_analysis(prjRds, inBnd, outRoads)
   
   # Process: Create and calculate "SPEED_upd" field.
   # This field is used to store speed values to be used in later processing. It allows for altering speed values according to QC criteria, without altering original values in the  existing "LOCAL_SPEED_MPH" field. 
   printMsg("Adding and populating 'SPEED_upd' field...")
   arcpy.AddField_management(outRoads, "Speed_upd", "LONG")
   codeblock = """def Speed(mtfcc, rttyp):
   if mtfcc == 'S1100' and rttyp == 'I':
      return 65
   elif mtfcc == 'S1100' and rttyp != 'I':
      return 55
   elif mtfcc in ['S1200', 'S1300', 'S1640']:
      return 45
   elif mtfcc == 'S1630':
      return 30
   elif mtfcc in ['C3061', 'C3062', 'S1400', 'S1740']:
      return 25
   elif mtfcc in ['S1500', 'S1730', 'S1780']:
      return 15
   elif mtfcc == 'S1820':
      return 10
   else:  
      return 3"""
   expression = "Speed(!MTFCC!,!RTTYP! )"
   arcpy.CalculateField_management(outRoads, "SPEED_upd", expression, "PYTHON_9.3",codeblock)

   # Process: Create and calculate "TravTime" field
   # This field is used to store the travel time, in minutes, required to travel 1 meter, based on the road speed designation.
   printMsg("Adding and populating 'TravTime' field...")
   arcpy.AddField_management(outRoads, "TravTime", "DOUBLE")
   expression = "0.037/ !SPEED_upd!"
   arcpy.CalculateField_management(outRoads, "TravTime", expression, "PYTHON_9.3")
   
   # Process: Create and calculate the "RmpHwy" field
   # This field indicates if a road is a limited access highway (2), a ramp (1), or any other road type (0)
   printMsg("Adding and populating 'RmpHwy' field...")
   arcpy.AddField_management(outRoads, "RmpHwy", "SHORT")
   codeblock = """def RmpHwy (mtfcc):
      if mtfcc in ("S1100", "S1100HOV"):
         return 2
      elif mtfcc == "S1630":
         return 1
      else:
         return 0"""
   expression = "RmpHwy(!MTFCC!)"
   arcpy.CalculateField_management(outRoads, "RmpHwy", expression, "PYTHON_9.3", codeblock)
   
   # Process: Create and calculate the "UniqueID" field
   # This field stores a unique ID with a state prefix for ease of merging data from different states.
   printMsg("Adding and populating 'UniqueID' field...")
   arcpy.AddField_management(outRoads, "UniqueID", "TEXT", "", "", "16")
   expression = "'TL_' + !LINEARID!"
   arcpy.CalculateField_management(outRoads, "UniqueID", expression, "PYTHON_9.3")
   
   printMsg("Finished prepping %s." % outRoads)
   return outRoads

def MergeRoads(inList, outRoads):
   """Merges VA RCL data with TIGER roads data, retaining only specified fields needed for travel time analysis in the output. 

   Important assumptions:
   - The input VA RCL data are the output of running the PrepRoadsVA function
   - The input TIGER roads data are the output of running the PrepRoadsTIGER function.
   - The above two inputs are in the same coordinate system.
   
This function was adapted from a ModelBuilder tool created by Kirsten R. Hazler and Tracy Tien for the Development Vulnerability Model (2015)"""
   
   # If input inList is actually a string delimited with semi-colons, need to parse and turn it into a list.
   if isinstance(inList, str):
      inList = inList.split(';')
      printMsg("String parsed.")
   
   # Create the field mapping
   printMsg("Creating field mappings...")
   inFlds = ['TravTime', 'UniqueID', 'RmpHwy', 'Speed_upd']
   fldMappings = arcpy.FieldMappings()
   for fld in inFlds:
      fldMap = arcpy.FieldMap()
      for tab in inList:
         fldMap.addInputField(tab, fld)
      fldMap.outputField.name = fld
      fldMappings.addFieldMap(fldMap)
   
   # Merge datasets
   printMsg("Merging datasets...")
   arcpy.Merge_management (inList, outRoads, fldMappings)
   
   printMsg("Mission accomplished.")
   return outRoads

############################################################################

# Use the section below to enable a function (or sequence of functions) to be run directly from this free-standing script (i.e., not as an ArcGIS toolbox tool)

def main():
   # Set up your variables here
   rcl = r'C:\Testing\RCL_Test.gdb\RCL2017Q3_Subset'
   tiger = r'C:\Testing\RCL_Test.gdb\tlRoads_prj'
   inList = [rcl, tiger]
   outRoads = r'C:\Testing\RCL_Test.gdb\mergeRoads'
   
   # Include the desired function run statement(s) below
   MergeRoads(inList, outRoads)
   
   # End of user input
   
if __name__ == '__main__':
   main()
