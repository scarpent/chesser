import gzip
import os
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest import mock

import pytest

_AWS_TEST_ENV = {
    "AWS_ACCESS_KEY_ID": "AKID_TEST",
    "AWS_SECRET_ACCESS_KEY": "SECRET_TEST",
    "AWS_STORAGE_BUCKET_NAME": "bucket-test",
    "AWS_S3_REGION_NAME": "us-east-1",
}

_AWS_KEYS = list(_AWS_TEST_ENV.keys())


def _set_s3_env(monkeypatch, *, configured: bool):
    """Helper: toggle AWS env vars to make can_upload_to_s3 deterministic."""
    if configured:
        for key, value in _AWS_TEST_ENV.items():
            monkeypatch.setenv(key, value)
    else:
        for key in _AWS_KEYS:
            monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def tasks_module():
    """Import lazily so patches hit the module under test."""
    from chesser import tasks

    return tasks


def test_can_upload_to_s3_false_when_missing_env_vars(tasks_module, monkeypatch):
    _set_s3_env(monkeypatch, configured=False)
    assert tasks_module.can_upload_to_s3() is False


def test_can_upload_to_s3_true_when_all_present(tasks_module, monkeypatch):
    _set_s3_env(monkeypatch, configured=True)
    assert tasks_module.can_upload_to_s3() is True


@mock.patch("chesser.tasks.call_command")
def test_backup_calls_export_db_and_writes_gzipped_json(
    mock_call_command, tasks_module
):
    """backup() should call the export command and gzip whatever it wrote."""

    def fake_call_command(name, stdout):
        assert name == "export_db"
        stdout.write('{"hello": "world"}\n')

    mock_call_command.side_effect = fake_call_command

    path, content_type = tasks_module.backup()
    assert content_type == "application/gzip"

    try:
        with gzip.open(path, "rb") as f:
            assert f.read().decode("utf-8") == '{"hello": "world"}\n'
    finally:
        # Best-effort cleanup if your backup path is stable (often /tmp/...).
        try:
            os.remove(path)
        except OSError:  # pragma: no cover
            pass


def test_upload_to_amazon_s3_returns_false_if_not_configured(
    tasks_module, monkeypatch, tmp_path
):
    _set_s3_env(monkeypatch, configured=False)

    # Even if a file exists, missing env vars should short-circuit before boto3.
    p = tmp_path / "x.gz"
    p.write_bytes(b"abc")

    assert (
        tasks_module.upload_to_amazon_s3(str(p), "k.json.gz", "application/gzip")
        is False
    )


@mock.patch("chesser.tasks.boto3.client")
def test_upload_to_amazon_s3_puts_object(
    mock_boto_client, tasks_module, monkeypatch, tmp_path
):
    _set_s3_env(monkeypatch, configured=True)

    p = tmp_path / "backup.json.gz"
    p.write_bytes(b"abc")

    captured = {}

    def fake_put_object(**kwargs):
        # Read Body while it's still open (inside upload_to_amazon_s3's with-block)
        body = kwargs["Body"]
        captured["bytes"] = body.read()
        captured["kwargs"] = kwargs
        return {"ETag": '"fake"'}

    fake_client = mock.Mock()
    fake_client.put_object = mock.Mock(side_effect=fake_put_object)

    mock_boto_client.return_value = fake_client

    ok = tasks_module.upload_to_amazon_s3(
        str(p),
        "db_backup_20260117_010203.json.gz",
        "application/gzip",
    )

    assert ok is True

    mock_boto_client.assert_called_once_with(
        "s3",
        aws_access_key_id="AKID_TEST",
        aws_secret_access_key="SECRET_TEST",
        region_name="us-east-1",
    )

    fake_client.put_object.assert_called_once()

    kwargs = captured["kwargs"]
    assert kwargs["Bucket"] == "bucket-test"
    assert kwargs["Key"] == "db_backup_20260117_010203.json.gz"
    assert kwargs["ContentType"] == "application/gzip"
    assert captured["bytes"] == b"abc"


@mock.patch("chesser.tasks.boto3.client")
def test_upload_to_amazon_s3_returns_false_on_exception(
    mock_boto_client, tasks_module, monkeypatch, tmp_path, capfd
):
    _set_s3_env(monkeypatch, configured=True)

    p = tmp_path / "backup.json.gz"
    p.write_bytes(b"abc")

    fake_client = mock.Mock()
    fake_client.put_object = mock.Mock(side_effect=RuntimeError("boom"))
    mock_boto_client.return_value = fake_client

    ok = tasks_module.upload_to_amazon_s3(
        str(p),
        "k.json.gz",
        "application/gzip",
    )

    assert ok is False

    out = capfd.readouterr().out
    assert "❌ Error uploading object key k.json.gz to S3:" in out
    assert "boom" in out


@mock.patch("chesser.tasks.BackgroundScheduler")
@mock.patch("chesser.tasks.timezone.now")
def test_start_scheduler_schedules_two_jobs(
    mock_now, mock_scheduler_cls, tasks_module, settings
):
    settings.HEARTBEAT_STARTUP_DELAY_MINUTES = 10
    settings.BACKUP_STARTUP_DELAY_MINUTES = 30
    settings.HEARTBEAT_INTERVAL_HOURS = 6
    settings.BACKUP_INTERVAL_HOURS = 24

    fixed_now = datetime(2026, 1, 17, 12, 0, 0, tzinfo=dt_timezone.utc)
    mock_now.return_value = fixed_now

    scheduler = mock.Mock()
    mock_scheduler_cls.return_value = scheduler

    tasks_module.start_scheduler()

    assert scheduler.add_job.call_count == 2
    scheduler.start.assert_called_once()

    call1 = scheduler.add_job.call_args_list[0]
    call2 = scheduler.add_job.call_args_list[1]

    # Heartbeat job
    func1, trigger1 = call1.args[0], call1.args[1]
    kwargs1 = call1.kwargs
    assert trigger1 == "interval"
    assert kwargs1["hours"] == 6
    assert kwargs1["next_run_time"] == fixed_now + timedelta(minutes=10)
    assert callable(func1)

    # Backup job
    func2, trigger2 = call2.args[0], call2.args[1]
    kwargs2 = call2.kwargs
    assert trigger2 == "interval"
    assert kwargs2["hours"] == 24
    assert kwargs2["next_run_time"] == fixed_now + timedelta(minutes=30)
    assert func2 is tasks_module.backup_and_upload


@mock.patch("chesser.tasks.upload_to_amazon_s3")
@mock.patch("chesser.tasks.can_upload_to_s3", return_value=False)
@mock.patch("chesser.tasks.backup", return_value=("/tmp/x.gz", "application/gzip"))
def test_backup_and_upload_returns_false_when_s3_not_configured(
    mock_backup, mock_can_upload, mock_upload, tasks_module
):
    assert tasks_module.backup_and_upload() is False
    mock_upload.assert_not_called()


@mock.patch("chesser.tasks.upload_to_amazon_s3", return_value=True)
@mock.patch("chesser.tasks.can_upload_to_s3", return_value=True)
@mock.patch("chesser.tasks.backup", return_value=("/tmp/x.gz", "application/gzip"))
@mock.patch("chesser.tasks.timezone.now")
def test_backup_and_upload_uploads_with_datestamped_key(
    mock_now, mock_backup, mock_can_upload, mock_upload, tasks_module
):
    fixed_now = datetime(2026, 1, 17, 1, 2, 3, tzinfo=dt_timezone.utc)
    mock_now.return_value = fixed_now

    assert tasks_module.backup_and_upload() is True
    mock_upload.assert_called_once_with(
        "/tmp/x.gz",
        "db_backup_20260117_010203.json.gz",
        "application/gzip",
    )
