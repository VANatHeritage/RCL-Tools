# ---------------------------------------------------------------------------
# Helper.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creator: Kirsten R. Hazler
# Creation Date: 2017-10-24 
# Last Edit: 2017-12-05

# Summary:
# Imports standard modules, applies standard settings, and defines a collection of helper functions to be called by other scripts.

# Import modules
print 'Importing modules, including arcpy, which takes way longer than it should...'
import arcpy, os, sys, traceback
from datetime import datetime as datetime
from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")
scratchGDB = arcpy.env.scratchGDB
arcpy.env.overwriteOutput = True

def countFeatures(features):
   '''Gets count of features'''
   count = int((arcpy.GetCount_management(features)).getOutput(0))
   return count
   
def garbagePickup(trashList):
   '''Deletes Arc files in list, with error handling. Argument must be a list.'''
   for t in trashList:
      try:
         arcpy.Delete_management(t)
      except:
         pass
   return      
      
def GetElapsedTime (t1, t2):
   """Gets the time elapsed between the start time (t1) and the finish time (t2)."""
   delta = t2 - t1
   (d, m, s) = (delta.days, delta.seconds/60, delta.seconds%60)
   (h, m) = (m/60, m%60)
   deltaString = '%s days, %s hours, %s minutes, %s seconds' % (str(d), str(h), str(m), str(s))
   return deltaString

def printMsg(msg):
   arcpy.AddMessage(msg)
   print msg
   return
   
def printWrng(msg):
   arcpy.AddWarning(msg)
   print 'Warning: ' + msg
   return
   
def printErr(msg):
   arcpy.AddError(msg)
   print 'Error: ' + msg
   return
   
def ProjectToMatch (fcTarget, csTemplate):
   """Project a target feature class to match the coordinate system of a template dataset"""
   # Get the spatial reference of your target and template feature classes
   srTarget = arcpy.Describe(fcTarget).spatialReference # This yields an object, not a string
   srTemplate = arcpy.Describe(csTemplate).spatialReference 

   # Get the geographic coordinate system of your target and template feature classes
   gcsTarget = srTarget.GCS # This yields an object, not a string
   gcsTemplate = srTemplate.GCS

   # Compare coordinate systems and decide what to do from there. 
   if srTarget.Name == srTemplate.Name:
      printMsg('Coordinate systems match; no need to do anything.')
      return fcTarget
   else:
      printMsg('Coordinate systems do not match; proceeding with re-projection.')
      if fcTarget[-3:] == 'shp':
         fcTarget_prj = fcTarget[:-4] + "_prj.shp"
      else:
         fcTarget_prj = fcTarget + "_prj"
      if gcsTarget.Name == gcsTemplate.Name:
         printMsg('Datums are the same; no geographic transformation needed.')
         arcpy.Project_management (fcTarget, fcTarget_prj, srTemplate)
      else:
         printMsg('Datums do not match; re-projecting with geographic transformation')
         # Get the list of applicable geographic transformations
         # This is a stupid long list
         transList = arcpy.ListTransformations(srTarget,srTemplate) 
         # Extract the first item in the list, assumed the appropriate one to use
         geoTrans = transList[0]
         # Now perform reprojection with geographic transformation
         arcpy.Project_management (fcTarget, fcTarget_prj, srTemplate, geoTrans)
      printMsg("Re-projected data is %s." % fcTarget_prj)
      return fcTarget_prj

def TabToDict(inTab, fldKey, fldValue):
   '''Converts two fields in a table to a dictionary'''
   codeDict = {}
   with arcpy.da.SearchCursor(inTab, [fldKey, fldValue]) as sc:
      for row in sc:
         key = sc[0]
         val = sc[1]
         codeDict[key] = val
   return codeDict      

def JoinFields(ToTab, fldToJoin, FromTab, fldFromJoin, addFields):
   '''An alternative to arcpy's JoinField_management, which is unbearably slow.
   
   ToTab = The table to which fields will be added
   fldToJoin = The key field in ToTab, used to match records in FromTab
   FromTab = The table from which fields will be copied
   fldFromJoin = the key field in FromTab, used to match records in ToTab
   addFields = the list of fields to be added'''
   
   codeblock = '''def getFldVal(srcID, fldDict):
      try:
         fldVal = fldDict[srcID]
      except:
         fldVal = None
      return fldVal'''
   
   for fld in addFields:
      printMsg('Working on "%s" field...' %fld)
      fldObject = arcpy.ListFields(FromTab, fld)[0]
      fldDict = TabToDict(FromTab, fldFromJoin, fld)
      printMsg('Established data dictionary.')
      expression = 'getFldVal(!%s!, %s)' % (fldToJoin, fldDict)
      srcFields = arcpy.ListFields(ToTab, fld)
      if len(srcFields) == 0:
         arcpy.AddField_management (ToTab, fld, fldObject.type, '', '', fldObject.length)
      printMsg('Calculating...')
      arcpy.CalculateField_management (ToTab, fld, expression, 'PYTHON', codeblock)
      printMsg('"%s" field done.' %fld)
   return ToTab
   
def SpatialCluster (inFeats, fldID, searchDist, fldGrpID = 'grpID'):
   '''Clusters features based on specified search distance. Features within twice the search distance of each other will be assigned to the same group.
   inFeats = The input features to group
   fldID = The field containing unique feature IDs in inFeats
   searchDist = The search distance to use for clustering. This should be half of the max distance allowed to include features in the same cluster. E.g., if you want features within 500 m of each other to cluster, enter "250 METERS"
   fldGrpID = The desired name for the output grouping field. If not specified, it will be "grpID".'''
   
   # Initialize trash items list
   trashList = []
   
   # Delete the GrpID field from the input features, if it already exists.
   try:
      arcpy.DeleteField_management (inFeats, fldGrpID)
   except:
      pass
      
   # Buffer input features
   printMsg('Buffering input features')
   outBuff = scratchGDB + os.sep + 'outBuff'
   arcpy.Buffer_analysis (inFeats, outBuff, searchDist, '', '', 'ALL')
   trashList.append(outBuff)
   
   # Explode multipart  buffers
   printMsg('Exploding buffers')
   explBuff = scratchGDB + os.sep + 'explBuff'
   arcpy.MultipartToSinglepart_management (outBuff, explBuff)
   trashList.append(explBuff)
   
   # Add and populate grpID field in buffers
   printMsg('Adding and populating grouping field in buffers')
   arcpy.AddField_management (explBuff, fldGrpID, 'LONG')
   arcpy.CalculateField_management (explBuff, fldGrpID, '!OBJECTID!', 'PYTHON')
   
   # Spatial join buffers with input features
   printMsg('Performing spatial join between buffers and input features')
   joinFeats = scratchGDB + os.sep + 'joinFeats'
   arcpy.SpatialJoin_analysis (inFeats, explBuff, joinFeats, 'JOIN_ONE_TO_ONE', 'KEEP_ALL', '', 'WITHIN')
   trashList.append(joinFeats)
   
   # Join grpID field to input features
   # This employs a custom function because arcpy is stupid slow at this
   JoinFields(inFeats, fldID, joinFeats, 'TARGET_FID', [fldGrpID])
   
   # Cleanup: delete buffers, spatial join features
   garbagePickup(trashList)
   
   printMsg('Processing complete.')
   
   return inFeats
   
def tbackInLoop():
   '''Standard error handling routing to add to bottom of scripts'''
   tb = sys.exc_info()[2]
   tbinfo = traceback.format_tb(tb)[0]
   pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
   msgs = arcpy.GetMessages(1)
   msgList = [pymsg, msgs]

   #printWrng(msgs)
   printWrng(pymsg)
   printMsg(msgs)
   
   return msgList
   
def unique_values(table, field):
   ''' Gets list of unique values in a field.
   Thanks, ArcPy Cafe! https://arcpy.wordpress.com/2012/02/01/create-a-list-of-unique-field-values/'''
   with arcpy.da.SearchCursor(table, [field]) as cursor:
      return sorted({row[0] for row in cursor})

##################################################################################################################
# Use the main function below to run a function directly from Python IDE or command line with hard-coded variables

def main():
   # Set up variables
   inFeats = r'E:\ConsVision_RecMod\Terrestrial\Input\TerrestrialFacilities.shp'
   fldID =  'FID'
   searchDist = '250 METERS'
   fldGrpID = 'grpID_500m'
   
   # Specify function to run
   SpatialCluster (inFeats, fldID, searchDist, fldGrpID)

if __name__ == '__main__':
   main()
