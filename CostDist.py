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
import Helper
from Helper import *

def CostSurfTravTime(inRoads, snpRast, outCostSurf, lahOnly = False, valFld = "TravTime", priFld = "Speed_upd"):
   """Creates a cost surface from road segments based on the TravTime field, which represents time, in minutes, to travel 1 meter at the posted road speed. Areas with no roads are assumed to allow walking speed of 3 miles/hour, equivalent to a TravTime value of  0.01233.
   
Parameters:
- inRoads: Input roads feature class. This should have been produced by running the sequence of functions in the ProcRoads.py module.
- snpRast: A raster used as a processing mask and to set cell size and alignment. This could be an NLCD raster resampled to 5-m cells, for example.
- outCostSurf: The output raster dataset.
- lahOnly: Boolean, default value is False. If True, the background value is NoData; if False, it is set to a walking speed value.
- valFld: The field used to set the output raster values. The default field is "TravTime".
- priFld: The priority field, used to determine which road segment to use to assign cell values in cases of conflict. The default field is "Speed_upd".

This function was adapted from ModelBuilder tools created by Kirsten R. Hazler and Tracy Tien for the Development Vulnerability Model (2015)"""
   
   # Environment settings
   arcpy.env.snapRaster = snpRast
   # arcpy.env.mask = snpRast    # masking not desirable if long bridges will get masked out over water
   arcpy.env.extent = inRoads # extent should be based on input roads; raster is just for snapping
   
   # Ensure inputs are in same coordinate system
   printMsg('Checking coordinate systems of inputs...')
   prjRoads = ProjectToMatch (inRoads, snpRast)
   
   # Rasterize lines
   printMsg('Rasterizing lines...')
   tmpRast = scratchGDB + os.sep + 'tmpRast'
   arcpy.PolylineToRaster_conversion(prjRoads, valFld, tmpRast, "MAXIMUM_LENGTH", priFld, snpRast)
   printMsg('Rasterized lines are stored as %s.' % tmpRast)
   
   # Set time costs for non-roads to finalize cost surface
   printMsg('Creating final cost surface...')
   if lahOnly:
      # lahOnly has only highways/ramps, so no background value is needed
      arcpy.CopyRaster_management(tmpRast, outCostSurf)
   else:
      cs = Con(IsNull(tmpRast), 0.01233, tmpRast)
      cs.save(outCostSurf)
   
   # Cleanup
   try:
      arcpy.Delete_management(tmpRast)
   except:
      printMsg('Attmempted cleanup, but unable to delete %s.' % tmpRast)
   
   printMsg('Mission accomplished.')
   
   return outCostSurf

############################################################################

# Use the section below to enable a function (or sequence of functions) to be run directly from this free-standing script (i.e., not as an ArcGIS toolbox tool)
def main():
   scratchGDB = r'C:\David\scratch\roads.gdb'
   # all roads cost surface
   inRoads = r'C:\David\projects\va_cost_surface\roads_proc\prep_roads\prep_roads.gdb\all_subset'
   snpRast = r'C:\David\projects\va_cost_surface\snap\Snap_VaLam30.tif'
   outCostSurf = r'C:\David\projects\va_cost_surface\cost_surfaces\costSurf_all.tif'

   CostSurfTravTime(inRoads, snpRast, outCostSurf)
   
   # LAH-only cost surface
   inRoads = r'C:\David\projects\va_cost_surface\roads_proc\prep_roads\prep_roads.gdb\all_subset_only_lah'
   snpRast = r'C:\David\projects\va_cost_surface\snap\Snap_VaLam30.tif'
   outCostSurf = r'C:\David\projects\va_cost_surface\cost_surfaces\costSurf_only_lah.tif'

   CostSurfTravTime(inRoads, snpRast, outCostSurf, lahOnly = True)
   
   # no-LAH cost surface
   inRoads = r'C:\David\projects\va_cost_surface\roads_proc\prep_roads\prep_roads.gdb\all_subset_no_lah'
   snpRast = r'C:\David\projects\va_cost_surface\snap\Snap_VaLam30.tif'
   outCostSurf = r'C:\David\projects\va_cost_surface\cost_surfaces\costSurf_no_lah.tif'

   CostSurfTravTime(inRoads, snpRast, outCostSurf)
   
if __name__ == '__main__':
   main()
