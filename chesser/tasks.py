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

    buffer = StringIO()
    backup_file_path = "/tmp/chesser_dumpdata.json"
    print(f"Running chesser app dumpdata ➤ {backup_file_path}")
    call_command("dumpdata", "chesser", indent=4, stdout=buffer)
    backup_data = buffer.getvalue()

    with open(backup_file_path, "w") as backup_file:
        backup_file.write(backup_data)

    dropbox_dest_path = (
        f"/chesser_dumpdata_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    print("Uploading dumpdata to Dropbox 📦️")

    return upload_to_dropbox(backup_file_path, dropbox_dest_path)
