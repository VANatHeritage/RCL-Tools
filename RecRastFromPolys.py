#--------------------------------------------------------------------------------------
# RecRastFromPolys.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-10-27
# Last Edit: 2017-10-27
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
inSnap = r'H:\Backups\DCR_Work_DellD\ConsVision_VulnMod\DataConsolidation\tiff_lam\cs_TrvTm_2011_lam.tif'

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
arcpy.env.extent = inSnap
arcpy.env.mask = inSnap

# Designate output folder
outFolder = outDir + os.sep + 'raster'
if not os.path.exists(outFolder):
    os.makedirs(outFolder)
else: 
    print('%s subdirectory already exists in the output folder. Exiting.' % outFolder)
    exit()

# Create baseline zero raster
baseline = CreateConstantRaster(0)

# Get the list of relevant features classes in the input GDB

# Initialize counter
myIndex = 1 

# Initialize empty list to store IDs of facility groups that fail to get processed
myFailList = []

# Start the timer
t0 = datetime.now()
printMsg('Processing started: %s' % str(t0))

# For each feature class
   # Add and populate value field with 1
   
   # Convert to raster
   
   # Add to baseline raster
   
   # Update baseline raster