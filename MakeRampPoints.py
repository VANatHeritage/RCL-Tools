# -*- coding: utf-8 -*-
"""
MakeRampPoints.py
Version:  ArcGIS 10.3.1 / Python 2.7.8
Creator: David Bucklin
Creation Date: 2018-07-19 
Last Edit: 2018-07-19

This script can be used to generate 'ramp points' used in a raster-based service
area analysis. It generates a point at connections between local roads (all non-limited access highways)
and ramps leading to limited access highways.
"""

import Helper
from Helper import *
import arcpy

wd = r'C:\David\projects\va_cost_surface\rmpts\rmpt_2017Q3_test.gdb'
arcpy.CreateFileGDB_management(r'C:\David\projects\va_cost_surface\rmpts','rmpt_2017Q3_test.gdb')

lah = r'C:\David\projects\va_cost_surface\roads_proc\prep_roads\prep_roads.gdb\all_subset_only_lah'
local = r'C:\David\projects\va_cost_surface\roads_proc\prep_roads\prep_roads.gdb\all_subset_no_lah'

arcpy.env.workspace = wd
arcpy.env.overwriteOutput = True
arcpy.Select_analysis(lah,'hwy','RmpHwy = 2')
arcpy.Select_analysis(lah,'rmp','RmpHwy = 1')

base = arcpy.MakeFeatureLayer_management("rmp")
arcpy.SelectLayerByLocation_management(base, "INTERSECT", "hwy","#", "NEW_SELECTION")
cur = arcpy.MakeFeatureLayer_management(base, "cur")

# loop until no new ramp segments
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

# select only endpoint intersecting local roads, save as rmpt2
arcpy.Select_analysis(local,"loc",'RmpHwy <> 1')

arcpy.SelectLayerByLocation_management(rmpt1,"INTERSECT","loc")
arcpy.CopyFeatures_management(rmpt1,"rmpt2")

# non-VA fix, for step 2
# select ramps that touch LAH
arcpy.SelectLayerByLocation_management(base, "BOUNDARY_TOUCHES", "hwy","#", "NEW_SELECTION")
# dump to endpoints
arcpy.FeatureVerticesToPoints_management(base,"rmpt2fix1","BOTH_ENDS")

# select points that do NOT intersect highways - these identify which ramps to unselect in next step
# remaining points should be on both ramps and LAH layer, but not on LAH themselves
rmpt2fix1 = arcpy.MakeFeatureLayer_management("rmpt2fix1")
arcpy.SelectLayerByLocation_management(rmpt2fix1,"INTERSECT","hwy", "#","NEW_SELECTION", "INVERT")

# de-select ramps intersecting points from above (should be a small number (~146))
arcpy.SelectLayerByLocation_management(base,"INTERSECT",rmpt2fix1,"#","REMOVE_FROM_SELECTION")
arcpy.SelectLayerByAttribute_management(base, "REMOVE_FROM_SELECTION", "UniqueID LIKE 'VA_%'")
# (should be a small number (~146))
arcpy.GetCount_management(base)

# from these, find intersections with local roads, then export as single-part
arcpy.Intersect_analysis([base,"loc"], 'rmpt2_nonVAfix1', "ONLY_FID", "#", "POINT")
arcpy.MultipartToSinglepart_management('rmpt2_nonVAfix1', 'rmpt2_nonVAfix2')
arcpy.Merge_management(["rmpt2",'rmpt2_nonVAfix2'],"rmpt3")

# end

# NOTE:
# in a previous run-through, some points in the non-VA fix were on ramps that went over local roads
# not connecting with them. These were manually removed. This version of rmpt2_nonVAfix2 is used in Merge below:
# arcpy.Merge_management(["rmpt2",r'C:\David\projects\va_cost_surface\rmpts\rmppt2_nonVAfix2.shp'],"rmpt3")

# end