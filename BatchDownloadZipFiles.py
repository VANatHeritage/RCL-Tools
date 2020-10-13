# -------------------------------------------------------------------------------------------------------
# BatchDownloadZipFiles.py
# Version:  Python 2.7.5
# Creation Date: 2015-07-14
# Last Edit: 2018-05-29
# Creator:  Kirsten R. Hazler
# Credits:  I adapted the FTP-related procedures from code provided by Adam Thom, here:  
# https://gis.stackexchange.com/questions/59047/downloading-multiple-files-from-tiger-ftp-site/
#
# Summary:
#     Downloads a set of zip files from an FTP site.  
#     The file set is determined by a list in a user-provided CSV file, which is assumed to have a header row containing field names.
#
# Usage Tips:
# Recommended default parameters to attach to tools in ArcGIS toolbox are below.  This single script
# can be added to multiple script tools with different defaults.
#
# TIGER/Line Roads data
#     in_fld = 'GEOID' (5-digit code for state/county)
#     pre = 'tl_2014_' (for 2014 data)
#     suf = '_roads.zip' 
#     ftpHOST = 'ftp2.census.gov'
#     ftpDIR = 'geo/tiger/TIGER2014/ROADS'
#
# National Hydrography Dataset (NHD) 
#     in_fld = 'HUC4' (for subregions)
#     pre = 'NHDH' (for high-resolution data)
#           'NHDM' (for medium-resolution data)
#     suf = '_931v220.zip' (for high-resolution data)
#           '_92v200.zip' (for medium-resolution data)
#     ftpHOST = 'nhdftp.usgs.gov'
#     ftpDIR = 'DataSets/Staged/SubRegions/FileGDB/HighResolution'
#              'DataSets/Staged/SubRegions/FileGDB/MediumResolution'
# 
# National Elevation Dataset (NED)
#     in_fld = 'FILE_ID' (assuming this is obtained from reference shapefile ned_1arcsec_g)
#     pre = 'USGS_NED_1_' (for 1 arc-second data)
#     suf = '_ArcGrid.zip' (for ArcGrid format)
#     ftpHOST = 'rockyftp.cr.usgs.gov'
#     ftpDIR = 'vdelivery/Datasets/Staged/Elevation/1/ArcGrid' (for 1 arc-second data)
# -------------------------------------------------------------------------------------------------------

# Import required modules
print 'Importing necessary modules...'
import ftplib # needed to connect to the FTP server and download files
import socket # needed to test FTP connection (or something; I dunno)
import csv # needed to read/write CSV files
import os # provides access to operating system funtionality such as file and directory paths
import sys # provides access to Python system functions
import traceback # used for error handling
import gc # garbage collection
import datetime # for time stamps
from datetime import datetime

def BatchDownloadZips(in_tab, in_fld, out_dir, ftpHOST, ftpDIR, pre = '', suf = '', extract = True):
   '''Downloads a set of zip files from an FTP site.  
      The file set is determined by a list in a user-provided CSV file, which is assumed to have a header row containing field names.
   in_tab = Table (in CSV format) containing unique ID field for the files to retrieve
   in_fld = Field containing the unique ID
   out_dir = Output directory to store downloaded files
   ftpHOST = FTP site
   ftpDIR = FTP directory
   pre = Filename prefix; optional
   suf = Filename suffix; optional'''

   # Create and open a log file.
   # If this log file already exists, it will be overwritten.  If it does not exist, it will be created.
   ProcLogFile = out_dir + os.sep + 'README.txt'
   Log = open(ProcLogFile, 'w+') 
   FORMAT = '%Y-%m-%d %H:%M:%S'
   timestamp = datetime.now().strftime(FORMAT)
   Log.write("Process logging started %s \n" % timestamp)

   # Initialize lists
   FileList = list() # List to hold filenames
   ProcList = list() # List to hold processing results

   # Make a list of the files to download, from the input table
   print 'Reading table...'
   try:
      with open(in_tab, 'r' ) as theFile:
         reader = csv.DictReader(theFile)
         for row in reader:
            fname = pre + row[in_fld] + suf
            FileList.append(fname)
   except:
      Log.write('Unable to parse input table.  Exiting...')
      exit()

   try:
      ftp = ftplib.FTP(ftpHOST)
      msg = "\nCONNECTED TO HOST '%s' \n" % ftpHOST
      print msg
      Log.write(msg)
   except (socket.error, socket.gaierror) as e:
      msg = 'Error: cannot reach "%s" \n' % ftpHOST
      print msg
      Log.write(msg)
      exit()

   try:
      ftp.login()
      print 'Logged in'
   except ftplib.error_perm:
      msg = 'Error: cannot login annonymously \n'
      print msg
      Log.write(msg)
      ftp.quit()
      exit()

   try:
      ftp.cwd(ftpDIR)
      print 'Changed to "%s" folder' %ftpDIR
   except ftplib.error_perm:
      msg = 'Error: cannot CD to "%s" \n' %ftpDIR
      print msg
      Log.write (msg)
      ftp.quit()
      exit()

   # Download the files and save to the output directory, while keeping track of success/failure
   for fileName in FileList:
      try:
         print('Downloading %s ...' % fileName)
         with open(os.path.join(out_dir, fileName), 'wb') as local_file:
            ftp.retrbinary('RETR '+ fileName, local_file.write)
         ProcList.append('Successfully downloaded %s' % fileName)
      except:
         ProcList.append('Failed to download %s' % fileName)

   # Write download results to log.
   for item in ProcList:
      Log.write("%s\n" % item)
    
   timestamp = datetime.now().strftime(FORMAT)
   Log.write("\nProcess logging ended %s" % timestamp)   
   Log.close()
   
   if extract:
      try:
         import BatchExtractZipFiles
         BatchExtractZipFiles.BatchExtractZipFiles(out_dir, out_dir + os.sep + 'unzip')
         print 'All files extracted.'
      except:
         print 'Error unzipping files.'

   return
   
##################################################################################################################
# Use the main function below to run a function directly from Python IDE or command line with hard-coded variables

def main():
   # Set up variables 
   # The following are for TIGER/Line roads data
   in_tab = r'L:\David\projects\RCL_processing\counties.txt'
   in_fld = 'GEOID' #(5-digit code for state/county)
   out_dir = r'L:\David\projects\RCL_processing\Tiger_2007\data'
   ftpHOST = 'ftp2.census.gov'
   ftpDIR = 'geo/tiger/geo/tiger/TIGER2007FE/51_VIRGINIA'
   pre = 'fe_2007_'
   suf = '_edges.zip'
   extract = True
   
   # Specify function to run
   BatchDownloadZips(in_tab, in_fld, out_dir, ftpHOST, ftpDIR, pre, suf, extract)

if __name__ == '__main__':
   main()