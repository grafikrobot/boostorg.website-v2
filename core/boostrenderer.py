import boto3
from botocore.exceptions import ClientError
import json
from minio import Minio
import os
import re

from django.conf import settings

from mistletoe import HTMLRenderer
from mistletoe.span_token import SpanToken
from pygments import highlight
from pygments.styles import get_style_by_name as get_style
from pygments.lexers import get_lexer_by_name as get_lexer, guess_lexer
from pygments.formatters.html import HtmlFormatter


def get_content_from_s3(key=None, bucket_name=None):
    """
    Get content from S3. Returns the decoded file contents if able. 

    Includes some logic to insert Minio if running locally.
    """
    if not key:
        raise

    if not bucket_name:
        bucket_name = settings.STATIC_CONTENT_BUCKET_NAME

    s3_keys = get_s3_keys(key)

    if not s3_keys:
        s3_keys = [key]

    client = get_s3_client()

    for s3_key in s3_keys:
        try:
            if isinstance(client, Minio):
                response = client.get_object(bucket_name, s3_key.lstrip("/"))
            else:
                response = client.get_object(Bucket=bucket_name, Key=s3_key.lstrip("/"))
            file_content = response["Body"].read()
            content_type = response["ContentType"]
            return file_content, content_type
        except ClientError as e:
            # Log the error and continue with the next key in the list
            pass

        # Handle URLs that are directories looking for `index.html` files
        if s3_key.endswith("/"):
            try:
                original_key = s3_key.lstrip("/")
                index_html_key = f"{original_key}index.html"
                if isinstance(client, Minio):
                    response = client.get_object(bucket_name, index_html_key)
                else:
                    response = client.get_object(Bucket=bucket_name, Key=index_html_key)
                file_content = response["Body"].read()
                content_type = response["ContentType"]
                return file_content, content_type
            except ClientError as e:
                # Log the error and continue with the next key in the list
                pass

    # Return None if no valid object is found
    return None


def get_s3_client():
    """
    Get the S3 client based on the environment
    """
    if settings.LOCAL_DEVELOPMENT:
        return Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL,
        )
    return boto3.client(
        "s3",
        aws_access_key_id=settings.STATIC_CONTENT_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.STATIC_CONTENT_AWS_SECRET_ACCESS_KEY,
        endpoint_url="http://localhost:9000",
        region_name="us-east-1",
    )


def get_s3_keys(content_path, config_filename="stage_static_config.json"):
    """
    Get the S3 key for a given content path
    """
    # Get the config file for the static content URL settings.
    project_root = settings.BASE_DIR
    config_file_path = os.path.join(project_root, config_filename)

    if not content_path.startswith("/"):
        content_path = f"/{content_path}"

    with open(config_file_path, "r") as f:
        config_data = json.load(f)

    s3_keys = []
    for item in config_data:
        site_path = item["site_path"]
        s3_path = item["s3_path"]

        if site_path == "/" and content_path.startswith(site_path):
            if s3_path in content_path:
                s3_keys.append(content_path)
            else:
                s3_keys.append(os.path.join(s3_path, content_path.lstrip("/")))

        elif content_path.startswith(site_path):
            s3_keys.append(content_path.replace(site_path, s3_path))

    return s3_keys


class Youtube(SpanToken):
    """
    Span token for Youtube shortcodes
    Expected shortcode: `[[ youtube | U4VZ9DRdXAI ]]`
    youtube is thrown out but in the shortcode for readability
    """

    pattern = re.compile(r"\[\[ *(.+?) *\| *(.+?) *\]\]")

    def __init__(self, match):
        self.target = match.group(2)


class PygmentsRenderer(HTMLRenderer):
    formatter = HtmlFormatter()
    formatter.noclasses = True

    def __init__(self, *extras, style="solarized-dark"):
        super().__init__(*extras)
        self.formatter.style = get_style(style)

    def render_block_code(self, token):
        code = token.children[0].content
        lexer = get_lexer(token.language) if token.language else guess_lexer(code)
        return highlight(code, lexer, self.formatter)


class BoostRenderer(PygmentsRenderer):
    def __init__(self):
        super().__init__(Youtube)

    def render_youtube(self, token):
        template = '<iframe width="560" height="315" src="https://www.youtube.com/embed/{target}" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>'
        return template.format(target=token.target)
