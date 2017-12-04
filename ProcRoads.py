# ---------------------------------------------------------------------------
# ProcRoads.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creator: Kirsten R. Hazler
# Creation Date: 2017-10-17 
# Last Edit: 2017-12-4

# Summary:
# A collection of functions for processing roads data to prepare them as inputs for various analyses.

# Usage tips:
# Use the following function sequence to prepare roads for travel time analysis:
# - PrepRoadsVA_tt (to prepare Virginia RCL data for travel time analysis)
# - PrepRoadsTIGER_tt (to prepare TIGER roads data from adjacent states for travel time analysis)
# - MergeRoads_tt (to merge the RCL and TIGER datasets into a seamless dataset, with a limited set of critical fields in the output)
# 
# The following functions are helper functions called by the above functions:
# - printMsg (shortcut for informative progress messaging)
# - ProjectToMatch (to project one dataset to match the coordinate system of another)
# ---------------------------------------------------------------------------

# Import Helper module and functions
import Helper
from Helper import *

def PrepRoadsVA_tt(inRCL):
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

def PrepRoadsTIGER_tt(inList, inBnd, outRoads):
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

def MergeRoads_tt(inList, outRoads):
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

def ExtractRCL_su(inRCL, outRCL):
   """Extracts the relevant features from the Virginia Road Centerlines (RCL) feature class to be used for creating road surfaces. Omits segments based on data in the MTFCC and SEGMENT_TYPE fields. If any of the assumed fields do not exist, have been renamed, or are in the wrong format, the script will fail.
   
Excludes the following MTFCC types:
- S1730: Alleys
- S1780: Parking Lot Roads
- S9999: Driveways
- S1710: Walkways/Pedestrian Trails
- S1720: Stairways
- S1740: Service Vehicle Private Drves
- S1820: Bike Paths or Trails
- S1830: Bridle Paths
- S1500: 4WD Vehicular Trails

Excludes the following SEGMENT_TYPE values:
- 2: Bridge/Overpass
- 10: Tunnel/Underpass
- 50: Ferry Crossing

This function was adapted from a ModelBuilder toolbox created by Kirsten R. Hazler and Peter Mitchell"""

   where_clause = "MTFCC NOT IN ( 'S1730', 'S1780', 'S9999', 'S1710', 'S1720', 'S1740', 'S1820', 'S1830', 'S1500' ) AND SEGMENT_TYPE NOT IN (2, 10, 50)"
   arcpy.Select_analysis (inRCL, outRCL, where_clause)
   
   return outRCL
   
def PrepRoadsVA_su(inRCL, inVDOT):
   """Adds fields to road centerlines data, necessary for generating road surfaces.

This function was adapted from a ModelBuilder toolbox created by Kirsten R. Hazler and Peter Mitchell"""

   # Define a class to store field information
   class Field:
      def __init__(self, Name = '', Type = '', Length = ''):
         self.Name = Name
         self.Type = Type
         self.Length = Length
   
   # Specify fields to add
   # All field names have the prefix "NH" to indicate they are fields added by Natural Heritage   
   fldBuffM = Field('NH_BUFF_M', 'DOUBLE', '') # Buffer width in meters. This field is calculated automatically based on information in other fields.
   fldFlag = Field('NH_SURFWIDTH_FLAG', 'SHORT', '') # Flag for surface widths needing attention. This field is automatically calculated initially, but can be manually changed as needed.
   fldComments = Field('NH_COMMENTS', 'TEXT', 500) # QC/processing/editing comments. This field is for automatic or manual data entry.
   fldBuffFt = Field('NH_BUFF_FT', 'DOUBLE', '') # Buffer width in feet. This field is for manual data entry, used to override buffer width values that would otherwise be calculated.
   addFields = [fldBuffM, fldFlag, fldComments, fldBuffFt]
   
   # Add the fields
   for f in addFields:
      arcpy.AddField_management (inRCL, f.Name, f.Type, '', '', f.Length)
      printMsg('Field %s added.' % f.Name)
   
   # Join fields from VDOT table
   vdotFields = ['VDOT_RTE_TYPE_CD', 'VDOT_SURFACE_WIDTH_MSR', 'VDOT_TRAFFIC_AADT_NBR']
   JoinFields(inRCL, 'VDOT_EDGE_ID', inVDOT, 'VDOT_EDGE_ID', vdotFields)
   
   # Calculate flag field
   expression = "calcFlagFld(!VDOT_SURFACE_WIDTH_MSR!, !MTFCC!, !VDOT_RTE_TYPE_CD!)"
   code_block = '''def calcFlagFld(width, mtfcc, routeType):
      if width == None or width == 0: 
         return -1
      elif width < 24 and (mtfcc in ('S1100', 'S1100HOV') or routeType == 'IS'):
         return -1
      elif width < 22 and (mtfcc == 'S1200PRI' or routeType in ('SR', 'US')):
         return -1
      elif width < 20 and mtfcc == 'S1200LOC':
         return -1
      elif width < 18:
         return -1
      else: 
         return 0'''
   arcpy.CalculateField_management (inRCL, fldFlag.Name, expression, 'PYTHON', code_block)
   
   return inRCL
   
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