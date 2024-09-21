import shutil
import os
import argparse
from datetime import datetime
from pathlib import Path
import time

from common_utils import custom_copy, get_file_size_mb
from upload_drive import upload_file, check_and_fetch_env_vars


def validate_folder(folder):
    """
    Checks if folder exists
    """
    if not os.path.isdir(folder):
        raise FileNotFoundError(f"No such directory: {folder}")


def backup_folder(folder, file_size_limit, overall_online_limit, max_files_per_dir, skip_offline_backup,
                  restrict_certain_file_sizes):
    """
        1. Use os walk to traverse every file in work dir
        2. If file is too big or belongs to a folder containing too many files, the filename is logged to offline_backup_files.txt (gitignored)
           Maintaining the same folder structure, this file is copied into offline backup folder, sibling to WORK_DIR
        3. Else copy to online backup folder which will later be zipped and uploaded to google drive
        4. Copy bashrc into online backup folder.
        5. Zip both backup folders and upload the online zip to google drive.
        6. Check if online zip exceeds file size limit, default 3 gb. If so throw an error that this program needs to be modified to become more selective.
        7. Upload zip file. Change folder id to that of new folder created in drive. Delete pre existing backup folders. Check for drive free space
        8. Remove files and folders created by the program on the local system.
    """
    folder = os.path.abspath(folder)
    validate_folder(folder)
    dst_folder_id, offline_backup_dst_folder = check_and_fetch_env_vars(strict=True)[1:]
    if not skip_offline_backup:
        validate_folder(offline_backup_dst_folder)

    parent_folder = Path(folder).resolve().parent
    dt_string = datetime.now().strftime("%d_%m_%Y_%H_%M")  # append to both zips
    online_backup_folder = os.path.join(parent_folder, f"{os.path.basename(folder)}_online_backup")
    online_backup_zip = os.path.join(parent_folder, f"{dt_string}_{os.path.basename(folder)}_online_backup.zip")
    offline_backup_folder = os.path.join(parent_folder, f"{os.path.basename(folder)}_offline_backup")
    offline_backup_zip = os.path.join(parent_folder, f"{os.path.basename(folder)}_offline_backup_{dt_string}.zip")
    print("Deleting pre-existing backup folders...")
    shutil.rmtree(online_backup_folder, ignore_errors=True)
    shutil.rmtree(offline_backup_folder, ignore_errors=True)
    print("Successfully removed!")

    offline_backed_up_files, count = segregate_files_into_online_offline_backup(folder, file_size_limit,
                                                                                max_files_per_dir, skip_offline_backup,
                                                                                offline_backup_folder,
                                                                                online_backup_folder,
                                                                                restrict_certain_file_sizes)

    print(f"Totally {count} files have been copied.")
    # Now all files have been copied to either online or offline backups. Now zip them and upload the online backup zip
    shutil.make_archive(online_backup_zip.split(".")[-2], 'zip', online_backup_folder)
    if get_file_size_mb(online_backup_zip) > overall_online_limit:
        raise ValueError(f"Online backup zip file is too large ({os.path.getsize(online_backup_zip) / (1 << 20)} MB) to be uploaded. \
            Please tighten online backup criteria")
    upload_file(online_backup_zip, 0, dst_folder_id, report_free_space=True)

    if not skip_offline_backup and validate_folder(offline_backup_folder):
        shutil.make_archive(offline_backup_zip.split(".")[-2], 'zip', offline_backup_folder)
    list_offline_files = open(os.path.join(Path(__file__).resolve().parent, "offline_backup_files.txt"), 'w')
    for f in offline_backed_up_files:
        list_offline_files.write(f + '\n')
    list_offline_files.close()
    if not skip_offline_backup:
        print("Copying offline backup zip...")
        custom_copy(offline_backup_zip, os.path.join(offline_backup_dst_folder, os.path.basename(offline_backup_zip)))

    print("Removing both backup zip files")
    Path(offline_backup_zip).unlink(missing_ok=True)
    Path(online_backup_zip).unlink(missing_ok=True)
    print("Program completed successfully. Reminder to delete the older zip file in your google drive.")


def segregate_files_into_online_offline_backup(input_folder: str, file_size_limit: int, max_files_per_dir: int,
                                               skip_offline_backup: int, offline_backup_folder: str,
                                               online_backup_folder: str, restrict_certain_file_sizes: int):
    """
    Segregate files into online and offline backups, refer README for conditions that can be specified on cmd line
    Parameters
    ----------
    input_folder: Work Folder to be backed up
    file_size_limit: (MB) Each individual file or sum of nested sizes in git or virtualenv folders
    max_files_per_dir: Maximum number of files allowed in each directory for online backup
    skip_offline_backup
    offline_backup_folder: Temporary folder for offline backup files before moving to the location defined in .env
    online_backup_folder: Temporary folder for online backup files before being zipped and uploaded to drive
    restrict_certain_file_sizes
    """
    count = 0
    offline_backed_up_files = []
    files_per_path = {}  # stores no. of files in each path in input_folder, key is slash separated

    for path, dirnames, filenames in os.walk(input_folder):
        for src_filename in filenames:
            src_filepath = os.path.join(path, src_filename)
            if not os.path.isfile(src_filepath):
                continue

            subfolder_wrt_input_root = os.path.dirname(os.path.relpath(src_filepath, input_folder))
            file_size_mb = get_file_size_mb(src_filepath)

            if path not in files_per_path:
                files_per_path[path] = len(os.listdir(path))

            # If the total size of all files recursively in the git dir is greater than the normal individual file_size_limit, skip it
            try:
                from secret_constants import excluded_dirs, restricted_extensions, restricted_max_file_size_mb
            except ImportError:
                # default values if secret_constants.py isn't in the project's root dir
                excluded_dirs = [".git"]
                restricted_extensions = [".mp4", ".mkv", ".h5", ".weights"]
                restricted_max_file_size_mb = 20

            is_excluded_dir = False
            for excluded_dir in excluded_dirs:
                is_excluded_dir = recursive_file_size_check(path, file_size_limit, excluded_dir)

            is_restricted_file = False
            # Files ending in restricted_extensions are subject to the lower restricted_max_file_size_mb limit,
            # instead of file_size_limit
            if restrict_certain_file_sizes == 1 and any(
                    x in src_filename for x in restricted_extensions) and file_size_mb > restricted_max_file_size_mb:
                is_restricted_file = True

            if file_size_mb > file_size_limit or files_per_path[
                path] > max_files_per_dir or is_excluded_dir or is_restricted_file:
                offline_backed_up_files.append(src_filepath)
                os.makedirs(os.path.join(offline_backup_folder, subfolder_wrt_input_root), exist_ok=True)
                custom_copy(src_filepath, os.path.join(offline_backup_folder, subfolder_wrt_input_root, src_filename))

            else:
                if not skip_offline_backup:
                    os.makedirs(os.path.join(online_backup_folder, subfolder_wrt_input_root), exist_ok=True)
                    custom_copy(src_filepath,
                                os.path.join(online_backup_folder, subfolder_wrt_input_root, src_filename))

            count += 1
            if count in [1, 2, 100, 200, 500] or count % 1000 == 0:
                print(f"{count} files processed")
    return offline_backed_up_files, count

def recursive_file_size_check(path, file_size_limit, delimiter):
    """
    If the total size of all files recursively in the git dir is greater than the normal individual file_size_limit,
    return True to tell the caller that the folder should be skipped

    Parameters
    ----------
    path: Full path to be checked, part of this path contains the delimiter
    file_size_limit: Normal individual file size limit
    delimiter: .git or venv (virtualenv folder name defiled in .env, fetched by caller)
    """
    if delimiter in path:
        path_upto_git = path.partition(delimiter)[0]
        if sum(f.stat().st_size for f in Path(path_upto_git).glob('**/*') if f.is_file()) / (
                1 << 20) > file_size_limit:
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", required=True, help="Relative or absolute path to work folder to be backed up")
    parser.add_argument("-fl", type=int, default=300,
                        help="Maximum size of file in MB that is allowed to be backed up online, default:%(default)s")
    parser.add_argument("-ol", type=int, default=3000,
                        help="Maximum size of zip file in MB that is allowed to be uploaded to drive, default:%(default)s")
    parser.add_argument("-m", type=int, default=200,
                        help="Maximum number of files in a directory that is allowed to be uploaded to drive, default:%(default)s")
    parser.add_argument("-s", type=int, choices=[0, 1], default=0,
                        help="Specify whether to skip offline backup, default:%(default)s")
    parser.add_argument("-r", type=int, choices=[0, 1], default=1,
                        help="Specify whether to restrict file sizes for certain file types to 20 MB, default:%(default)s")
    args = vars(parser.parse_args())
    start_time = time.time()
    backup_folder(args["d"], args["fl"], args["ol"], args["m"], args["s"], args["r"])
    execution_time = time.time() - start_time
    print(f"Execution time: {execution_time:.2f} seconds")


if __name__ == "__main__":
    main()
