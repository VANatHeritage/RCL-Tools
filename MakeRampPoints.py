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

import Helper
from Helper import *
import arcpy

# create new geodatabase
arcpy.CreateFileGDB_management(r'C:\David\projects\va_cost_surface\rmpts','rmpt_test2.gdb')
wd = r'C:\David\projects\va_cost_surface\rmpts\rmpt_test2.gdb'

# path to Limited access highways
lah = r'C:\David\projects\va_cost_surface\roads_proc\prep_roads\prep_roads.gdb\all_subset_only_lah'
# path to layer excluding limited access highways
local = r'C:\David\projects\va_cost_surface\roads_proc\prep_roads\prep_roads.gdb\all_subset_no_lah'

# make LAH, ramp layers to work with
arcpy.env.workspace = wd
arcpy.env.overwriteOutput = True
arcpy.Select_analysis(lah,'hwy','RmpHwy = 2')
arcpy.Select_analysis(lah,'rmp','RmpHwy = 1')

# identify ramps intersecting highways
base = arcpy.MakeFeatureLayer_management("rmp")
arcpy.SelectLayerByLocation_management(base, "INTERSECT", "hwy","#", "NEW_SELECTION")
cur = arcpy.MakeFeatureLayer_management(base, "cur")

# using selected ramp segements, add intersecting ramps until no new ramps are selected
a = 0
b = 1
while a != b:
   a = int(arcpy.GetCount_management(cur)[0])
   print('start = ' + str(a))
   arcpy.SelectLayerByLocation_management(base,"BOUNDARY_TOUCHES",cur,"#","ADD_TO_SELECTION")
   cur = arcpy.MakeFeatureLayer_management(base, "cur")
   b = int(arcpy.GetCount_management(cur)[0])
   print('end = ' + str(b))

# create all endpoints of ramps
arcpy.FeatureVerticesToPoints_management(cur,"rmpt1","BOTH_ENDS")
rmpt1 = arcpy.MakeFeatureLayer_management("rmpt1")

# select only ramp endpoints intersecting local roads, save as rmpt2
arcpy.Select_analysis(local,"loc",'RmpHwy <> 1')

arcpy.SelectLayerByLocation_management(rmpt1,"INTERSECT","loc")
arcpy.CopyFeatures_management(rmpt1,"rmpt2")

"""
TIGER/Line fix.

Some ramps in the TIGER datasets do not have endpoints at local roads, even though they do connect to them.
The following steps attempt to generate points for that subset of ramps. 
If working with only the Virginia dataset, this section is not necessary, and 'rmpt2' is the final dataset.
"""

# select ramps that touch LAH
arcpy.SelectLayerByLocation_management(base, "BOUNDARY_TOUCHES", "hwy","#", "NEW_SELECTION")
# dump to endpoints
arcpy.FeatureVerticesToPoints_management(base,"rmpt2fix1","BOTH_ENDS")

# select points that do NOT intersect highways - these identify which ramps to unselect in next step
# remaining points should be on both ramps and LAH layer, but not on the LAH themselves
rmpt2fix1 = arcpy.MakeFeatureLayer_management("rmpt2fix1")
arcpy.SelectLayerByLocation_management(rmpt2fix1,"INTERSECT","hwy", "#","NEW_SELECTION", "INVERT")

# un-select ramps intersecting points from above
arcpy.SelectLayerByLocation_management(base,"INTERSECT",rmpt2fix1,"#","REMOVE_FROM_SELECTION")
# remove ramps from Virginia dataset - this fix is only for Tiger datasets
arcpy.SelectLayerByAttribute_management(base, "REMOVE_FROM_SELECTION", "UniqueID LIKE 'VA_%'")

# from these, find intersection points with local roads, then export as single-part
arcpy.Intersect_analysis([base,"loc"], 'rmpt2_nonVAfix1', "ONLY_FID", "#", "POINT")
arcpy.MultipartToSinglepart_management('rmpt2_nonVAfix1', 'rmpt2_nonVAfix2')

# clean up
garbagePickup(['loc','hwy','rmp'])

# NOTE:
# in a previous run-through, some points in the non-VA fix were on ramps that overpass local roads,
# not actually connecting with them. The layer 'rmpt2_nonVAfix2' should be reviewed and those
# points manually deleted prior to merging into the final layer ('rmpt3')

# merge datasets into final ramp points layer
arcpy.Merge_management(["rmpt2","rmpt2_nonVAfix2"],"rmpt3")

# end