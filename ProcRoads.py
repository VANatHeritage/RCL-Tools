# ---------------------------------------------------------------------------
# ProcRoads.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creator: Kirsten R. Hazler
# Creation Date: 2017-10-17 
# Last Edit: 2017-12-06

# Summary:
# A collection of functions for processing roads data to prepare them as inputs for various analyses.

# Usage tips:
# Use the following function sequence to prepare roads for travel time analysis:
# - PrepRoadsVA_tt (to prepare Virginia RCL data for travel time analysis)
# - PrepRoadsTIGER_tt (to prepare TIGER roads data from adjacent states for travel time analysis)
# - MergeRoads_tt (to merge the RCL and TIGER datasets into a seamless dataset, with a limited set of critical fields in the output)
# 
# Use the following function sequence to generate road surfaces from road centerlines:
# - ExtractRCL_su (to extract the relevant road segments for which you want surfaces generated)
# - PrepRoadsVA_su (to add necessary fields to roads data)
# - AssignBuffer_su (to assign road surface buffer widths)
# - CreateRoadSurfaces_su (to generate road surfaces based on the specified buffer widths)
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
   printMsg('Extracting relevant road segments and saving...')
   arcpy.Select_analysis (inRCL, outRCL, where_clause)
   printMsg('Roads exracted.')
   
   return outRCL
   
def PrepRoadsVA_su(inRCL, inVDOT):
   """Adds fields to road centerlines data, necessary for generating road surfaces.
- inRCL = road centerlines feature class
- inVDOT = VDOT attribute table (from same geodatabase as inRCL)

This function was adapted from a ModelBuilder toolbox created by Kirsten R. Hazler and Peter Mitchell"""

   # Define a class to store field information
   class Field:
      def __init__(self, Name = '', Type = '', Length = ''):
         self.Name = Name
         self.Type = Type
         self.Length = Length
   
   # Specify fields to add
   printMsg('Setting field definitions')
   # All field names have the prefix "NH" to indicate they are fields added by Natural Heritage   
   fldBuffM = Field('NH_BUFF_M', 'DOUBLE', '') # Buffer width in meters. This field is calculated automatically based on information in other fields.
   fldFlag = Field('NH_SURFWIDTH_FLAG', 'SHORT', '') # Flag for surface widths needing attention. This field is automatically calculated initially, but can be manually changed as needed (-1 = needs attention; 0 = OK; 1 = record reviewed and amended)
   fldComments = Field('NH_COMMENTS', 'TEXT', 500) # QC/processing/editing comments. This field is for automatic or manual data entry.
   fldBuffFt = Field('NH_BUFF_FT', 'DOUBLE', '') # Buffer width in feet. This field is for manual data entry, used to override buffer width values that would otherwise be calculated.
   fldConSite = Field('NH_CONSITE', 'SHORT', '') # Field to indicate if segment relevant to ConSite delineation (1 = close enough to features to be relevant; 0 = not relevant)
   addFields = [fldBuffM, fldFlag, fldComments, fldBuffFt, fldConSite]
   
   # Add the fields
   printMsg('Adding fields...')
   for f in addFields:
      arcpy.AddField_management (inRCL, f.Name, f.Type, '', '', f.Length)
      printMsg('Field %s added.' % f.Name)
   
   # Join fields from VDOT table
   printMsg('Joining attributes from VDOT table. This could take hours...')
   vdotFields = ['VDOT_RTE_TYPE_CD', 'VDOT_SURFACE_WIDTH_MSR', 'VDOT_TRAFFIC_AADT_NBR']
   #JoinFields(inRCL, 'VDOT_EDGE_ID', inVDOT, 'VDOT_EDGE_ID', vdotFields)
   #My JoinFields function failed to finish after ~24 hours, so I reverted to using arcpy.JoinField.
   arcpy.JoinField_management(inRCL, 'VDOT_EDGE_ID', inVDOT, 'VDOT_EDGE_ID', vdotFields)
   
   # Calculate flag field
   printMsg('Calculating flag field')
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
   arcpy.CalculateField_management (inRCL, 'NH_SURFWIDTH_FLAG', expression, 'PYTHON', code_block)
   
   printMsg('Roads attribute table updated.')
   
   return inRCL
   
def AssignBuffer_su(inRCL):
   """Assign road surface buffer width based on other attribute fields.

The codeblock used to assign buffer widths is based on information here:
https://nacto.org/docs/usdg/geometric_design_highways_and_streets_aashto.pdf. 
See the various tables (labeled "Exhibit x-x) showing the minimum width of traveled way and shoulders for different road types and capacities. Relevant pages: 388,429,452, 476-478, 507-509.

This function was adapted from a ModelBuilder toolbox created by Kirsten R. Hazler and Peter Mitchell"""

   # Get formatted time stamp and auto-generated comment
   ts = datetime.now()
   stamp = '%s-%s-%s %s:%s' % (ts.year, str(ts.month).zfill(2), str(ts.day).zfill(2), str(ts.hour).zfill(2), str(ts.minute).zfill(2))
   comment = "Buffer distance auto-calculated %s" % stamp
   
   # Calculate fields
   printMsg('Calculating buffer widths. This could take awhile...')
   expression = "calculateBuffer(!NH_SURFWIDTH_FLAG!, !NH_BUFF_FT!, !VDOT_SURFACE_WIDTH_MSR!, !LOCAL_SPEED_MPH!, !VDOT_TRAFFIC_AADT_NBR!, !MTFCC!, !VDOT_RTE_TYPE_CD!)"
   code_block = """def calculateBuffer(flag, override, surfwidth, speed, vehicles, mtfcc, routeType):
      convFactor = 0.1524 # This converts feet to meters, then divides by 2 to get buffer width
      
      if override == None:
      # If no manual value has been entered, assign defaults based on road type, speed, and traffic volume
         if speed == None or speed == 0:
            speed = 25
            
         if vehicles == None or vehicles == 0:
            trafficVol = 1
         elif vehicles < 400:
            trafficVol = 1
         elif vehicles < 1500:
            trafficVol = 2
         elif vehicles < 2000:
            trafficVol = 3
         else:
            trafficVol = 4
         
         if flag == 0:
            laneWidth = surfwidth
         
         # Freeways
         if mtfcc in ('S1100', 'S1100HOV') or routeType == 'IS':
            if flag == -1:
               laneWidth = 24
            shoulderWidth = 24

         # Arterials
         elif mtfcc == 'S1200PRI' or routeType in ('SR', 'US'):
            if flag == -1:
               if speed <= 45:
                  if trafficVol <= 3:  
                     laneWidth = 22
                  else: 
                     laneWidth = 24
               elif speed <= 55:
                  if trafficVol <= 2:  
                     laneWidth = 22
                  else: 
                     laneWidth = 24
               else:
                  laneWidth = 24
            if trafficVol == 1:
               shoulderWidth = 8
            elif trafficVol <= 3:
               shoulderWidth = 12
            else:
               shoulderWidth = 16
         
         # Collectors   
         elif mtfcc == 'S1200LOC':
            if flag == -1:
               if speed <= 30:
                  if trafficVol <= 2:  
                     laneWidth = 20
                  elif trafficVol <= 3:
                     laneWidth = 22
                  else: 
                     laneWidth = 24
               elif speed <= 50:
                  if trafficVol <= 1:  
                     laneWidth = 20
                  elif trafficVol <= 3:
                     laneWidth = 22
                  else: 
                     laneWidth = 24
               else:
                  if trafficVol <= 2:  
                     laneWidth = 22
                  else: 
                     laneWidth = 24
            if trafficVol == 1:
               shoulderWidth = 4
            elif trafficVol == 2:
               shoulderWidth = 10
            elif trafficVol == 3:
               shoulderWidth = 12
            else:
               shoulderWidth = 16
         
         # Local roads
         else: 
            if flag == -1:
               if speed <= 15:
                  if trafficVol == 1:  
                     laneWidth = 18
                  elif trafficVol <= 3:
                     laneWidth = 20
                  else: 
                     laneWidth = 22
               elif speed <= 40:
                  if trafficVol == 1:  
                     laneWidth = 18
                  elif trafficVol == 2:
                     laneWidth = 20
                  elif trafficVol == 3:
                     laneWidth = 22
                  else: 
                     laneWidth = 24
               elif speed <= 50:
                  if trafficVol == 1:  
                     laneWidth = 20
                  elif trafficVol <= 3:
                     laneWidth = 22
                  else: 
                     laneWidth = 24
               else:
                  if trafficVol <= 2:
                     laneWidth = 22
                  else: 
                     laneWidth = 24
            if trafficVol == 1:
               shoulderWidth = 4
            elif trafficVol == 2:
               shoulderWidth = 10
            elif trafficVol == 3:
               shoulderWidth = 12
            else:
               shoulderWidth = 16
         
         roadWidth_FT = laneWidth + shoulderWidth
         buff_M = roadWidth_FT * convFactor
      else:
      # Use manually measured value if it exists
         buff_M = override*convFactor*2
      return buff_M"""
   arcpy.CalculateField_management (inRCL, 'NH_BUFF_M', expression, 'PYTHON', code_block)
   arcpy.CalculateField_management (inRCL, 'NH_COMMENTS', '"%s"' %comment, 'PYTHON')
   
   printMsg('Mission accomplished.')
   
   return inRCL

def CreateRoadSurfaces_su(inRCL, outSurfaces):
   """Generates road surfaces from road centerlines.
   
   This function was adapted from a ModelBuilder toolbox created by Kirsten R. Hazler and Peter Mitchell"""
   printMsg('Creating road surfaces. This could take awhile...')
   arcpy.Buffer_analysis(inRCL, outSurfaces, "NH_BUFF_M", "FULL", "FLAT", "NONE", "", "PLANAR")
   printMsg('Mission accomplished.')
   
   return outSurfaces
   
def CheckConSite_su(inRCL, inFeats, searchDist):
   """Checks if road segment is potentially relevant to ConSite delineation, based on spatial proximity to inFeats, and marks records accordingly in the NH_CONSITE field (1 = potentially relevant; 0 = not relevant)
   
This function was adapted from a ModelBuilder toolbox created by Kirsten R. Hazler and Peter Mitchell"""
   
   arcpy.MakeFeatureLayer_management(inRCL, "lyrRCL")
   SelectLayerByLocation_management ("lyrRCL", "WITHIN_A_DISTANCE", inFeats, searchDist, "NEW_SELECTION", "NOT_INVERT")
   arcpy.CalculateField_management("lyrRCL", "NH_CONSITE", 1, "PYTHON")
   arcpy.SelectLayerByAttribute_management("lyrRCL", "SWITCH_SELECTION")
   arcpy.CalculateField_management("lyrRCL", "NH_CONSITE", 0, "PYTHON")
   
   return inRCL
      
############################################################################

# Use the section below to enable a function (or sequence of functions) to be run directly from this free-standing script (i.e., not as an ArcGIS toolbox tool)

def main():
   # Set up your variables here
   inRCL = r'H:\Backups\GIS_Data_VA\VGIN\RCL\CurrentData\RCL_2017Q3\Virginia_RCL_Dataset_2017Q3.gdb\VA_CENTERLINE'
   outRCL = r'C:\Users\xch43889\Documents\Working\RCL\RCL_Proc.gdb\RCL_subset_20171206'
   inVDOT = r'H:\Backups\GIS_Data_VA\VGIN\RCL\CurrentData\RCL_2017Q3\Virginia_RCL_Dataset_2017Q3.gdb\VDOT_ATTRIBUTE'
   outSurfaces = r'C:\Users\xch43889\Documents\Working\RCL\RCL_Proc.gdb\RCL_surfaces_20171206'
   
   # Include the desired function run statement(s) below
   #ExtractRCL_su(inRCL, outRCL)
   #PrepRoadsVA_su(outRCL, inVDOT)
   #AssignBuffer_su(outRCL)
   CreateRoadSurfaces_su(outRCL, outSurfaces)

   
   # End of user input
   
if __name__ == '__main__':
   main()