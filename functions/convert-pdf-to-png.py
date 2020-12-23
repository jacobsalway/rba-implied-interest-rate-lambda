import boto3
import uuid
import struct
from urllib.parse import unquote_plus
from subprocess import PIPE, run

s3_client = boto3.client('s3')

S3_BUCKET = 'cash-rate'

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

def lambda_handler(event, context):
    for record in event['Records']:
        download_path = download_record(s3_client, record)
        file_name = get_file_name(record)
        
        # get images from pdf
        image_prefix = str(uuid.uuid4()).replace('-', '')
        run(['pdfimages', '-png', download_path, '/tmp/{}'.format(image_prefix)])
        
        # find right png file
        call = run(['pdfimages', '-list', download_path], stdout=PIPE, universal_newlines=True)
        images = call.stdout.split('\n')
        correct_image = list(filter(lambda e: 'smask' in e, images)) # smask means it's the interest rates
        correct_image_number = '{0:0=3d}'.format(int(correct_image[0].split()[1]))
        correct_file = '{}-'.format(image_prefix) + correct_image_number + '.png'
        
        # upload png to s3
        png_name = file_name.split('.')[0] + '.png'
        s3_client.upload_file('/tmp/' + correct_file, S3_BUCKET, 'pngs/' + png_name)