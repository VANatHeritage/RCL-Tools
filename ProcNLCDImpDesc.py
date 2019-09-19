# ---------------------------------------------------------------------------
# ProcNLCDImpDesc.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creator: David N. Bucklin
# Creation Date: 2019-09-11

# Summary:
# Used to create cost surfaces from NLCD's Impervious Descriptor raster dataset (released with NLCD 2016).
# Both Limited access highways and local (all other roads) cost rasters are output.
# Speeds are assigned in 'Remap' variable; alter this as needed.

# Tiger roads are is used to define limited access highways and ramps. 2018 Tiger was used,
# as this dataset was found to have the better LAH/ramp classification than older datasets (i.e. 2016).
# This information is only used to reclassify the impervious descriptor dataset (it does not "create" roads).

# FIXME: Roads that cross LAH (over/underpass) are not represented in the dataset.
#  SOLUTION: Use focal statistics to fill these areas based on maximum speed in window
# FIXME: Tunnels are not represented in this dataset (as they are not surface roads).
#  SOLUTION: Major tunnels were hand digitized and are burned in to the dataset (see 'burnin_tunnels' feature class)
# ---------------------------------------------------------------------------

# Import Helper module and functions
import Helper
from Helper import *

# Datasets used in script
# NLCD impervious descriptor
imp0 = r'L:\David\GIS_data\NLCD\nlcd_2016\nlcd_2016ed_Impervious_albers.gdb\impDescriptor_2001'
# Tiger/Line roads (only LAH and ramps are used from this dataset, for reclassifying those roads)
road = r'L:\David\projects\RCL_processing\Tiger_2018\roads_proc.gdb\all_centerline'
# Snap raster
snap = imp0  # for now
# burn in tunnels feature class
burn = r'L:\David\projects\RCL_processing\Tiger_2018\roads_proc.gdb\burnin_tunnels'
# Speed remap values (reclassified impervious descriptor class to MPH)
remap = RemapValue([[0, 3], [1, 45], [2, 55], [3, 35], [4, 45], [5, 25], [6, 35],
[11, 45], [12, 55], [13, 35], [14, 45], [15, 25], [16, 35], [101, 60], [102, 70], [103, 50], [104, 60]])
# workspace
arcpy.env.workspace = r'L:\David\projects\vulnerability_model\cost_surfaces\cost_surfaces_2001.gdb'

# create GDB
try:
   arcpy.CreateFileGDB_management(os.path.dirname(arcpy.env.workspace), os.path.basename(arcpy.env.workspace))
except:
   print('GDB already exists')

# Environment settings
arcpy.env.mask = snap
arcpy.env.extent = snap
arcpy.env.cellSize = snap
arcpy.env.snapRaster = snap
arcpy.env.outputCoordinateSystem = snap
arcpy.env.overwriteOutput = True

# Original remap (remove unwanted classes)
remap0 = RemapValue([[0, 0], [1, 1], [2, 2], [3, 3], [4, 4], [5, 5], [6, 6], [9, 0], [10, 0], [11, 0], [12, 0], [127, "NODATA"]])

# original reclass, get rid of unwanted values
arcpy.sa.Reclassify(imp0, "Value", remap0).save("temp_imp0")
# burn in missing roads (tunnels)
burnrast = arcpy.PolylineToRaster_conversion(burn, "rast", "temp_burn")
arcpy.MosaicToNewRaster_management(["temp_imp0", "temp_burn"], arcpy.env.workspace, "temp_imp", number_of_bands=1,
                                   mosaic_method="LAST")  # LAST uses burn values in overlap
imp = "temp_imp"

# process limited access roads/ramps for reclassifying roads in impervious descriptor
lah = arcpy.Select_analysis(road, 'temp_rd', "MTFCC IN ('S1100')")
lah1 = arcpy.Buffer_analysis(lah, 'temp_rd_bufflah', 45, dissolve_option="ALL")
# set LAH areas for Primary/Secondary roads to value of 100
lah2 = arcpy.sa.ExtractByMask(imp, lah1)
arcpy.sa.Reclassify(lah2, "Value", RemapRange([[0, 0, 0], [0.5, 4.5, 100], [4.5, 126, 0]])).save('temp_lah_raster')

# only take ramps that intersect LAH
rmp = arcpy.Select_analysis(road, 'temp_rd', "MTFCC IN ('S1630')")
rmp1 = arcpy.Buffer_analysis(rmp, 'temp_rd_buffrmp', 45, dissolve_option="ALL")
rmp2 = arcpy.MultipartToSinglepart_management(rmp1, 'temp_rd_buffrmp1')
rmp_lyr = arcpy.MakeFeatureLayer_management(rmp2)
arcpy.SelectLayerByLocation_management(rmp_lyr, "INTERSECT", "temp_rd_bufflah", "#", "NEW_SELECTION")

# set all ramp road areas to value of 10
rmp3 = arcpy.sa.ExtractByMask(imp, rmp_lyr)
arcpy.sa.Reclassify(rmp3, "Value", RemapRange([[0, 0, 0], [0.5, 6.5, 10], [6.5, 126, 0]])).save('temp_rmp_raster')

# add LAH/RMP to original raster (values +100 and +10, respectively)
arcpy.sa.CellStatistics(['temp_lah_raster', 'temp_rmp_raster'], "MAXIMUM", "DATA").save('temp_lah_rmp')
arcpy.sa.CellStatistics([imp, 'temp_lah_rmp'], "SUM", "DATA").save('temp_imprcl')

# now set NULL LAH areas
arcpy.sa.SetNull('temp_imprcl', 'temp_imprcl', 'Value > 100').save('temp_imprcl_nolah')
# reclassify values to MPH
arcpy.sa.Reclassify('temp_imprcl_nolah', 'Value', remap).save('temp_mph_local1')
# assign an MPH to NULL LAH areas for the local cost raster (over/under-passes)
arcpy.sa.ExtractByMask(arcpy.sa.FocalStatistics('temp_mph_local1', NbrCircle(3, "CELL"), "MAXIMUM", "DATA"),
                       'temp_lah_raster').save('temp_mph_local2')
# add the two local MPH rasters, convert to cost
arcpy.sa.CellStatistics(['temp_mph_local1', 'temp_mph_local2'], "MAXIMUM", "DATA").save('local_mph')
(0.037 / Raster('local_mph')).save('local_cost')

# now output an LAH-only raster (ramps included)
arcpy.sa.SetNull('temp_imprcl', 'temp_imprcl',
                 'Value NOT IN (11,12,13,14,15,16,101,102,103,104)').save('temp_imprcl_lah')
arcpy.sa.Reclassify('temp_imprcl_lah', 'Value', remap).save('lah_mph')
(0.037 / Raster('lah_mph')).save('lah_cost')

# delete temp, build pyramids
rm = arcpy.ListFeatureClasses("temp_*") + (arcpy.ListRasters("temp_*"))
for r in rm:
   arcpy.Delete_management(r)
arcpy.BuildPyramidsandStatistics_management(arcpy.env.workspace)

## END