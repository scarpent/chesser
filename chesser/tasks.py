import gzip
from datetime import timedelta
from io import StringIO

import boto3
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone


def can_upload_to_s3():
    required = [
        settings.AWS_ACCESS_KEY_ID,
        settings.AWS_SECRET_ACCESS_KEY,
        settings.AWS_STORAGE_BUCKET_NAME,
        settings.AWS_S3_REGION_NAME,
    ]
    return all(required)


def start_scheduler():
    heartbeat_start = timezone.now() + timedelta(
        minutes=settings.HEARTBEAT_STARTUP_DELAY_MINUTES,
    )
    backup_start = timezone.now() + timedelta(
        minutes=settings.BACKUP_STARTUP_DELAY_MINUTES,
    )

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: print("💓 Scheduler heartbeat"),
        "interval",
        hours=settings.HEARTBEAT_INTERVAL_HOURS,
        next_run_time=heartbeat_start,
    )
    scheduler.add_job(
        backup_and_upload,
        "interval",
        hours=settings.BACKUP_INTERVAL_HOURS,
        next_run_time=backup_start,
    )
    scheduler.start()


def upload_to_amazon_s3(local_filepath, s3_object_key, content_type):
    if not can_upload_to_s3():
        print("AWS s3 upload not configured (missing env vars)")
        return False

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        with open(local_filepath, "rb") as upload_file:
            s3_client.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=s3_object_key,
                Body=upload_file,
                ContentType=content_type,
            )
    except Exception as e:
        print(f"❌ Error uploading object key {s3_object_key} to S3: {e}", flush=True)
        return False

    print(f"✌️  Uploaded to s3://{settings.AWS_STORAGE_BUCKET_NAME}/{s3_object_key}")
    return True


def backup():
    buffer = StringIO()
    print("➡️  Running export_db")
    call_command("export_db", stdout=buffer)
    backup_data = buffer.getvalue()
    backup_data_bytes = backup_data.encode("utf-8")

    backup_gzipped_path = "/tmp/chesser_dumpdata.json.gz"
    print(f"💾 Compressing dumpdata ➤ {backup_gzipped_path}")
    with gzip.open(backup_gzipped_path, "wb") as f:
        f.write(backup_data_bytes)

    return backup_gzipped_path, "application/gzip"


def backup_and_upload():
    path_to_backup, content_type = backup()

    if not can_upload_to_s3():
        print("⛔️ s3 not configured; not uploading to AWS; keeping local backup only")
        return False

    datestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    s3_object_key = f"db_backup_{datestamp}.json.gz"
    print("☁️  Uploading DB backup to AWS s3 🪣")

    return upload_to_amazon_s3(path_to_backup, s3_object_key, content_type)
