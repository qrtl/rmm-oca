# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import io
import os
from unittest import mock

from botocore.exceptions import ClientError

from odoo.tests.common import TransactionCase

from odoo.addons.attachment_s3.models import ir_attachment as s3_module

S3_ENV = {
    "AWS_ACCESS_KEY_ID": "test-key",
    "AWS_SECRET_ACCESS_KEY": "test-secret",
    "AWS_BUCKETNAME": "test-bucket",
    "AWS_REGION": "ap-northeast-1",
}


class TestAttachmentS3(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Attachment = self.env["ir.attachment"]
        env_patcher = mock.patch.dict(os.environ, S3_ENV)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        session_patcher = mock.patch.object(s3_module.boto3.session, "Session")
        self.session = session_patcher.start()
        self.addCleanup(session_patcher.stop)
        self.client = self.session.return_value.client.return_value
        # The bucket check talks to S3 through a boto3 resource; keep it out.
        bucket_patcher = mock.patch.object(type(self.Attachment), "_get_s3_bucket")
        self.get_s3_bucket = bucket_patcher.start()
        self.addCleanup(bucket_patcher.stop)
        for cache in (s3_module._s3_clients, s3_module._s3_ready_buckets):
            cache.clear()
            self.addCleanup(cache.clear)

    def test_client_reused_within_process(self):
        first = self.Attachment._get_s3_client("test-bucket")
        second = self.Attachment._get_s3_client("test-bucket")
        self.assertIs(first, second)
        self.session.assert_called_once()

    def test_client_not_shared_across_fork(self):
        self.Attachment._get_s3_client("test-bucket")
        with mock.patch.object(s3_module.os, "getpid", return_value=-1):
            self.Attachment._get_s3_client("test-bucket")
        self.assertEqual(self.session.call_count, 2)

    def test_read_is_single_get_object(self):
        self.client.get_object.return_value = {"Body": io.BytesIO(b"image")}
        data = self.Attachment._store_file_read("s3://test-bucket/abc")
        self.assertEqual(data, b"image")
        self.client.get_object.assert_called_once_with(Bucket="test-bucket", Key="abc")
        self.client.head_object.assert_not_called()
        self.get_s3_bucket.assert_not_called()

    def test_read_missing_object_returns_empty(self):
        self.client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )
        self.assertEqual(self.Attachment._store_file_read("s3://test-bucket/abc"), "")

    def test_write_is_put_object_and_checks_bucket_once(self):
        attachment = self.Attachment.with_context(storage_location="s3")
        fname = attachment._store_file_write("abc", b"image")
        attachment._store_file_write("def", b"other")
        self.assertEqual(fname, "s3://test-bucket/abc")
        self.client.put_object.assert_any_call(
            Bucket="test-bucket", Key="abc", Body=b"image"
        )
        self.assertEqual(self.client.put_object.call_count, 2)
        self.get_s3_bucket.assert_called_once_with(name="test-bucket")

    def test_delete_only_in_configured_bucket(self):
        self.Attachment._store_file_delete("s3://other-bucket/abc")
        self.client.delete_object.assert_not_called()
        self.Attachment._store_file_delete("s3://test-bucket/abc")
        self.client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="abc"
        )
        self.client.head_object.assert_not_called()
