import uuid
from urllib.parse import unquote_plus

def get_file_name(record):
    key = unquote_plus(record['s3']['object']['key'])
    file_name = key.split('/')[-1]
    
    return file_name

def download_record(s3_client, record):
    bucket = record['s3']['bucket']['name']
    key = unquote_plus(record['s3']['object']['key'])
    tmpkey = key.replace('/', '')
    download_path = '/tmp/{}{}'.format(uuid.uuid4(), tmpkey)
    s3_client.download_file(bucket, key, download_path)

    return download_path