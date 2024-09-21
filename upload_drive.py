from __future__ import print_function

import argparse
import mimetypes
import os
import pickle

from apiclient import errors
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive']
WORK_BACKUP = ""
WORK_DIR = ""
DEFAULT_DRIVE_FOLDER_ID = ""


def trash_file(service, file_id):
    """Move a file in Google Drive to the trash.

    Args:
      service: Drive API service instance.
      file_id: ID of the file to trash.

    Returns:
      The updated file if successful, None otherwise.
    """
    try:
        body = {'trashed': True}
        updated_file = service.files().update(fileId=file_id, body=body).execute()
        return updated_file

    except errors.HttpError as error:
        print('An error occurred: %s' % error)
    return None


def delete_by_filename(service, filename: str):
    """Delete all files matching filename on Google Drive.

    Args:
        service: Drive API service instance.
        filename (str): Filename to delete.
    """
    page_token = None
    delete_file_ids = []
    while True:
        response = service.files().list(q="name='{}'".format(filename),
                                        spaces='drive',
                                        fields='nextPageToken, files(id, name)',
                                        pageToken=page_token).execute()
        for file in response.get('files', []):
            # Process change
            print('Found file: %s (%s)' % (file.get('name'), file.get('id')))
            delete_file_ids.append(file.get('id'))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    for file_id in delete_file_ids:
        trash_file(service, file_id)
        print("Deleted")


def upload_file(filepath_argument: str, delete_existing, destination_drive_folder_id, report_free_space=False):
    check_and_fetch_env_vars()
    filepath = os.path.abspath(filepath_argument)
    _print_file_size(filepath)

    creds = get_credentials()
    service = build('drive', 'v3', credentials=creds)

    if delete_existing:
        delete_by_filename(service, os.path.basename(filepath))

    mime_type = get_mime_type(filepath)
    media = MediaFileUpload(filepath, mimetype=mime_type, resumable=True)
    file_metadata = {'name': os.path.basename(filepath), 'parents': [destination_drive_folder_id]}
    request = service.files().create(media_body=media, body=file_metadata)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print("Uploaded %d%%." % int(status.progress() * 100))
    print("Upload Complete!")

    if report_free_space:
        print_free_space(service)


def _print_file_size(filepath: str):
    file_size = os.path.getsize(filepath)
    print("File Size is :", round(file_size / (1024 * 1024), 2), "MB")


def get_credentials():
    """
    Reads credentials.json stored in directory defined in .env, throws an error if not found
    On first execution opens a browser to allow the user to login, thereby generating token.pickle which stores the
    user's access and refresh tokens for subsequent program runs

    Returns credentials object that can be used to access Drive APIs
    """
    token_pickle_filepath = os.path.join(WORK_DIR, "token.pickle")
    credentials_json_filepath = os.path.join(WORK_DIR, "credentials.json")
    if not os.path.isfile(credentials_json_filepath):
        raise FileNotFoundError(f"credentials.json not found in work directory {WORK_DIR}")
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_pickle_filepath):
        with open(token_pickle_filepath, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_json_filepath, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_pickle_filepath, 'wb') as token:
            pickle.dump(creds, token)
    return creds


def get_mime_type(filepath):
    mt = mimetypes.guess_type(filepath)
    if not mt:
        raise ValueError("Cannot determine Mime Type of {}".format(filepath))
    return mt[0]


def print_free_space(service):
    result = service.about().get(fields="*").execute()
    result = result.get("storageQuota", {})
    print(round(float(result['usageInDrive']) / (1 << 20), 2), "MB remaining in drive")


def check_and_fetch_env_vars(strict=False):
    """
    Function that checks whether all environment variables needed by the program are stored in the .env file
    If so, these environment variables are stored in global variables and returned as a list

    Args:
        strict (bool, optional): Whether to raise an error if environment variable for offline backup is not defined.
        Defaults to False since we don't need it for uploading individual files
    Returns:
        list: List [WORK_DIR, DEFAULT_DRIVE_FOLDER_ID, WORK_BACKUP, venv_folder_name]
        of the environment variables fetched from .env file
    """
    load_dotenv()
    global WORK_DIR, DEFAULT_DRIVE_FOLDER_ID, WORK_BACKUP
    WORK_DIR = os.getenv("WORK_DIR")
    DEFAULT_DRIVE_FOLDER_ID = os.getenv("DEFAULT_DRIVE_FOLDER_ID")
    WORK_BACKUP = os.getenv("WORK_BACKUP")
    if None in (WORK_DIR, DEFAULT_DRIVE_FOLDER_ID):
        raise ValueError("Environment variables not defined")
    if strict and WORK_BACKUP is None:
        raise ValueError("Environment variable for offline work backup not defined")
    return [WORK_DIR, DEFAULT_DRIVE_FOLDER_ID, WORK_BACKUP]


def main():
    check_and_fetch_env_vars()

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", required=True, help="Absolute or relative path of the file to be uploaded")
    parser.add_argument("-p", required=False,
                        help="Parent drive folder's ID in which file is to be uploaded, (default: %(default)s)",
                        default=DEFAULT_DRIVE_FOLDER_ID)

    parser.add_argument("-d", required=False, type=int, choices=[0, 1],
                        help="Specifies whether pre-existing files of the same name should be deleted, (default: %(default)s)",
                        default=0)

    parser.add_argument("-s", required=False, type=int, choices=[0, 1],
                        help="Specifies whether drive free space should be printed (default: %(default)s)", default=0)

    args = vars(parser.parse_args())

    upload_file(args["f"], args["d"], args["p"], args["s"])


if __name__ == '__main__':
    main()
