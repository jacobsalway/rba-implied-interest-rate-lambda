import os
import urllib3
import boto3
from datetime import datetime
from dateutil import tz

s3_client = boto3.client('s3')

LOCAL_FILE_SYS = '/tmp'
S3_BUCKET = 'cash-rate'

def _get_key():
    dt_now = datetime.now(tz=tz.gettz('Australia/Sydney'))
    return dt_now.strftime('%Y-%m-%d') + '.pdf'

def get_data():
    url = 'https://www.asx.com.au/data/trt/ib_expectation_curve_graph.pdf'
    http = urllib3.PoolManager()
    try:
        response = http.request('GET', url, retries=urllib3.util.Retry(3))
        return response.data
    except:
        print('ASX pdf error')

def write_data(data, name, loc=LOCAL_FILE_SYS):
    file_name = os.path.join(loc, name)
    with open(file_name, 'wb') as f:
        f.write(data)
    return file_name

def lambda_handler(event, context):
    key = _get_key()
    cashrate_pdf = get_data()
    file_name = write_data(cashrate_pdf, key)
    s3_client.upload_file(file_name, S3_BUCKET, 'pdfs/' + key)