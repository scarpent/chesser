import gzip
from io import StringIO

import dropbox
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(backup_and_upload, "interval", hours=4)
    scheduler.start()


def upload_to_dropbox(file_path, dropbox_dest_path):
    """
    Upload a file to Dropbox using the Dropbox API.
    :param file_path: The local file path of the file to upload.
    :param dropbox_dest_path: The destination path in Dropbox

    dropbox path needs to start with a forward slash? dropps it into Apps/Chesser
    """
    if not settings.DROPBOX_ACCESS_TOKEN:
        print("DROPBOX_ACCESS_TOKEN not set")
        return False

    dbx = dropbox.Dropbox(settings.DROPBOX_ACCESS_TOKEN)

    with open(file_path, "rb") as f:
        try:
            dbx.files_upload(
                f.read(), dropbox_dest_path, mode=dropbox.files.WriteMode.overwrite
            )
            print(f"File uploaded successfully to {dropbox_dest_path}")
        except dropbox.exceptions.ApiError as e:
            print(f"Error uploading file: {e}")
            return False

    return True


def backup_and_upload():
    if not settings.DROPBOX_ACCESS_TOKEN:
        print("Not running backup for want of a DROPBOX_ACCESS_TOKEN")
        return False

    buffer = StringIO()  # Use BytesIO to hold the compressed data
    print("Running chesser app dumpdata ➤")

    call_command("dumpdata", "chesser", indent=2, stdout=buffer)
    backup_data = buffer.getvalue()
    backup_data_bytes = backup_data.encode("utf-8")

    backup_gzipped_path = "/tmp/chesser_dumpdata.json.gz"
    print(f"Compressing dumpdata ➤ {backup_gzipped_path}")
    with gzip.open(backup_gzipped_path, "wb") as f:
        f.write(backup_data_bytes)

    datestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    dropbox_dest_path = f"/chesser_dumpdata_{datestamp}.json.gz"
    print("Uploading gzipped dumpdata to Dropbox 📦️")

    return upload_to_dropbox(backup_gzipped_path, dropbox_dest_path)
