# -------------------------------------------------------------------------------------------------------
# BatchExtractZipfiles.py
# Version:  Python 2.7.5
# Creation Date: 2015-04-15
# Last Edit: 2018-05-29
# Creator:  Kirsten R. Hazler
#
# Summary:
#     Extracts all zip files within a specified directory, and saves the output to another specified directory.
#
# Usage Tips:
#     This is intended to be run as an ArcGIS tool.
#
# Required Arguments (input by user):
#  ZipDir:  The directory containing the zip files to be extracted
#  OutDir:  The directory in which extracted files will be stored
# -------------------------------------------------------------------------------------------------------

# Import required modules
import zipfile # for handling zipfiles
import os # provides access to operating system funtionality such as file and directory paths
import sys # provides access to Python system functions
import traceback # used for error handling

def BatchExtractZipFiles(ZipDir, OutDir):
   
   # If the output directory does not already exist, create it
   if not os.path.exists(OutDir):
      os.makedirs(OutDir)
   print 'Extracting all files to ' + str(OutDir) + '...'
                                      
   # Set up the processing log                                   
   ProcLog = OutDir + os.sep + "ZipLog.txt"
   log = open(ProcLog, 'w+')
   
   try:
      flist = os.listdir (ZipDir) # Get a list of all items in the input directory
      zfiles = [f for f in flist if '.zip' in f] # This limits the list to zip files
      for zfile in zfiles:
         if zipfile.is_zipfile (ZipDir + os.sep + zfile):
            try:
               zf = zipfile.ZipFile(ZipDir + os.sep + zfile)
               zf.extractall(OutDir)
               log.write('\n' + zfile + ' extracted')
   
            except:
               log.write('\nWarning: Failed to extract %s' % zfile)
               # Error handling code swiped from "A Python Primer for ArcGIS"
               tb = sys.exc_info()[2]
               tbinfo = traceback.format_tb(tb)[0]
               pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
         else: 
            log.write('\nWarning: %s is not a valid zip file' % zfile)
   except:
      # Error handling code swiped from "A Python Primer for ArcGIS"
      tb = sys.exc_info()[2]
      tbinfo = traceback.format_tb(tb)[0]
      pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
   finally:
      log.close()
      

##################################################################################################################
# Use the main function below to run a function directly from Python IDE or command line with hard-coded variables
# Note that this is built-in to BatchDownloadZipFiles (when extract = True), so by default, running this function below is commented out

#def main():
#   # Set up variables 
#   ZipDir = r'C:\bla\folder'
#   OutDir = r'C:\bla\folder\unzip'
#   
#   # Specify function to run
#   BatchExtractZipFiles(ZipDir, OutDir)
#
#if __name__ == '__main__':
#   main()