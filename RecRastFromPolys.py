#--------------------------------------------------------------------------------------
# RecRastFromPolys.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-10-27
# Last Edit: 2017-11-06
# Creator:  Kirsten R. Hazler
#
# Summary:
# Creates a summary raster from a set of Network Analyst Service Area polygons.
#
# Usage:
# First create the polygons using RunServiceAreaAnalysisLoop.py
#--------------------------------------------------------------------------------------


##################### User Options #####################

# Input Data: 
# geodatabase containing polygons
inGDB = r'C:\Testing\ConsVisionRecMod\Statewide\na_ServArea\output\trlHds\trlHds.gdb' 
# template raster to set cell size and alignment
inSnap = r'C:\Testing\ConsVisionRecMod\Statewide\cs_TrvTm_2011_lam.tif'

# Output Data
outDir = r'C:\Testing\ConsVisionRecMod\Statewide\na_ServArea\output\trlHds'


################### End User Options ###################


# Import Helper module and functions
import Helper
from Helper import *
from arcpy import env

# Apply environment settings
arcpy.env.snapRaster = inSnap
arcpy.env.cellSize = inSnap
arcpy.env.mask = inSnap
arcpy.env.outputCoordinateSystem = inSnap
arcpy.env.extent = inSnap

# Designate output folder
outFolder = outDir + os.sep + 'raster'
if not os.path.exists(outFolder):
   os.makedirs(outFolder)
else: 
   pass

# Start the timer
t0 = datetime.now()
printMsg('Processing started: %s' % str(t0))

# Set up some output variables
zeroRast = outFolder + os.sep + 'zeros.tif'
sumRast = outFolder + os.sep + 'sum.tif'
tmpRast = outFolder + os.sep + 'tmp.tif'

# Create running zeros and running sum rasters
if arcpy.Exists(zeroRast):
   printMsg('Zero raster already exists. Proceeding to next step...')
else:
   printMsg('Initializing running sum raster with zeros...')
   zeros = CreateConstantRaster(0)
   zeros.save(zeroRast)
   printMsg('Zero raster created.')
arcpy.CopyRaster_management (zeroRast, sumRast)
printMsg('Running sum raster created.')

# Get the list of polygon feature classes in the input GDB
arcpy.env.workspace = inGDB
inPolys = arcpy.ListFeatureClasses ('', 'Polygon')
numPolys = len(inPolys)
printMsg('There are %s polygons to process.' % str(numPolys))

# Initialize counter
myIndex = 1 

# Initialize empty list to store IDs of facility groups that fail to get processed
myFailList = []

# Loop through the polygons, creating rasters and updating running sum raster
for poly in inPolys:
   try:
      printMsg('Working on polygon %s' % str(myIndex))
      # Add and populate value field with 1
      printMsg('Adding and populating raster value field...')
      poly = inGDB + os.sep + poly
      arcpy.AddField_management (poly, 'val', 'SHORT')
      arcpy.CalculateField_management (poly, 'val', 1, 'PYTHON')
      
      # Convert to raster
      printMsg('Converting to raster...')
      arcpy.env.extent = poly
      arcpy.PolygonToRaster_conversion (poly, 'val', tmpRast, 'MAXIMUM_COMBINED_AREA')
      
      # Add to running sum raster and save
      printMsg('Adding to running sum raster...')
      arcpy.env.extent = inSnap
      newSum = CellStatistics ([sumRast, tmpRast], "SUM", "DATA")
      arcpy.CopyRaster_management (newSum, sumRast)
      
      printMsg('Completed polygon %s' % str(myIndex))
   except:
      printMsg('Processing for polygon %s failed.' % str(myIndex))
      tbackInLoop()
      myFailList.append
   finally:
      t1 = datetime.now()
      printMsg('Processing for polygon %s ended at %s' % (str(myIndex), str(t1)))
      myIndex += 1
      
if len(myFailList) > 0:
   num_Fails = len(myFailList)
   printMsg('\nProcess complete, but the following %s facility IDs failed: %s.' % (str(num_Fails), str(myFailList)))
   
# End the timer
t2 = datetime.now()
deltaString = GetElapsedTime(t0, t2)
printMsg('All features completed: %s' % str(t2))
printMsg('Total processing time: %s.' % deltaString)
