# ---------------------------------------------------------------------------
# CostDist.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creator: Kirsten R. Hazler
# Creation Date: 2017-10-24 
# Last Edit: 2018-06-28

# Summary:
# A collection of functions for running cost distance analysis based on road speeds.

# Usage tips:
# Prior to running the functions in this module, use the following function sequence from ProcRoads.py to prepare roads for travel time analysis:
# - PrepRoadsVA (to prepare Virginia RCL data)
# - PrepRoadsTIGER (to prepare TIGER roads data from adjacent states)
# - MergeRoads (to merge the RCL and TIGER datasets into a seamless dataset, with a limited set of critical fields in the output)
# 
# The following functions are helper functions called by the above functions:
# - printMsg (shortcut for informative progress messaging)
# - ProjectToMatch (to project one dataset to match the coordinate system of another)
# ---------------------------------------------------------------------------

# Import Helper module and functions
from Helper import *


def CostSurfTravTime(inRoads, snpRast, outCostSurf, bkgdNoData=False, valFld="TravTime", priFld="Speed_upd"):
   """Creates a cost surface from road segments based on the TravTime field, which represents time, in minutes, to travel 1 meter at the posted road speed. Areas with no roads are assumed to allow walking speed of 3 miles/hour, equivalent to a TravTime value of  0.01233.
   
Parameters:
- inRoads: Input roads feature class. This should have been produced by running the sequence of functions in the ProcRoads.py module.
- snpRast: A raster used as a processing mask and to set cell size and alignment. This could be an NLCD raster resampled to 5-m cells, for example.
- outCostSurf: The output raster dataset.
- bkgdNoData: Boolean, default value is False. If True, the background value is NoData; if False, it is set to a walking speed value.
- valFld: The field used to set the output raster values. The default field is "TravTime".
- priFld: The priority field, used to determine which road segment to use to assign cell values in cases of conflict. The default field is "Speed_upd".

This function was adapted from ModelBuilder tools created by Kirsten R. Hazler and Tracy Tien for the Development Vulnerability Model (2015)"""

   # Ensure inputs are in same coordinate system
   printMsg('Checking coordinate systems of inputs...')
   prjRoads = ProjectToMatch(inRoads, snpRast)

   # Rasterize lines
   printMsg('Rasterizing lines...')
   tmpRast = outCostSurf + '0'
   arcpy.PolylineToRaster_conversion(prjRoads, valFld, tmpRast, "MAXIMUM_LENGTH", priFld, snpRast)

   # Set time costs for non-roads to finalize cost surface
   printMsg('Creating final cost surface...')
   if bkgdNoData:
      # bkgdNoData has only highways/ramps, so no background value is needed
      cs = ExtractByMask(tmpRast, snpRast)
   else:
      cs = Con(IsNull(tmpRast), 0.01233, tmpRast)
   cs.save(outCostSurf)
   # Cleanup
   try:
      arcpy.Delete_management(tmpRast)
   except:
      printMsg('Attempted cleanup, but unable to delete %s.' % tmpRast)

   printMsg('Mission accomplished.')
   return outCostSurf


############################################################################

# Use the section below to enable a function (or sequence of functions) to be run directly from this free-standing script (i.e., not as an ArcGIS toolbox tool)
def main():

   # set project folder and create new cost surfaces GDB
   project = r'L:\David\projects\RCL_processing\Tiger_2020'
   outGDB = project + os.sep + 'cost_surfaces.gdb'
   if not arcpy.Exists(outGDB):
      arcpy.CreateFileGDB_management(os.path.dirname(outGDB), os.path.basename(outGDB))

   # template raster
   snpRast = r'L:\David\projects\RCL_processing\RCL_processing.gdb\SnapRaster_albers_wgs84'
   arcpy.env.extent = snpRast
   arcpy.env.snapRaster = snpRast
   arcpy.env.cellSize = snpRast
   arcpy.env.mask = snpRast
   arcpy.env.overwriteOutput = True

   # Roads subset dataset (see ProcRoads.py)
   inGDB = os.path.join(project, 'roads_proc.gdb')
   inRoads = os.path.join(inGDB, 'all_subset')


   ## Make cost surfaces
   # NOTE: both surfaces should include ramps (RmpHwy = 1)
   # LAH-only cost surface
   roadSub = os.path.join(inGDB, 'all_subset_only_lah')
   arcpy.Select_analysis(inRoads, roadSub, "RmpHwy <> 0")
   outCostSurf = outGDB + os.sep + 'costSurf_only_lah'
   CostSurfTravTime(roadSub, snpRast, outCostSurf, bkgdNoData=True)
   # no-LAH cost surface
   roadSub = os.path.join(inGDB, 'all_subset_no_lah')
   arcpy.Select_analysis(inRoads, roadSub, "RmpHwy <> 2")
   outCostSurf = outGDB + os.sep + 'costSurf_no_lah'
   CostSurfTravTime(roadSub, snpRast, outCostSurf)


   ## Make walking cost surface-on local roads only: Walkable roads include everything except LAH/ramps
   inRoads1 = os.path.join(inGDB, 'all_centerline_urbAdjust')
   inRoads = os.path.join(inGDB, 'all_centerline_walkable')
   arcpy.Select_analysis(inRoads1, inRoads, "rmpHwy = 0 AND RTTYP <> 'I'")
   outCostSurf = outGDB + os.sep + 'walkRoads'
   CostSurfTravTime(inRoads, snpRast, outCostSurf, bkgdNoData=True)
   # Make background values for walking (excluding areas of LAH as nodata areas in the walk raster)
   lah = outGDB + os.sep + 'costSurf_only_lah'
   Con(IsNull(lah), 0.03699, None).save(outGDB + os.sep + 'crawl')
   # Final walking cost surface raster is: NoData on LAH roads, 3 MPH on all other roads, and 1 MPH in all other areas
   Con(IsNull(outCostSurf), outGDB + os.sep + 'crawl', 0.01233).save(outGDB + os.sep + 'costSurf_walk')


   ## clean up
   garbagePickup([outGDB + os.sep + 'walkRoads', outGDB + os.sep + 'crawl'])
   # Build pyramids for all rasters
   arcpy.BuildPyramidsandStatistics_management(outGDB)

if __name__ == '__main__':
   main()
