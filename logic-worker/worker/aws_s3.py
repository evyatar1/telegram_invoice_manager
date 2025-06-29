import boto3
import io
import os

# Retrieve S3 bucket and region from environment variables
S3_BUCKET = os.getenv("S3_BUCKET")
S3_REGION = os.getenv("S3_REGION")

# Initialize S3 client using credentials from environment variables
# boto3 will automatically look for AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
s3 = boto3.client("s3", region_name=S3_REGION)

def download_to_memory(key: str) -> bytes:
    """Downloads a file from S3 into memory and returns its bytes."""
    try:
        # Get the object from S3
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        # Read its content into a BytesIO object
        buffer = io.BytesIO(obj["Body"].read())
        return buffer.getvalue()
    except Exception as e:
        print(f"Error downloading {key} from S3: {e}")
        return None
