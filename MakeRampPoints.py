# -*- coding: utf-8 -*-
"""
MakeRampPoints.py
Version:  ArcGIS 10.3.1 / Python 2.7.13
Creator: David Bucklin
Creation Date: 2018-07-19 
Last Edit: 2018-07-23

This script can be used to generate 'ramp points' for use in a raster-based service
area analysis. It generates points at connections between local roads (all non-limited access highways)
and ramps that lead to limited access highways.
"""

from Helper import *

# working geodatabase for cost surfaces should have been created in CostDist.py
project = r'L:\David\projects\RCL_processing\Tiger_2019'
wd = project + os.sep + 'cost_surfaces.gdb'

# path to Limited access highways (make sure to use the ones with the project you want
lah = project + os.sep + 'roads_proc.gdb/all_subset_only_lah'
# path to layer excluding limited access highways
local = project + os.sep + 'roads_proc.gdb/all_subset_no_lah'
## END VARIABLES

# make LAH, ramp layers to work with
arcpy.env.workspace = wd
arcpy.env.overwriteOutput = True
arcpy.Select_analysis(lah, 'hwy', 'RmpHwy = 2')
arcpy.Select_analysis(lah, 'rmp', 'RmpHwy = 1')

# identify ramps intersecting highways
base = arcpy.MakeFeatureLayer_management("rmp")
arcpy.SelectLayerByLocation_management(base, "INTERSECT", "hwy", "#", "NEW_SELECTION")
cur = arcpy.MakeFeatureLayer_management(base, "cur")

# using selected ramp segments, add intersecting ramps until no new ramps are selected
a = 0
b = 1
while a != b:
   a = int(arcpy.GetCount_management(cur)[0])
   arcpy.SelectLayerByLocation_management(base, "BOUNDARY_TOUCHES", cur, "#", "ADD_TO_SELECTION")
   cur = arcpy.MakeFeatureLayer_management(base, "cur")
   b = int(arcpy.GetCount_management(cur)[0])
   print('end = ' + str(b))

# create all endpoints of selected ramps
arcpy.FeatureVerticesToPoints_management(cur, "rmpt1", "BOTH_ENDS")
rmpt1 = arcpy.MakeFeatureLayer_management("rmpt1")

# get local roads only from local (remove ramps)
arcpy.Select_analysis(local, "loc", 'RmpHwy <> 1')
loc = arcpy.MakeFeatureLayer_management("loc")

# select only ramp endpoints intersecting local roads, save as rmpt2
arcpy.SelectLayerByLocation_management(rmpt1, "INTERSECT", "loc")
# arcpy.SelectLayerByLocation_management(rmpt1,"WITHIN_A_DISTANCE","loc", "1 Meters") # use this? Doesn't seem to make much difference in 2011 data
arcpy.CopyFeatures_management(rmpt1, "rmpt2")

## get "dead end" hwy points (transition from LAH to local road without ramp) points
arcpy.Select_analysis(lah, 'hwy_end', 'RmpHwy = 2')
arcpy.Dissolve_management('hwy_end', 'hwy_end_diss', "#", "#", "SINGLE_PART", "UNSPLIT_LINES")
arcpy.FeatureVerticesToPoints_management("hwy_end_diss", "he1", "BOTH_ENDS")
he1 = arcpy.MakeFeatureLayer_management("he1")
rmp = arcpy.MakeFeatureLayer_management("rmp")

# select local roads intersecting lah
arcpy.SelectLayerByLocation_management(loc, "INTERSECT", "hwy_end_diss")
# now select highway end points intersecting those roads
arcpy.SelectLayerByLocation_management(he1, "INTERSECT", loc)
# now remove those intersecting ramps
arcpy.SelectLayerByLocation_management(he1, "INTERSECT", "rmp", "#", "REMOVE_FROM_SELECTION")

# get highway endpoints (where they turn into local roads) 
arcpy.CopyFeatures_management(he1, "hwy_endpts")
arcpy.AddField_management("hwy_endpts", "UniqueID", "TEXT")
arcpy.CalculateField_management("hwy_endpts", "UniqueID", "'HWYEND_' + str(int(!OBJECTID!))", "PYTHON_9.3")

# if not working with TIGER/line at all, this is the final dataset
# arcpy.Merge_management(["rmpt2","hwy_endpts"],"rmpt_final")

"""
TIGER/Line fix.

Some ramps in the TIGER datasets do not have endpoints at local roads, even though they do connect to them.
The following steps attempt to generate points for that subset of ramps. 
"""

# select ramps that touch LAH
arcpy.SelectLayerByLocation_management(base, "BOUNDARY_TOUCHES", "hwy", "#", "NEW_SELECTION")
# dump to endpoints
arcpy.FeatureVerticesToPoints_management(base, "rmpt2fix1", "BOTH_ENDS")

# select points that do NOT intersect highways - these identify which ramps to unselect in next step
# remaining points should be on both ramps and LAH layer, but not on the LAH themselves
rmpt2fix1 = arcpy.MakeFeatureLayer_management("rmpt2fix1")
arcpy.SelectLayerByLocation_management(rmpt2fix1, "INTERSECT", "hwy", "#", "NEW_SELECTION", "INVERT")

# un-select ramps intersecting points from above
arcpy.SelectLayerByLocation_management(base, "INTERSECT", rmpt2fix1, "#", "REMOVE_FROM_SELECTION")
# remove ramps from Virginia dataset - this fix is only for Tiger datasets (if not using VA dataset, leave commented)
# arcpy.SelectLayerByAttribute_management(base, "REMOVE_FROM_SELECTION", "UniqueID LIKE 'VA_%'")

# from these, find intersection points with local roads, then export as single-part
arcpy.Intersect_analysis([base, "loc"], 'rmpt2_nonVAfix1', "ONLY_FID", "#", "POINT")
arcpy.MultipartToSinglepart_management('rmpt2_nonVAfix1', 'rmpt2_nonVAfix2')
arcpy.AddField_management("rmpt2_nonVAfix2", "UniqueID", "TEXT")
arcpy.CalculateField_management("rmpt2_nonVAfix2", "UniqueID", "'NONVAFIX_' + str(int(!FID_rmp!))", "PYTHON_9.3")

# working here: need to review layer
# NOTE:
# in a previous run-through, some points in the non-VA fix were on ramps that overpass local roads,
# not actually connecting with them. The layer 'rmpt2_nonVAfix2' should be reviewed and those
# points manually deleted prior to merging into the final layer below ('rmpt_final')

# merge all datasets into final ramp points layer
arcpy.Merge_management(["rmpt2", "rmpt2_nonVAfix2", "hwy_endpts"], "rmpt_final_all")
arcpy.DeleteIdentical_management('rmpt_final_all', ['UNIQUEID', 'Shape'], '5 Meters')
arcpy.Clip_analysis('rmpt_final_all', r'L:\David\projects\RCL_processing\RCL_processing.gdb\VA_Buff50mi_wgs84', 'rmpt_final')

# clean up
garbagePickup(['loc', 'hwy', 'rmp', 'he1', 'hwy_end', 'hwy_end_diss', 'rmpt1', 'rmpt2_nonVAfix1', 'rmpt2fix1'])

# end
