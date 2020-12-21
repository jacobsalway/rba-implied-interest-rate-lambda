from PIL import Image
import PIL.ImageOps
import pytesseract
from datetime import datetime
import boto3
import uuid
from urllib.parse import unquote_plus

s3_client = boto3.client('s3')

def download_record(s3_client, record):
    bucket = record['s3']['bucket']['name']
    key = unquote_plus(record['s3']['object']['key'])
    tmpkey = key.replace('/', '')
    download_path = '/tmp/{}{}'.format(uuid.uuid4(), tmpkey)
    s3_client.download_file(bucket, key, download_path)

    return download_path

def crop_and_preprocess(image):
    # crop to interest rate text section
    w, h = image.size
    image = image.crop((137, 844, w, h))

    # get rid of one pixel borders that might mess up OCR
    w, h = image.size
    for x in range(w):
        for y in range(h):
            v = image.getpixel((x, y))
            a = image.getpixel((x, y-1)) if y-1 >= 0 else 0
            b = image.getpixel((x+1, y)) if x+1 < w else 0
            c = image.getpixel((x+1, y+1)) if x+1 < w and y+1 < h else 0
            d = image.getpixel((x-1, y)) if x-1 >= 0 else 0
            if v == 255 and ((a,c) == (0, 0) or (b,d) == (0,0)):
                image.putpixel((x,y), 0)

    # invert image so text is black on white
    image = PIL.ImageOps.invert(image)

    return image

def test_and_convert(text):
    lines = text.strip().split('\n')

    # make sure only two lines of recognised text
    if len(lines) != 2:
        raise Exception('OCR failed')

    months = lines[0].split(' ')
    rates = lines[1].split(' ')

    # make sure OCR did not miss any months or add any extras
    if len(months) != 18 or len(rates) != 18:
        raise Exception('OCR missed text')
    
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
        image = Image.open(image_path)
        image = crop_and_preprocess(image)
        text = pytesseract.image_to_string(image) # OCR
        months, rates = test_and_convert(text)

        print(months)
        print(rates)

        # with open('test.csv', 'w') as f:
        #     f.write(','.join(months))
        #     f.write('\n')
        #     f.write(','.join(rates))