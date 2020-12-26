import cv2
import numpy
import pytesseract
from datetime import datetime
import boto3
import uuid
from common import get_file_name, download_record

s3_client = boto3.client('s3')

S3_BUCKET = 'cash-rate'

def preprocess_image(image):
    # invert for black text on white background
    image = cv2.bitwise_not(image)

    # crop to relevant section in lower 10%
    w, h = tuple(image.shape[1::-1])
    x, y = 0, int(h * 0.9)
    image = image[y:h, 100:]

    # take the average grayscale value of each row and column
    # if below a certain threshold, it is a table border so set the row/column to white
    mask = image.mean(axis=1) < 50
    image[mask, :] = 255
    mask = image.mean(axis=0) < 125
    image[:, mask] = 255

    # remove possible noise while keeping edges
    image = cv2.bilateralFilter(image, 15, 75, 75)

    return image

def test_and_convert(lines):
    # make sure only two lines of recognised text
    if len(lines) != 2:
        raise Exception('OCR failed')

    # split into each month
    months, rates = lines[0].split(' '), lines[1].split(' ')

    # make sure OCR did not miss any months or add any extras
    if len(months) != len(rates):
        raise Exception('OCR missed text')
    
    # compensate for possibility of OCR missing hyphens in dates
    # e.g. Apr20 -> Apr-20
    for i in range(len(months)):
        if '-' not in months[i]:
            months[i] = '{}-{}'.format(months[i][:3], months[i][3:])

    # compensate for possibility of OCR missing decimal point in rates
    # e.g. 0410 -> 0.410
    # this will break if ASX changes the number format
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
        raise Exception('OCR text does not match expected format')  

    return months, rates

def lambda_handler(event, context):
    for record in event['Records']:
        image_path = download_record(s3_client, record)
        file_name = get_file_name(record)

        image = cv2.imread(image_path, 0)
        image = preprocess_image(image)

        # --oem 2 means both legacy and LSTM
        # --psm 6 means to treat the whole image as a block of text
        text = pytesseract.image_to_string(image, lang='eng', config='--oem 2 --psm 6')

        # remove any garbage before the rates start
        # by stripping everything before hte first digit
        text, index = text.strip().split('\n')[-2:], 0
        for i, c in enumerate(text[1]):
            if c.isdigit():
                index = i
                break
        text[1] = text[1][index:]

        months, rates = test_and_convert(rates)

        file_date = file_name.split('.')[0]
        final_csv = [[file_date, i, j] for i, j in zip(months, rates)]

        csvname = '/tmp/{}.csv'.format(uuid.uuid4())
        with open(csvname, 'w') as f:
            for row in final_csv:
                f.write(','.join(row))
                f.write('\n')
        
        s3_client.upload_file(csvname, S3_BUCKET, 'csvs/' + file_date + '.csv')