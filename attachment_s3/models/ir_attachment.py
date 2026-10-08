# Copyright 2016-2019 Camptocamp SA
# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import logging
import os
import threading
from urllib.parse import urlsplit

from odoo import _, api, exceptions, models

from ..s3uri import S3Uri

_logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError, EndpointConnectionError
except ImportError:
    boto3 = None  # noqa
    ClientError = None  # noqa
    EndpointConnectionError = None  # noqa
    _logger.debug("Cannot 'import boto3'.")

# Building a boto3 client loads the service model and resolves credentials,
# which costs far more than the request itself, so one client is kept per set
# of connection parameters. Clients are thread-safe but must not cross a fork
# (the prefork server forks its workers), hence the process id in the key.
_s3_clients = {}
# Buckets already checked (and created when missing) by this process.
_s3_ready_buckets = set()
_s3_lock = threading.Lock()


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _get_stores(self):
        return ["s3"] + super()._get_stores()

    @api.model
    def _get_s3_bucket_name(self, name=None):
        bucket_name = name or os.environ.get("AWS_BUCKETNAME")
        if bucket_name:
            # replaces {db} by the database name to handle multi-tenancy
            bucket_name = bucket_name.format(db=self.env.cr.dbname)
        return bucket_name

    @api.model
    def _get_s3_connection_params(self, bucket_name):
        """Return the boto3 connection parameters from the environment

        Raise a UserError when the credentials or the bucket name are missing.
        """
        host = os.environ.get("AWS_HOST")

        # Ensure host is prefixed with a scheme (use https as default)
        if host and not urlsplit(host).scheme:
            host = "https://%s" % host

        region_name = os.environ.get("AWS_REGION")
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

        params = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
        }
        if host:
            params["endpoint_url"] = host
        if region_name:
            params["region_name"] = region_name
        if not (access_key and secret_key and bucket_name):
            msg = _(
                "If you want to read from the %(bucket_name)s S3 bucket, the following "
                "environment variables must be set:\n"
                "* AWS_ACCESS_KEY_ID\n"
                "* AWS_SECRET_ACCESS_KEY\n"
                "If you want to write in the %(bucket_name)s S3 bucket, this variable "
                "must be set as well:\n"
                "* AWS_BUCKETNAME\n"
                "Optionally, the S3 host can be changed with:\n"
                "* AWS_HOST\n"
            ).format(bucket_name=bucket_name)

            raise exceptions.UserError(msg)
        return params

    @api.model
    def _get_s3_client(self, bucket_name):
        """Return the S3 client of this process for the configured connection"""
        params = self._get_s3_connection_params(bucket_name)
        key = (os.getpid(),) + tuple(sorted(params.items()))
        client = _s3_clients.get(key)
        if client is None:
            with _s3_lock:
                client = _s3_clients.get(key)
                if client is None:
                    # A session of its own: creating clients from boto3's
                    # shared default session is not thread-safe.
                    client = boto3.session.Session().client("s3", **params)
                    _s3_clients[key] = client
        return client

    @api.model
    def _get_s3_bucket(self, name=None):
        """Connect to S3 and return the bucket

        The following environment variables can be set:
        * ``AWS_HOST``
        * ``AWS_REGION``
        * ``AWS_ACCESS_KEY_ID``
        * ``AWS_SECRET_ACCESS_KEY``
        * ``AWS_BUCKETNAME``

        If a name is provided, we'll read this bucket, otherwise, the bucket
        from the environment variable ``AWS_BUCKETNAME`` will be read.

        """
        bucket_name = self._get_s3_bucket_name(name)
        params = self._get_s3_connection_params(bucket_name)
        # try:
        s3 = boto3.resource("s3", **params)
        bucket = s3.Bucket(bucket_name)
        exists = True
        try:
            s3.meta.client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                exists = False
        except EndpointConnectionError as error:
            # log verbose error from s3, return short message for user
            _logger.exception("Error during connection on S3")
            raise exceptions.UserError(str(error)) from None

        if not exists:
            region_name = params.get("region_name")
            if not region_name:
                bucket = s3.create_bucket(Bucket=bucket_name)
            else:
                bucket = s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": region_name},
                )
        return bucket

    @api.model
    def _ensure_s3_bucket(self, bucket_name):
        """Check the bucket, creating it when missing, once per process"""
        key = (os.getpid(), bucket_name)
        if key not in _s3_ready_buckets:
            self._get_s3_bucket(name=bucket_name)
            _s3_ready_buckets.add(key)

    @api.model
    def _store_file_read(self, fname):
        if fname.startswith("s3://"):
            s3uri = S3Uri(fname)
            try:
                client = self._get_s3_client(s3uri.bucket())
            except exceptions.UserError:
                _logger.exception(
                    "error reading attachment '%s' from object storage", fname
                )
                return ""
            try:
                # One GetObject request. download_fileobj() would add a
                # HeadObject of its own and start a thread pool per file.
                response = client.get_object(Bucket=s3uri.bucket(), Key=s3uri.item())
                read = response["Body"].read()
            except ClientError:
                read = ""
                _logger.info("attachment '%s' missing on object storage", fname)
            except EndpointConnectionError:
                read = ""
                _logger.exception(
                    "error reading attachment '%s' from object storage", fname
                )
            return read
        else:
            return super()._store_file_read(fname)

    @api.model
    def _store_file_write(self, key, bin_data):
        location = self.env.context.get("storage_location") or self._storage()
        if location == "s3":
            bucket_name = self._get_s3_bucket_name()
            client = self._get_s3_client(bucket_name)
            self._ensure_s3_bucket(bucket_name)
            filename = "s3://%s/%s" % (bucket_name, key)
            try:
                client.put_object(Bucket=bucket_name, Key=key, Body=bin_data)
            except ClientError as error:
                # log verbose error from s3, return short message for user
                _logger.exception("Error during storage of the file %s" % filename)
                raise exceptions.UserError(
                    _("The file could not be stored: %s") % str(error)
                ) from None
        else:
            _super = super()
            filename = _super._store_file_write(key, bin_data)
        return filename

    @api.model
    def _store_file_delete(self, fname):
        if fname.startswith("s3://"):
            s3uri = S3Uri(fname)
            bucket_name = s3uri.bucket()
            item_name = s3uri.item()
            # delete the file only if it is on the current configured bucket
            # otherwise, we might delete files used on a different environment
            if bucket_name == os.environ.get("AWS_BUCKETNAME"):
                client = self._get_s3_client(bucket_name)
                try:
                    # Deleting a missing key succeeds, so no HeadObject first.
                    client.delete_object(Bucket=bucket_name, Key=item_name)
                    _logger.info("file %s deleted on the object storage" % (fname,))
                except ClientError:
                    # log verbose error from s3, return short message for
                    # user
                    _logger.exception("Error during deletion of the file %s" % fname)
        else:
            return super()._store_file_delete(fname)
