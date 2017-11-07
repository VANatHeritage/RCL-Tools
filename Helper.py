# ---------------------------------------------------------------------------
# Helper.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creator: Kirsten R. Hazler
# Creation Date: 2017-10-24 
# Last Edit: 2017-11-7

# Summary:
# Imports standard modules, applies standard settings, and defines a collection of helper functions to be called by other scripts.

# Import modules
import arcpy, os, sys, traceback
from datetime import datetime as datetime
#from arcpy.sa import *
#arcpy.CheckOutExtension("Spatial")
scratchGDB = arcpy.env.scratchGDB
arcpy.env.overwriteOutput = True

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

def countFeatures(features):
   '''Gets count of features'''
   count = int((arcpy.GetCount_management(features)).getOutput(0))
   return count
   
def unique_values(table, field):
   ''' Gets list of unique values in a field.
   Thanks, ArcPy Cafe! https://arcpy.wordpress.com/2012/02/01/create-a-list-of-unique-field-values/'''
   with arcpy.da.SearchCursor(table, [field]) as cursor:
      return sorted({row[0] for row in cursor})

def TabToDict(inTab, fldKey, fldValue):
   '''Converts two fields in a table to a dictionary'''
   codeDict = {}
   with arcpy.da.SearchCursor(inTab, [fldKey, fldValue]) as sc:
      for row in sc:
         key = sc[0]
         val = sc[1]
         codeDict[key] = val
   return codeDict
      
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
      
def GetElapsedTime (t1, t2):
   """Gets the time elapsed between the start time (t1) and the finish time (t2)."""
   delta = t2 - t1
   (d, m, s) = (delta.days, delta.seconds/60, delta.seconds%60)
   (h, m) = (m/60, m%60)
   deltaString = '%s days, %s hours, %s minutes, %s seconds' % (str(d), str(h), str(m), str(s))
   return deltaString
   