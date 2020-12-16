import boto3
import sys
import os
import uuid
import struct
from urllib.parse import unquote_plus
from subprocess import PIPE, run

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])
        tmpkey = key.replace('/', '')
        download_path = '/tmp/{}{}'.format(uuid.uuid4(), tmpkey)
        s3_client.download_file(bucket, key, download_path)
        
        # get images from pdf
        run(['pdfimages', '-png', download_path, '/tmp/image'])
        
        # find right png file
        call = run(['pdfimages', '-list', download_path], stdout=PIPE, universal_newlines=True)
        images = call.stdout.split('\n')
        correct_image = list(filter(lambda e: 'smask' in e, images)) # smask means it's the interest rates
        correct_image_number = '{0:0=3d}'.format(int(correct_image[0].split()[1]))
        correct_file = 'image-' + correct_image_number + '.png'
        
        # upload png to s3
        png_name = key.split('.')[0] + '.png'
        s3_client.upload_file('/tmp/' + correct_file, bucket, png_name)
