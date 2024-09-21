# Selectively Backup Folder to Google Drive

Have you ever been in a situation where you 
wanted to backup your work or coding folder to google drive? 

Currently you would have to manually go through your folder, copy files that are small 
enough to be backed up online to a separate folder and exclude the large ones. You 
would then have to zip this separate folder and then use the Drive GUI to upload it.
If you're someone that likes to do this often, like daily or even weekly, doing this 
periodically would be tedious and repetitive.

This program automates the process of backing up your work folder, by 
backing up most files and programs inside a zip file which will be uploaded to Google 
Drive. The remaining, excluded files will be sent to an alternate offline location. The files to be backed up offline can be configured on 
the command line by specifying individual file size limits for online backup, stricter 
limits for certain extensions, maximum number of files in a directory (such as 
training datasets) and skipping 
most ".git" or virtualenv folders. 

## Setup

1. Clone this repo.
2. `pip install -r requirements.txt`
3. Setup Google Workspace API by following the [QuickStart Guide](https://developers.google.com/drive/api/quickstart/python) 
4. In the above link, Enable the API, Configure the OAuth consent screen and add 
   yourself as a test user. For both the test user and for enabling API, use your 
   google account, for which you have a drive account where you want to backup your files.
5. In the Google Cloud portal, when you download the credentials, you will see a file 
   named "client_secret_....json". Save this file and later note its location in 
   WORK_DIR property in the .env file, as explained in step 8. Rename this file to "credentials.json". After the first run 
   and authentication, future program executions would occur without browser pop-ups, 
   by using "token.pickle" generated in the first program run- this file is also 
   stored in WORK_DIR. Delete token.pickle if you ever change the "SCOPES" variable in 
   `upload_drive.py` 
6. The first time you run the script, you will be prompted to login to this google 
   account in a browser window. In case you face the "Something Went Wrong" error 
   on trying to sign in, you can copy the special auth link from the terminal and 
   paste it in an incognito/private window and try signing in there.
7. Create a file called ".env" in the root directory of this project.
8. The following properties should be added to the file:
   * WORK_DIR="\<full path of the folder in which credentials.json and token.pickle are>"
   * DEFAULT_DRIVE_FOLDER_ID="\<alphanumeric id of destination gdrive folder>"
   * WORK_BACKUP="\<full path of folder in which large files backed up offline are>"

## Usage

To use this script, run it from the command line and provide the required arguments.

### Required Options

* -d: Relative or absolute path to the work folder to be backed up.

### Optional Options

* -fl: Maximum size of file in MB that is allowed to be backed up online (default: 300 
  MB).
* -ol: Maximum size of zip file in MB that is allowed to be uploaded to drive (default: 
3000 MB).
* -m: Maximum number of files in a directory that is allowed to be uploaded to drive 
(default: 200).
* -s: Specify whether to skip offline backup (default: 0, i.e., do not skip).
* -r: Specify whether to restrict file sizes for certain file types to 20 MB (default: 1,
i.e., restrict).

### Example Usage

`python backup_work_folder.py -d /path/to/work/folder -fl 500 -ol 4000 -m 250 -s 1 -r 0
`

This command will back up the specified work folder, allowing individual files up to 500 
MB in 
size, final zip file to be uploaded to Google Drive limited to 4000 MB in size, and a 
maximum of 250 
files in 
each 
directory. 
Offline backup will be skipped, and type-specific file size restrictions will not be 
applied.

## Additional Information
1. Type-specific file size restrictions, if enabled, will apply a stricter individual 
   file size limit of 20 MB to files with the following extensions: [".mp4", ".mkv", ".
   h5", ".weights"]. This can be configured using secret constants as mentioned in 
   point number 3.
2. The property specifying maximum number of files in a directory (-m) is meant to 
   exclude 
   folders like "train/cat" containing 500 cat images, etc.
3. Code automatically handles excluding ".git" (harcoded) folders from the 
   backup, in 
   cases where the sum of file sizes of all nested files and subfolders of these 
   folders exceeds the normal individual file size limit (-fl). This property cannot 
   be configured on the command line, except by modifying "-fl". It can instead be 
   configured by creating a module called "secret_constants.py" where we define 
   excluded_dirs (list of str- [".git", "venv", etc]), restricted_extensions (list of 
   str), 
   restricted_max_file_size_mb (int)
4. To upload individual files, follow setup instructions and then directly use `python 
upload_drive.py -f path/to/file.txt`
