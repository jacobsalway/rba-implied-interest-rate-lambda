import cv2
import numpy
import pytesseract
from datetime import datetime
import boto3
import uuid
from urllib.parse import unquote_plus

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

def test_and_convert(lines):
    # make sure only two lines of recognised text
    if len(lines) != 2:
        raise Exception('OCR failed')

    months = lines[0].split(' ')
    rates = lines[1].split(' ')

    # make sure OCR did not miss any months or add any extras
    if len(months) != len(rates):
        print(months)
        print(rates)
        raise Exception('OCR missed text')

    for i in range(len(months)):
        if '-' not in months[i]:
            months[i] = '{}-{}'.format(months[i][:3], months[i][3:])

    for i in range(len(rates)):
        if '.' not in rates[i]:
            rates[i] = '{}.{}'.format(rates[i][0], rates[i][1:])
    
    # test the format of each recognised text row and convert for writing to csv
    # Jan-20, Feb-20 etc. for months
    # 0.040, 0.050 etc. for rates
    try:
        months = list(map(lambda x: datetime.strptime(x, '%b-%y').strftime('%Y-%m-%d'), months))
        rates = list(map(lambda x: str(float(x)), rates))
    except:
        print(months)
        print(rates)
        raise Exception('OCR text does not match expected format')  

    return months, rates

def lambda_handler(event, context):
    for record in event['Records']:
        image_path = download_record(s3_client, record)
        file_name = get_file_name(record)

        image = cv2.imread(image_path, 0)

        image = cv2.bitwise_not(image)

        w, h = tuple(image.shape[1::-1])
        x, y = 0, int(h * 0.9)

        image = image[y:h, 100:]

        mask = image.mean(axis=1) < 50
        image[mask, :] = 255
        mask = image.mean(axis=0) < 125
        image[:, mask] = 255

        image = cv2.bilateralFilter(image, 15, 75, 75)

        # image = cv2.resize(image, None, fx = 2, fy = 2, interpolation = cv2.INTER_LINEAR)

        text = pytesseract.image_to_string(image, lang='eng', config='--oem 2 --psm 6')

        rates, index = text.strip().split('\n')[-2:], 0
        for i, c in enumerate(rates[1]):
            if c.isdigit():
                index = i
                break

        rates[1] = rates[1][index:]

        months, rates = test_and_convert(rates)

        file_date = file_name.split('.')[0]
        final_csv = [[file_date, i, j] for i, j in zip(months, rates)]

        csvname = '/tmp/{}.csv'.format(uuid.uuid4())
        with open(csvname, 'w') as f:
            for row in final_csv:
                f.write(','.join(row))
                f.write('\n')
        
        s3_client.upload_file(csvname, S3_BUCKET, 'csvs/' + file_date + '.csv')