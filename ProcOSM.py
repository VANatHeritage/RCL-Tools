# ---------------------------------------------------------------------------
# ProcOSM.py
# Version:  ArcGIS Pro / Python 3.x
# Creator: David Bucklin
# Creation Date: 2021-04

# Pre-requisite:
# download OSM data from Geofabrik here: http://download.geofabrik.de/north-america/us.html.

# Summary:
# A collection of functions for processing OSM roads data to prepare them as a Network Dataset. Processes include:
#  prepOSM: function to merge multiple states' OSM datasets, clip to a boundary, and assign a UA attribute for those
#     segments intersecting an urban areas feature class.
#  attributeOSM: calculates attributes RmpHwy, SPEED_MPH, and TT_MIN. See the functions [rmpHwy, mph, tt] for details
#  makeNetworkDataset: Create a network dataset. This will generate Roads_Hwy and Roads_Local datasets, and a
#     Ramp_Points feature class which defines the connections between them.

# See OSM_networkSettings.txt for further information on configuring the Network Dataset in ArcGIS Pro.

# ---------------------------------------------------------------------------

import arcpy
import time
import os
from ProcRoads import CalcRoadDensity
arcpy.env.overwriteOutput = True


def mergeTiles(projName):
   """
   :param projName: Name for output merged GDB and dataset
   :return: feature class
   """
   # tileGDB = r'L:\David\GIS_data\OSM\osmdata.tileGDB'
   # projName = 'VA_50mile'

   dt = time.strftime('%Y%m%d')

   # get project FCs
   ls = arcpy.ListFeatureClasses(projName + '_osm_line_*')
   bound = arcpy.ListFeatureClasses(projName + '_features_*')[0]
   # grid = arcpy.ListFeatureClasses(projName + '_grid_*')[0]

   # set environments
   arcpy.env.extent = bound
   arcpy.env.outputCoordinateSystem = bound
   arcpy.env.overwriteOutput = True

   # make new tileGDB with timestamp
   proj_gdb = os.getcwd() + os.sep + projName + '_' + dt + '.tileGDB'
   if not arcpy.Exists(proj_gdb):
      print('Creating geodatabase `' + proj_gdb + '`...')
      arcpy.CreateFileGDB_management(os.path.dirname(proj_gdb), os.path.basename(proj_gdb))

   # initiate new feature class
   out = proj_gdb + os.sep + projName + '_osm_line'
   arcpy.CopyFeatures_management(ls[0], out)

   # coulddo: use merge? Might cause issues with memory/processing
   ls2 = ls[1:]
   print('Appending tiles to output dataset...')
   for i in ls2:
      print(i)
      arcpy.Append_management(i, out, "NO_TEST")

   # Clean up final dataset
   print('Deleting identical road segments...')
   arcpy.AddSpatialIndex_management(out)
   arcpy.DeleteIdentical_management(out, ['Shape'])  # Can take 15-30 minutes. # osm_id?
   arcpy.Compact_management(proj_gdb)

   return out


def prepOSM(inFC, appendFC, boundary, urbanAreas, outRoads):
   """
   For merging multiple states' OSM streets data from Geofabrik.
   inFC: Virginia feature class
   appendFC: list of all other states' feature classes
   boundary: feature class used as (coord system, extent, clip).
   urbanAreas: census urban areas feature class, used to assign attribute UA (1=in UA, 0=not in UA)
   outRoads: merged feature class
   """
   arcpy.env.outputCoordinateSystem = boundary
   arcpy.env.extent = boundary
   wd = os.path.dirname(outRoads)

   print('Creating merged feature class...')
   arcpy.FeatureClassToFeatureClass_conversion(inFC, wd, os.path.basename(outRoads))
   for i in appendFC:
      print(i)
      arcpy.Clip_analysis(i, boundary, wd + os.sep + 'rd2')
      arcpy.Append_management(wd + os.sep + 'rd2', outRoads, "NO_TEST")
   # delete identical by osm_id (border roads are included in both state datasets)
   arcpy.GetCount_management(outRoads)
   arcpy.DeleteIdentical_management(outRoads, ['osm_id'])

   # use a selection to attribute UA, so not to alter original geometry (e.g. erase or identity), which can mess with
   # connectivity for Network Analyst.
   print('Identifying roads in urban areas...')
   lyr = arcpy.MakeFeatureLayer_management(outRoads)
   arcpy.SelectLayerByLocation_management(lyr, 'HAVE_THEIR_CENTER_IN', urbanAreas)
   fld = 'UA'
   efld = [a.name for a in arcpy.ListFields(outRoads)]
   if fld not in efld:
      arcpy.AddField_management(outRoads, fld, 'SHORT')
   arcpy.CalculateField_management(lyr, fld, '1')
   arcpy.SelectLayerByAttribute_management(lyr, 'SWITCH_SELECTION')
   arcpy.CalculateField_management(lyr, fld, '0')
   del lyr

   # clean up
   arcpy.Delete_management([wd + os.sep + 'rd2'])
   return outRoads


def rmpHwy(code):
   # Internal fn for attributeOSM
   if code == 5111:
      return 2
   elif code == 5131:
      return 1
   else:
      return 0


def mph(maxspeed, code, ua):
   # Internal fn for attributeOSM
   if maxspeed >= 40 and code in (5111, 5112, 5113, 5114, 5115, 5121, 5122, 5123, 5131, 5132, 5133, 5134, 5135, 5141, 5142, 5143, 5144, 5145, 5146, 5147):
      # only use maxspeed if it is a driving road AND has an assigned speed >=25 MPH (~40 kph).
      s = int(0.5 + maxspeed * 0.621371)
   else:
      if code == 5111:
         # interstates
         s = 70
      elif code == 5112:
         # important roads, typically divided
         s = 65
      elif code == 5113:
         # primary roads
         s = 55
      elif code == 5114:
         # secondary roads
         s = 45
      elif code == 5115:
         # tertiary roads
         s = 35
      elif code in (5121, 5122):
         # local/residential roads
         s = 25
      elif code == 5123:
         # pedestrian-friendly streets
         s = 15
      elif code in (5124, 5153, 5154, 5155, 5199):
         # pedestrian roads/paths or unknown
         s = 3
      elif code in (5131, 5132, 5133, 5134, 5135):
         # connector roads/ramps
         s = 30
      elif code in (5141, 5142):
         # service roads/access roads/parking lots/forestry roads/agricultural use
         s = 15
      elif code == 5143:
         # grade 1 track
         s = 25
      elif code == 5144:
         # grade 2 track
         s = 20
      elif code == 5145:
         # grade 3 track
         s = 15
      elif code == 5146:
         # grade 4 track
         s = 10
      elif code == 5147:
         # grade 5 track
         s = 5
      elif code in (5151, 5152):
         # horse paths/cycle paths
         s = 10
      else:
         # error catch
         s = -1
      if int(ua) == 1:
         # if code in (5111, 5112, 5113, 5114):
         if s > 30:
            # if in urban area and assigned speed is greater than 30, adjust -10 MPH. This affects tertiary and larger roads.
            s = s - 10
   return s


def tt(length_m, speed_mph):
   # Internal fn for attributeOSM
   t = 0.03728 * length_m / speed_mph
   return t


def attributeOSM(inRoads):
   """
   Attribute calculations:
   1. assign 'RmpHwy' field (Highway=2, Ramp=1, other roads=0)
   2. add SPEED_MPH field
   3. add TT_MIN field
   Note: uses internal functions from helper.py to calculate fields.
   Calcuations done using UpdateCursor for faster performance.
   """
   efld = [a.name for a in arcpy.ListFields(inRoads)]

   print('Assigning ramp/highway designations...')
   fld = 'RmpHwy'
   if fld not in efld:
      arcpy.AddField_management(inRoads, fld, 'SHORT')
   with arcpy.da.UpdateCursor(inRoads, ['code', fld]) as curs:
      for i in curs:
         val = rmpHwy(i[0])
         i[1] = val
         curs.updateRow(i)

   print('Assigning road speeds...')
   fld = 'SPEED_MPH'
   if fld not in efld:
      arcpy.AddField_management(inRoads, fld, 'SHORT')
   with arcpy.da.UpdateCursor(inRoads, ['maxspeed', 'code', 'UA', fld]) as curs:
      for i in curs:
         val = mph(i[0], i[1], i[2])
         i[3] = val
         curs.updateRow(i)

   print('Assigning road travel times...')
   fld = 'TT_MIN'
   if fld not in efld:
      arcpy.AddField_management(inRoads, fld, 'DOUBLE')
   with arcpy.da.UpdateCursor(inRoads, ['Shape_Length', 'SPEED_MPH', fld]) as curs:
      for i in curs:
         val = tt(i[0], i[1])
         i[2] = val
         curs.updateRow(i)

   return inRoads


def makeNetworkDataset(inRoads, outGDB, fdName="RoadsNet", netName="RoadsNet_ND"):

   print('Making feature dataset...')
   arcpy.CreateFeatureDataset_management(outGDB, fdName, arcpy.env.outputCoordinateSystem)

   print('Creating motorway ramps connection points feature class...')
   # make ramp endpoints, to account for cases where link (ramp) does not connect to an endpoint of a road.
   # Adding these points to the network will override the default endpoint-only policy for limited access highways.
   lyr = arcpy.MakeFeatureLayer_management(inRoads, where_clause="RmpHwy = 1")
   arcpy.FeatureVerticesToPoints_management(lyr, os.path.join(outGDB, 'rmp'), "BOTH_ENDS")
   del lyr
   lyr_rmp = arcpy.MakeFeatureLayer_management(os.path.join(outGDB, 'rmp'))
   lyr_rd = arcpy.MakeFeatureLayer_management(inRoads, where_clause="RmpHwy <> 1")
   arcpy.SelectLayerByLocation_management(lyr_rmp, "INTERSECT", lyr_rd)
   arcpy.FeatureClassToFeatureClass_conversion(lyr_rmp, os.path.join(outGDB, fdName), 'Ramp_Points')
   del lyr_rmp, lyr_rd
   arcpy.Delete_management(os.path.join(outGDB, 'rmp'))
   # Not adding points for motorway direct connection to other roads, since endpoints should match.

   print('Selecting motorways and links...')
   # Add feature classes to feature dataset
   lyr = arcpy.MakeFeatureLayer_management(inRoads)
   arcpy.SelectLayerByAttribute_management(lyr, "NEW_SELECTION", "RmpHwy IN (1,2)")
   arcpy.FeatureClassToFeatureClass_conversion(lyr, os.path.join(outGDB, fdName), 'Roads_Hwy')
   print('Selecting all other roads...')
   arcpy.SelectLayerByAttribute_management(lyr, "SWITCH_SELECTION")
   arcpy.FeatureClassToFeatureClass_conversion(lyr, os.path.join(outGDB, fdName), 'Roads_Local')
   del lyr

   print('Making network dataset...')
   arcpy.CreateNetworkDataset_na(os.path.join(outGDB, fdName), netName, ['Roads_Hwy', 'Roads_Local', 'Ramp_Points'])
   # From here on, requires manual settings in ArcGIS pro (Source settings, Travel mode, Restrictions)

   return os.path.join(outGDB, fdName, netName)



def main():

   ## HEADER
   dt = time.strftime('%Y%m%d')

   # Make processing GDB
   outGDB = r'E:\projects\OSM\OSM_RoadsProc.gdb'
   if not arcpy.Exists(outGDB):
      arcpy.CreateFileGDB_management(os.path.dirname(outGDB), os.path.basename(outGDB))
   arcpy.env.workspace = outGDB

   ### BEGIN Network Dataset prep
   netGDB = r'E:\projects\OSM\network\OSM_RoadsNet_Albers.gdb'
   if not arcpy.Exists(netGDB):
      arcpy.CreateFileGDB_management(os.path.dirname(netGDB), os.path.basename(netGDB))

   urbanAreas = r'L:\David\projects\RCL_processing\Tiger_2018\roads_proc.gdb\metro_areas'
   boundary = r'L:\David\projects\RCL_processing\RCL_processing.gdb\VA_Buff50mi_wgs84'
   arcpy.env.outputCoordinateSystem = boundary
   inSnap = r"L:\David\projects\RCL_processing\RCL_processing.gdb\SnapRaster_albers_wgs84"

   # Get list of Geofabrik shapefiles
   nm = 'gis_osm_roads_free_1.shp'
   inFC = r'E:\projects\OSM\geofabrik\virginia-latest-free.shp' + os.sep + nm
   dirs = [d for d in os.listdir('geofabrik') if os.path.isdir(os.path.join('geofabrik', d)) and not d.startswith('virginia')]
   appendFC = [os.path.join(os.getcwd(), 'geofabrik', a, nm) for a in dirs]
   # Merged feature class to create
   outRoads = outGDB + os.sep + 'OSM_Roads_' + dt

   # Create merged dataset with UA, speed and travel time attributes
   prepOSM(inFC, appendFC, boundary, urbanAreas, outRoads)
   attributeOSM(outRoads)
   # Make a network GDB, dataset
   makeNetworkDataset(outRoads, netGDB)

   ### END Network Dataset prep


   # Additional processes below (Not needed for network dataset)

   # Make a driving-road density surface (excluding motorways and motorway-links)
   inRoads = 'OSM_Roads_20210422'
   rdlyr = arcpy.MakeFeatureLayer_management(inRoads, where_clause="code IN (5112, 5113, 5114, 5115, 5121, 5122, 5123, 5132, 5133, 5134, 5135, 5141, 5142, 5143, 5144, 5145, 5146, 5147)")
   CalcRoadDensity(rdlyr, inSnap, boundary, inRoads + '_kdens')
   del rdlyr

   # Buffer ALL driving roads, make a raster mask
   rdlyr = arcpy.MakeFeatureLayer_management(inRoads, where_clause="code IN (5111, 5112, 5113, 5114, 5115, 5121, 5122, 5123, 5131, 5132, 5133, 5134, 5135, 5141, 5142, 5143, 5144, 5145, 5146, 5147)")
   arcpy.PairwiseBuffer_analysis(rdlyr, inRoads + '_qtrMileBuff', "0.25 Miles", dissolve_option="ALL")
   del rdlyr

   # Make a mask out of buffered roads
   with arcpy.EnvManager(cellSize=inSnap, snapRaster=inSnap, extent=inSnap, outputCoordinateSystem=inSnap):
      arcpy.PolygonToRaster_conversion(inRoads + '_qtrMileBuff', 'OBJECTID', inRoads + '_qtrMileBuff_rast', cellsize=inSnap)
   arcpy.BuildPyramids_management(inRoads + '_qtrMileBuff_rast')


if __name__ == '__main__':
   main()

# end
