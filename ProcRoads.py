# ---------------------------------------------------------------------------
# ProcRoads.py
# Version:  ArcGIS Pro / Python 3.x
# Creator: Kirsten R. Hazler / David Bucklin
# Creation Date: 2017-10-17 
# Last Edit: 2022-03-11

# Summary:
# A collection of functions for processing roads data to prepare them as inputs for various analyses.

# Usage tips:
# See https://www2.census.gov/geo/pdfs/reference/mtfccs2018.pdf for current road codes in TIGER data

# Use the following function sequence to prepare roads for travel time analysis:
# - PrepRoadsVA_tt (to prepare Virginia RCL data for travel time analysis)
# - PrepRoadsTIGER_tt (to prepare TIGER roads data from adjacent states for travel time analysis)
# - MergeRoads_tt (to merge the RCL and TIGER datasets into a seamless dataset, with a limited set of critical fields in the output)
# - MakeNetworkDataset_tt (to create a new network dataset for travel time analyses, from merged roads dataset)
# 
# Use the following function sequence to generate road surfaces from road centerlines:
# - ExtractRCL_su (to extract the relevant road segments for which you want surfaces generated)
# - PrepRoadsVA_su (to add necessary fields to roads data)
# - AssignBuffer_su (to assign road surface buffer widths)
# - CreateRoadSurfaces_su (to generate road surfaces based on the specified buffer widths)

# Use the following function sequence to generate road density from TIGER road centerlines:
# - FilterRoads_dens
# - CalcRoadDensity
# ---------------------------------------------------------------------------

# Import Helper module and functions
from Helper import *


def PrepRoadsVA_tt(inRCL, outSubset=None):
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
   arcpy.AddField_management(inRCL, "SPEED_cmnt", "TEXT", "", "", 50)
   # Process: Create and calculate "FlgFld"
   # This field is used to flag records with suspect LOCAL_SPEED_MPH values
   # 1 = Flagged: need to update speed based on MTFCC field
   # -1 = Flagged: need to set speed to 3 (walking pace)
   # 0 = Unflagged: record assumed to be fine as is
   printMsg("Adding and populating 'FlgFld' field...")
   arcpy.AddField_management(inRCL, "FlgFld", "LONG")
   codeblock = """def Flg (exists, speed):
      if exists == "N":
         return -1
      else:
         if not speed or speed == 0 or speed % 5 != 0:
            return 1
         else:
            return 0"""
   expression = "Flg(!SEGMENT_EXISTS!,!LOCAL_SPEED_MPH!)"
   arcpy.CalculateField_management(inRCL, "FlgFld", expression, "PYTHON3", codeblock)

   # Process: Create and calculate "SPEED_upd" field.
   # This field is used to store speed values to be used in later processing. It allows for altering speed values according to QC criteria, without altering original values in the  existing "LOCAL_SPEED_MPH" field. 
   printMsg("Adding and populating 'SPEED_upd' field...")
   arcpy.AddField_management(inRCL, "SPEED_upd", "LONG")
   codeblock = """def SpdUpd(flgfld, mtfcc, speed):
      if flgfld == 1:
         if mtfcc in ['S1100','S1100HOV']:
            return 55
         elif mtfcc in ['S1200','S1200LOC','S1200PRI','S1300', 'S1640']:
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
   arcpy.CalculateField_management(inRCL, "SPEED_upd", expression, "PYTHON3", codeblock)

   # Process: Create and calculate "TravTime" field
   # This field is used to store the travel time, in minutes, required to travel 1 meter, based on the road speed designation.
   printMsg("Adding and populating 'TravTime' field...")
   arcpy.AddField_management(inRCL, "TravTime", "DOUBLE")
   expression = "0.037/ !SPEED_upd!"
   arcpy.CalculateField_management(inRCL, "TravTime", expression, "PYTHON3")

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
   arcpy.CalculateField_management(inRCL, "RmpHwy", expression, "PYTHON3", codeblock)

   # Process: Create and calculate the "UniqueID" field
   # This field stores a unique ID with a state prefix for ease of merging data from different states.
   printMsg("Adding and populating 'UniqueID' field...")
   arcpy.AddField_management(inRCL, "UniqueID", "TEXT", "", "", "16")
   expression = "'VA_' +  str(int(!RCL_ID!))"
   arcpy.CalculateField_management(inRCL, "UniqueID", expression, "PYTHON3")

   if outSubset:
      print("Outputting subset of driving-only roads (" + outSubset + ")...")
      where_clause = "MTFCC NOT IN ('S1730', 'S1780', 'S9999', 'S1710', 'S1720', 'S1740','S1820', 'S1830', 'S1500') AND SEGMENT_TYPE NOT IN (50)"
      arcpy.Select_analysis(inRCL, outSubset, where_clause)

   printMsg("Finished prepping %s." % inRCL)
   return inRCL


def PrepRoadsTIGER_tt(inDir, outRoads, outSubset=None, inBnd=None, urbAreas=None):
   """Prepares a set of TIGER line shapefiles representing roads to be used for travel time analysis. This function assumes that there already exist some specific fields, including:
   - MTFCC
   - RTTYP
   If any of the assumed fields do not exist, have been renamed, or are in the wrong format, the script will fail.

   This function was adapted from a ModelBuilder tool created by Kirsten R. Hazler and Tracy Tien for the Development Vulnerability Model (2015)"""

   # Process: Merge all roads
   arcpy.env.workspace = inDir
   inList = arcpy.ListFeatureClasses()

   printMsg("Merging TIGER roads datasets...")

   if inBnd:
      # Process: Clip to boundary
      mergeRds = scratchGDB + os.sep + "mergeRds"
      arcpy.Merge_management(inList, mergeRds)
      printMsg("Clipping roads to boundary...")
      arcpy.Clip_analysis(mergeRds, inBnd, outRoads)
   else:
      arcpy.Merge_management(inList, outRoads)

   # Process: Create and calculate "SPEED_upd" field.
   # This field is used to store speed values to be used in later processing. It allows for altering speed values according to QC criteria
   printMsg("Adding and populating 'Speed_upd' field...")
   arcpy.AddField_management(outRoads, "Speed_upd", "LONG")
   codeblock = """def Speed(mtfcc, rttyp):
      if mtfcc == 'S1100':
         if rttyp == 'I':
            return 70
         else:
            return 65
      elif mtfcc in ['S1200', 'S1640']:
         # secondary roads (not limited access)
         if rttyp in ['I','S','U']:
            # interstates, state roads, u.s. roads
            return 55
         else:
            return 45
      elif mtfcc == 'S1630':
         # ramps
         return 30
      elif mtfcc in ['C3061', 'C3062', 'S1400', 'S1740']:
         # residential/other roads
         return 25
      elif mtfcc in ['S1500', 'S1730', 'S1780']:
         # 4WD, alleys, and parking lots
         return 15
      elif mtfcc == 'S1820':
         # bike path
         return 10
      else:  
         return 3"""
   expression = "Speed(!MTFCC!,!RTTYP!)"
   arcpy.CalculateField_management(outRoads, "Speed_upd", expression, "PYTHON3", codeblock)

   # reduce speeds by 10 mph for road segments intersecting urban areas
   if urbAreas:
      printMsg("Adjusting speeds in urban areas...")
      noUrb = arcpy.Erase_analysis(outRoads, urbAreas, scratchGDB + os.sep + "noUrb")
      onlyUrb = arcpy.Clip_analysis(outRoads, urbAreas, scratchGDB + os.sep + "onlyUrb")
      codeblock = """def Speed(Speed_upd):
         if Speed_upd > 30:
            return Speed_upd - 10
         else:
            return Speed_upd"""
      expression = "Speed(!Speed_upd!)"
      arcpy.CalculateField_management(onlyUrb, "Speed_upd", expression, "PYTHON3", codeblock)
      outRoads = arcpy.Merge_management([noUrb, onlyUrb], outRoads + '_urbAdjust')

   # Process: Create and calculate "TravTime" field
   # This field is used to store the travel time, in minutes, required to travel 1 meter, based on the road speed designation.
   printMsg("Adding and populating 'TravTime' field...")
   arcpy.AddField_management(outRoads, "TravTime", "DOUBLE")
   expression = "0.037/ !SPEED_upd!"
   arcpy.CalculateField_management(outRoads, "TravTime", expression, "PYTHON3")

   # Process: Create and calculate the "RmpHwy" field
   # This field indicates if a road is a limited access highway (2), a ramp (1), or any other road type (0)
   printMsg("Adding and populating 'RmpHwy' field...")
   arcpy.AddField_management(outRoads, "RmpHwy", "SHORT")
   codeblock = """def RmpHwy(mtfcc):
      if mtfcc in ("S1100", "S1100HOV"):
         return 2
      elif mtfcc == "S1630":
         return 1
      else:
         return 0"""
   expression = "RmpHwy(!MTFCC!)"
   arcpy.CalculateField_management(outRoads, "RmpHwy", expression, "PYTHON3", codeblock)

   # Process: Create and calculate the "UniqueID" field
   # This field stores a unique ID with a state prefix for ease of merging data from different states.
   printMsg("Adding and populating 'UniqueID' field...")
   arcpy.AddField_management(outRoads, "UniqueID", "TEXT", "", "", "30")
   expression = "'TL_' + !LINEARID!"
   arcpy.CalculateField_management(outRoads, "UniqueID", expression, "PYTHON3")

   if outSubset:
      print("Outputting subset of driving-only roads (" + outSubset + ")...")
      where_clause = "MTFCC NOT IN ('S1710','S1720','S1730','S1750','S9999','S1820','S1830')"
      arcpy.Select_analysis(outRoads, outSubset, where_clause)

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
   inFlds = ['TravTime', 'UniqueID', 'RmpHwy', 'Speed_upd', 'MTFCC']
   fldMappings = arcpy.FieldMappings()
   for fld in inFlds:
      fldMap = arcpy.FieldMap()
      for tab in inList:
         fldMap.addInputField(tab, fld)
      fldMap.outputField.name = fld
      fldMappings.addFieldMap(fldMap)

   # Merge datasets
   printMsg("Merging datasets...")
   arcpy.Merge_management(inList, outRoads, fldMappings)

   printMsg("Mission accomplished.")
   return outRoads


def RampPts(roads, rampPts, highway="MTFCC = 'S1100'", ramp="MTFCC = 'S1630'", local="MTFCC NOT IN ('S1100', 'S1630')"):
   """
   This functions generates 'ramp points' for use as junctions in a network dataset. It generates
   points at all ramp segment endpoints which intersect a limited access highway or local road.

   This function was develope for use with Tiger/Line roads.

   Used as an internal fn in MakeNetworkDataset_tt.
   """

   lyr_rmp = arcpy.MakeFeatureLayer_management(roads, where_clause=ramp)
   arcpy.FeatureVerticesToPoints_management(lyr_rmp, "r1", "BOTH_ENDS")
   lyr_rmppt = arcpy.MakeFeatureLayer_management("r1")

   # select ramp points intersecting highways
   print('Getting junctions of ramps and highway...')
   lyr_hwy = arcpy.MakeFeatureLayer_management(roads, where_clause=highway)
   arcpy.SelectLayerByLocation_management(lyr_rmppt, "INTERSECT", lyr_hwy)
   arcpy.CopyFeatures_management(lyr_rmppt, rampPts)
   arcpy.CalculateField_management(rampPts, "junction", 1, field_type="SHORT")

   ## get "dead end" hwy points (transition from LAH to local road without ramp) points
   arcpy.Dissolve_management(lyr_hwy, 'hwy_end_diss', "#", "#", "SINGLE_PART", "UNSPLIT_LINES")
   arcpy.FeatureVerticesToPoints_management("hwy_end_diss", "he1", "BOTH_ENDS")
   he1 = arcpy.MakeFeatureLayer_management("he1")

   # select those highway ends intersecting with ramps
   arcpy.SelectLayerByLocation_management(he1, "INTERSECT", lyr_rmp)
   arcpy.CopyFeatures_management(he1, "hwy_endpts")
   arcpy.CalculateField_management('hwy_endpts', "junction", 1, field_type="SHORT")
   arcpy.Append_management('hwy_endpts', rampPts, "NO_TEST")

   # select ramp points intersecting local roads
   print('Getting junctions of ramps and local...')
   lyr_loc = arcpy.MakeFeatureLayer_management(roads, where_clause=local)
   arcpy.SelectLayerByLocation_management(lyr_rmppt, "INTERSECT", lyr_loc)
   arcpy.CopyFeatures_management(lyr_rmppt, 'tmp_ints')
   arcpy.CalculateField_management('tmp_ints', "junction", 2, field_type="SHORT")
   # This will append local ramp intersections, then delete those identical to a highway ramp intersection (hwy takes precendence)
   arcpy.Append_management('tmp_ints', rampPts, "NO_TEST")
   arcpy.SelectLayerByAttribute_management(lyr_rmppt, "CLEAR_SELECTION")

   # now find highway ends that share endpoint with local roads
   print('Getting junctions of highway ends and local...')
   arcpy.SelectLayerByLocation_management(lyr_loc, "BOUNDARY_TOUCHES", "hwy_end_diss")
   # now select highway end points intersecting those roads
   arcpy.SelectLayerByLocation_management(he1, "INTERSECT", lyr_loc)
   # now remove those points intersecting ramps
   arcpy.SelectLayerByLocation_management(he1, "INTERSECT", lyr_rmp, "#", "REMOVE_FROM_SELECTION")
   arcpy.CopyFeatures_management(he1, "hwy_endpts")
   arcpy.CalculateField_management('hwy_endpts', "junction", 3, field_type="SHORT")
   arcpy.Append_management('hwy_endpts', rampPts, "NO_TEST")

   print('Removing duplicate points...')
   arcpy.DeleteIdentical_management(rampPts, ["Shape"])
   arcpy.Delete_management(['tmp_ints', "r1", 'hwy_endpts'])

   return rampPts


def MakeNetworkDataset_tt(inRoads, outGDB):
   """
   :param inRoads: Input raods feature class.
   :param outGDB: Output geodatabase to hold new 'RCL' feature dataset and 'RCL_ND' network dataset
   :return: Feature dataset

   This function was developed for a Tiger-only dataset. Would likely need further editing for a VA-only or
   combined VA+Tiger dataset.
   """

   if not arcpy.Exists(outGDB):
      print("Creating new geodatabase `" + outGDB + "`.")
      arcpy.CreateFileGDB_management(os.path.dirname(outGDB), os.path.basename(outGDB))

   # Remove duplicate roads, make ramp points feature class
   rd_nodup = outGDB + os.sep + 'all_subset_nodup'
   RemoveDupRoads(inRoads, rd_nodup)
   # NOTE: use original roads for RampPts, not dup. removed, which may result in extra vertices that get turned into ramp points if used
   rmp_pts = outGDB + os.sep + "ramp_junctions"
   RampPts(inRoads, rmp_pts)

   # Make Network GDB and feature dataset
   fd = os.path.join(outGDB, 'RCL')
   arcpy.CreateFeatureDataset_management(outGDB, "RCL", arcpy.env.outputCoordinateSystem)
   arcpy.FeatureClassToFeatureClass_conversion(rd_nodup, fd, "roads_limitedAccess", "MTFCC = 'S1100'")
   arcpy.FeatureClassToFeatureClass_conversion(rd_nodup, fd, "roads_ramps", "MTFCC = 'S1630'")
   arcpy.FeatureClassToFeatureClass_conversion(rd_nodup, fd, "roads_local", "MTFCC NOT IN ('S1100', 'S1630')")
   arcpy.FeatureClassToFeatureClass_conversion(rmp_pts, fd, "ramps_limitedAccess", "junction = 1")
   arcpy.FeatureClassToFeatureClass_conversion(rmp_pts, fd, "ramps_local", "junction = 2")
   arcpy.FeatureClassToFeatureClass_conversion(rmp_pts, fd, "limitedAccess_local", "junction = 3")
   ls = ["roads_limitedAccess", "roads_ramps", "roads_local", "ramps_limitedAccess", "ramps_local",
         "limitedAccess_local"]

   # Create Network dataset
   arcpy.CreateNetworkDataset_na(fd, 'RCL_ND', ls, None)
   print("Created Network Dataset `" + fd + "`.")
   return fd


def ExtractRCL_su(inRCL, outRCL):
   """Extracts the relevant features from the Virginia Road Centerlines (RCL) feature class to be used for creating
   road surfaces. Omits segments based on data in the MTFCC and SEGMENT_TYPE fields. If any of the assumed fields do
   not exist, have been renamed, or are in the wrong format, the script will fail.
   
   Excludes the following MTFCC types:
   - S1730: Alleys
   - S1780: Parking Lot Roads
   - S9999: Driveways
   - S1710: Walkways/Pedestrian Trails
   - S1720: Stairways
   - S1740: Service Vehicle Private Drives
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
   # This will maintain domains (Select does not).
   arcpy.FeatureClassToFeatureClass_conversion(inRCL, os.path.dirname(outRCL), os.path.basename(outRCL), where_clause)
   printMsg('Roads extracted.')

   return outRCL


def PrepRoadsVA_su(inRCL, inVDOT):
   """Adds fields to road centerlines data, necessary for generating road surfaces.
   - inRCL = road centerlines feature class
   - inVDOT = VDOT attribute table (from same geodatabase as inRCL)

   This function was adapted from a ModelBuilder toolbox created by Kirsten R. Hazler and Peter Mitchell"""

   # Define a class to store field information
   class Field:
      def __init__(self, Name='', Type='', Length=''):
         self.Name = Name
         self.Type = Type
         self.Length = Length

   # Specify fields to add
   printMsg('Setting field definitions')
   # All field names have the prefix "NH" to indicate they are fields added by Natural Heritage   
   fldBuffM = Field('NH_BUFF_M', 'DOUBLE',
                    '')  # Buffer width in meters. This field is calculated automatically based on information in other fields.
   fldFlag = Field('NH_SURFWIDTH_FLAG', 'SHORT',
                   '')  # Flag for surface widths needing attention. This field is automatically calculated initially, but can be manually changed as needed (-1 = needs attention; 0 = OK; 1 = record reviewed and amended)
   fldComments = Field('NH_COMMENTS', 'TEXT',
                       500)  # QC/processing/editing comments. This field is for automatic or manual data entry.
   fldBuffFt = Field('NH_BUFF_FT', 'DOUBLE',
                     '')  # Buffer width in feet. This field is for manual data entry, used to override buffer width values that would otherwise be calculated.
   fldConSite = Field('NH_CONSITE', 'SHORT',
                      '')  # Field to indicate if segment relevant to ConSite delineation (1 = close enough to features to be relevant; 0 = not relevant)
   addFields = [fldBuffM, fldFlag, fldComments, fldBuffFt, fldConSite]

   # Add the fields
   printMsg('Adding fields...')
   for f in addFields:
      arcpy.AddField_management(inRCL, f.Name, f.Type, '', '', f.Length)
      printMsg('Field %s added.' % f.Name)

   # Join fields from VDOT table
   printMsg('Joining attributes from VDOT table. This could take hours...')
   vdotFields = ['VDOT_RTE_TYPE_CD', 'VDOT_SURFACE_WIDTH_MSR', 'VDOT_TRAFFIC_AADT_NBR']
   # JoinFields(inRCL, 'VDOT_EDGE_ID', inVDOT, 'VDOT_EDGE_ID', vdotFields)
   # My JoinFields function failed to finish after ~24 hours, so I reverted to using arcpy.JoinField.
   # arcpy.JoinField_management(inRCL, 'VDOT_EDGE_ID', inVDOT, 'VDOT_EDGE_ID', vdotFields)
   JoinFast(inRCL, 'VDOT_EDGE_ID', inVDOT, 'VDOT_EDGE_ID', vdotFields)

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
   arcpy.CalculateField_management(inRCL, 'NH_SURFWIDTH_FLAG', expression, 'PYTHON', code_block)

   printMsg('Roads attribute table updated.')

   return inRCL


def AssignBuffer_su(inRCL):
   """Assign road surface buffer width based on other attribute fields.
   The codeblock used to assign buffer widths is based on information here:
   https://nacto.org/docs/usdg/geometric_design_highways_and_streets_aashto.pdf. 
   See the various tables (labeled "Exhibit x-x) showing the minimum width of traveled
   way and shoulders for different road types and capacities. Relevant pages: 388,429,452, 476-478, 507-509.

   This function was adapted from a ModelBuilder toolbox created by Kirsten R. Hazler and Peter Mitchell"""

   # Get formatted time stamp and auto-generated comment
   ts = datetime.now()
   stamp = '%s-%s-%s %s:%s' % (
      ts.year, str(ts.month).zfill(2), str(ts.day).zfill(2), str(ts.hour).zfill(2), str(ts.minute).zfill(2))
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
   arcpy.CalculateField_management(inRCL, 'NH_BUFF_M', expression, 'PYTHON', code_block)
   arcpy.CalculateField_management(inRCL, 'NH_COMMENTS', '"%s"' % comment, 'PYTHON')

   printMsg('Mission accomplished.')

   return inRCL


def CreateRoadSurfaces_su(inRCL, outSurfaces):
   """Generates road surfaces from road centerlines.
   
   This function was adapted from a ModelBuilder toolbox created by Kirsten R. Hazler and Peter Mitchell"""
   printMsg('Creating road surfaces. This could take awhile...')
   with arcpy.EnvManager(XYTolerance="0.1 Meters"):
      # default tolernace is 0.001 meters. Larger tolerances will result in more generalized buffers (fewer vertices)
      arcpy.Buffer_analysis(inRCL, outSurfaces, "NH_BUFF_M", "FULL", "FLAT", "NONE", "", "PLANAR")
      # NOTE: Pairwise buffer doesn't have line_end option (defaults to round). Not using.
      # arcpy.PairwiseBuffer_analysis(inRCL, outSurfaces, "NH_BUFF_M", "NONE")
   printMsg('Running repair...')
   arcpy.RepairGeometry_management(outSurfaces)
   printMsg('Mission accomplished.')
   # Add domains back to road surfaces
   copyDomains(outSurfaces, inRCL)

   return outSurfaces


def CheckConSite_su(inRCL, inFeats, searchDist):
   """Checks if road segment is potentially relevant to ConSite delineation, based on spatial proximity to inFeats,
   and marks records accordingly in the NH_CONSITE field (1 = potentially relevant; 0 = not relevant)
   
   This function was adapted from a ModelBuilder toolbox created by Kirsten R. Hazler and Peter Mitchell"""

   arcpy.MakeFeatureLayer_management(inRCL, "lyrRCL")
   arcpy.SelectLayerByLocation_management("lyrRCL", "WITHIN_A_DISTANCE", inFeats, searchDist, "NEW_SELECTION",
                                          "NOT_INVERT")
   arcpy.CalculateField_management("lyrRCL", "NH_CONSITE", 1, "PYTHON")
   arcpy.SelectLayerByAttribute_management("lyrRCL", "SWITCH_SELECTION")
   arcpy.CalculateField_management("lyrRCL", "NH_CONSITE", 0, "PYTHON")

   return inRCL


def RemoveDupRoads(inRoads, outRoads, sort_fld=[["Speed_upd", "DESCENDING"]]):
   """Duplicate road segment removal developed for Tiger/Line roads dataset. Retains segment according to the priority
    in the sort argument (default is to retain highest speed segment). Arguments:
    - inRoads: Input roads. Make sure to filter to subset desired
    - outRoads: Output roads feature class
    - sort_fld: sorting order list, e.g.: [["Field1", "ASCENDING"], ["Field2", "DESCENDING"]]

    Used as an internal fn in MakeNetworkDataset_tt.
    Used as an internal fn in FilterRoad_dens, in place of Dissolve.

    NOTE: Uses an ArcPro-only function (CountOverlappingFeatures)
    """

   printMsg('Making unique segments for overlapping roads...')
   arcpy.CountOverlappingFeatures_analysis(inRoads, "over0")
   arcpy.SpatialJoin_analysis('over0', inRoads, 'road1', "JOIN_ONE_TO_MANY", match_option="WITHIN")
   printMsg('Creating no-duplicates roads dataset...')
   arcpy.Sort_management('road1', outRoads, sort_fld)
   arcpy.DeleteIdentical_management(outRoads, "TARGET_FID")
   garbagePickup(['road1', 'over0'])

   return outRoads


def FilterRoads_dens(inRoads, selType, outRoads):
   """Makes a subset of roads to include only those to be used for calculating road density, and removes
   duplicates/overlaps. This function is intended only for use with TIGER data in specific format; otherwise will fail.
   Parameters:
   - inRoads = Input roads from TIGER
   - selType = Type of selection to apply, with options "ALL", "NO_HIGHWAY", "LOCAL"
   - outRoads = Output feature class ready for density processing
   """

   # Specify selection query
   if selType == "ALL":
      selQry = "MTFCC in ('S1100', 'S1200', 'S1640', 'S1400', 'S1730', '1740')"
      # Does not actually include ALL, but most. Includes primary roads, secondary roads, collector/arterial roads, service drives, local roads, and alleys
   elif selType == "NO_HIGHWAY":
      selQry = "MTFCC in ('S1200', 'S1640', 'S1400', 'S1730', '1740')"
      # Same as above except excludes highways
   elif selType == "LOCAL":
      selQry = "MTFCC in ('S1640', 'S1400', 'S1730', '1740')"
      # Same as above except excludes secondary roads
   else:
      printMsg('No valid selection type specified; aborting.')
      sys.exit()

   # Subset records based on selection query
   printMsg('Extracting relevant road segments and saving...')
   tmpRoads = scratchGDB + os.sep + 'tmpRoads'
   arcpy.Select_analysis(inRoads, tmpRoads, selQry)

   # Eliminate duplicates/overlaps
   printMsg('Generating unique roads segments...')
   # arcpy.Dissolve_management(tmpRoads, outRoads, "", "", "SINGLE_PART", "DISSOLVE_LINES")
   # Below retains original road segments/attributes
   RemoveDupRoads(tmpRoads, outRoads)

   printMsg('Roads ready for density calculation')
   return outRoads


def CalcRoadDensity(inRoads, inSnap, inMask, outRoadDens, sRadius=250, outUnits="SQUARE_KILOMETERS",
                    outVals="DENSITIES"):
   """Creates a kernel density surface from input roads.
   Parameters:
   - inRoads = Input lines feature class representing roads
   - inSnap = Snap raster used to specify the output coordinate system, cell size, and cell alignment
   - inMask = Feature class or raster used to specify processing extent and mask
   - outRoadDens = Output raster representing road density
   - sRadius = The search radius within which to calculate density. Units are based on the linear unit of the
      projection of the output spatial reference.
   - outUnits = The desired area units of the output density values.
   - outVals = Determines what the values in the output raster represent. Options: DENSITIES or EXPECTED_COUNTS

   NOTE: If input coordinate system units are meters, and outUnits are SQUARE_KILOMETERS, the output densities are km
   per square km. It gets difficult to intuitively interpret using other units.
   """

   arcpy.env.snapRaster = inSnap
   arcpy.env.cellSize = inSnap
   arcpy.env.mask = inMask
   arcpy.env.extent = inMask
   cellSize = arcpy.env.cellSize

   printMsg('Comparing coordinate system of input roads with snap raster...')
   inRoads_prj = ProjectToMatch(inRoads, inSnap)

   printMsg('Calculating road density...')
   outKDens = arcpy.sa.KernelDensity(inRoads_prj, "NONE", cellSize, sRadius, outUnits, outVals)
   arcpy.sa.SetNull(outKDens, outKDens, "Value <= 0").save(outRoadDens)
   # outKDens.save(outRoadDens)
   arcpy.BuildPyramids_management(outRoadDens)

   printMsg('Finished.')
   return outRoadDens


############################################################################

# Use the section below to enable a function (or sequence of functions) to be run directly from this free-standing script (i.e., not as an ArcGIS toolbox tool)

# Usage tips:
# Use the following function sequence to prepare roads for travel time analysis:
# - PrepRoadsVA_tt (to prepare Virginia RCL data for travel time analysis)
# - PrepRoadsTIGER_tt (to prepare TIGER roads data from adjacent states for travel time analysis)
# - MergeRoads_tt (to merge the RCL and TIGER datasets into a seamless dataset, with a limited set of critical fields in the output)
# - MakeNetworkDataset_tt (to create a new network dataset for travel time analyses, from merged roads dataset)
# 
# Use the following function sequence to generate road surfaces from road centerlines:
# - ExtractRCL_su (to extract the relevant road segments for which you want surfaces generated)
# - PrepRoadsVA_su (to add necessary fields to roads data)
# - AssignBuffer_su (to assign road surface buffer widths)
# - CreateRoadSurfaces_su (to generate road surfaces based on the specified buffer widths)
#
# Use the following function sequence to generate road density from TIGER road centerlines:
# - FilterRoads_dens (filter roads according to selction, removes overlapping segments)
# - CalcRoadDensity (to calculate a road density surface)


def main():

   # The three workflows (Travel Time, Road Surfaces, and Road Density) are demonstrated below.
   # Change the inputs as needed to run a new analysis.

   ### Travel Time processing with Tiger only
   # set project folder name and create project geodatabase
   project = r'F:\David\projects\RCL_processing\Tiger_2020'
   wd = project + os.sep + 'roads_proc.gdb'
   if not arcpy.Exists(wd):
      arcpy.CreateFileGDB_management(os.path.dirname(wd), os.path.basename(wd))
   arcpy.env.workspace = wd
   arcpy.env.outputCoordinateSystem = r'F:\David\projects\RCL_processing\RCL_processing.gdb\VA_Buff50mi_wgs84'

   # Process Tiger roads for travel time
   inDir = project + '/data/unzip'
   outRoads = wd + os.sep + 'all_centerline'
   outSubsetTiger = 'all_subset'
   # Urban areas are used to reduce speeds on >30mph roads by 10 mph. Fixed to 2018 dataset
   urbAreas = r'F:\David\projects\RCL_processing\Tiger_2018\roads_proc.gdb\metro_areas'
   PrepRoadsTIGER_tt(inDir, outRoads, outSubsetTiger, inBnd=None, urbAreas=urbAreas)

   # Create a travel time Network Dataset
   inRoads = outSubsetTiger
   outGDB = project + os.sep + "RCL_Network.gdb"
   MakeNetworkDataset_tt(inRoads, outGDB)
   # From here, Network Dataset requires manual settings in ArcGIS pro. See NetworkAnalyst-Setup.txt.

   ### End Travel Time processing


   ### Road Surfaces processing
   project = r'D:\projects\RCL\VA_RCL\RCL_2021Q4'
   wd = project + os.sep + 'RCL_surfaces.gdb'
   if not arcpy.Exists(wd):
      arcpy.CreateFileGDB_management(os.path.dirname(wd), os.path.basename(wd))
   arcpy.env.workspace = wd
   arcpy.env.overwriteOutput = True

   # Set up your variables here
   orig_gdb = r'F:\David\GIS_data\roads\Virginia_RCL_Dataset_2021Q4.gdb'
   inRCL = 'VA_CENTERLINE'
   inVDOT = 'VDOT_ATTRIBUTE'
   outRCL = 'RCL_surface_subset'
   outSurfaces = 'VirginiaRoadSurfaces'

   # Copy original feature class, table to project GDB
   arcpy.FeatureClassToFeatureClass_conversion(orig_gdb + os.sep + 'VA_CENTERLINE', wd, inRCL)
   arcpy.TableToTable_conversion(orig_gdb + os.sep + inVDOT, wd, inVDOT)

   # Run road surfaces workflow
   ExtractRCL_su(inRCL, outRCL)
   PrepRoadsVA_su(outRCL, inVDOT)
   AssignBuffer_su(outRCL)
   CreateRoadSurfaces_su(outRCL, outSurfaces)

   ### End Road surfaces processing


   ### Road Density processing
   arcpy.env.workspace = r'F:\David\projects\RCL_processing\Tiger_2020\roads_proc.gdb'
   inRoads = "all_centerline_urbAdjust"  # r'F:\Working\RecMod\roads_proc_TIGER2018.gdb\all_centerline'
   selType = "NO_HIGHWAY"
   outRoads = "roads_filtered"  # r'F:\Working\RecMod\RecModProducts.gdb\Roads_filtered'
   inSnap = r"F:\David\projects\RCL_processing\RCL_processing.gdb\SnapRaster_albers_wgs84"  # r'F:\Working\Snap_AlbersCONUS30\Snap_AlbersCONUS30.tif'
   inMask = r"F:\David\projects\RCL_processing\RCL_processing.gdb\VA_Buff50mi_wgs84"  # r'F:\Working\VA_Buff50mi\VA_Buff50mi.shp'
   outRoadDens = "Roads_kdens_250"  # r'F:\Working\RecMod\RecModProducts.gdb\Roads_kdens_250'

   FilterRoads_dens(inRoads, selType, outRoads)
   CalcRoadDensity(outRoads, inSnap, inMask, outRoadDens)
   # arcpy.sa.SetNull(outRoadDens, outRoadDens, "Value <= 0").save("Roads_kdens_250_noZero")

   ### End Road Density processing


if __name__ == '__main__':
   main()
