import time
import json
import subprocess
import os

from datetime import datetime

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

DB_URL = os.environ.get('DB_URL', 'https://influxdb')
DB_TOKEN = os.environ.get('DB_TOKEN', 'changme')
DB_ORG = os.environ.get('DB_ORG', 'org')
DB_BUCKET = os.environ.get('DB_BUCKET', 'speedtest')

DB_RETRY_INVERVAL = int(os.environ.get('DB_RETRY_INVERVAL', 60)) # Time before retrying a failed data upload.

# Speedtest Settings
TEST_INTERVAL = int(os.environ.get('TEST_INTERVAL', 1800))  # Time between tests (in seconds).
TEST_FAIL_INTERVAL = int(os.environ.get('TEST_FAIL_INTERVAL', 60))  # Time before retrying a failed Speedtest (in seconds).

PRINT_DATA = os.environ.get('PRINT_DATA', "True") # Do you want to see the results in your logs? Type must be str. Will be converted to bool.

influxdb_client = InfluxDBClient(url=DB_URL, token=DB_TOKEN)

def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1")

def logger(level, message):
    print(level, ":", datetime.now().strftime("%d/%m/%Y %H:%M:%S"), ":", message)

def format_for_influx(cliout):
    data = json.loads(cliout)
    # There is additional data in the speedtest-cli output but it is likely not necessary to store.
    influx_data = [
        {
            'measurement': 'ping',
            'time': data['timestamp'],
            'fields': {
                'jitter': float(data['ping']['jitter']),
                'latency': float(data['ping']['latency'])
            }
        },
        {
            'measurement': 'download',
            'time': data['timestamp'],
            'fields': {
                # Byte to Megabit
                'bandwidth': data['download']['bandwidth'] / 125000,
                'bytes': data['download']['bytes'],
                'elapsed': data['download']['elapsed']
            }
        },
        {
            'measurement': 'upload',
            'time': data['timestamp'],
            'fields': {
                # Byte to Megabit
                'bandwidth': data['upload']['bandwidth'] / 125000,
                'bytes': data['upload']['bytes'],
                'elapsed': data['upload']['elapsed']
            }
        },
        {
            'measurement': 'packetLoss',
            'time': data['timestamp'],
            'fields': {
                'packetLoss': float(data.get('packetLoss', 0.0))
            }
        }
    ]
    return influx_data

def main():

    while (1):  # Run a Speedtest and send the results to influxDB indefinitely.
        speedtest = subprocess.run(
            ["speedtest", "--accept-license", "--accept-gdpr", "-f", "json"], capture_output=True)

        if speedtest.returncode == 0:  # Speedtest was successful.
            data = format_for_influx(speedtest.stdout)
            logger("Info", "Speedtest successful")
            try:
                write_api = influxdb_client.write_api(write_options=SYNCHRONOUS)
                write_api.write(DB_BUCKET, DB_ORG, data)
                logger("Info", "Data written to DB successfully")
                if str2bool(PRINT_DATA) == True:
                    logger("Info", data)
                time.sleep(TEST_INTERVAL)
            except:
                logger("Error", "Data write to DB failed")
                time.sleep(TEST_FAIL_INTERVAL)
        else:  # Speedtest failed.
            logger("Error", "Speedtest failed")
            logger("Error", speedtest.stderr)
            logger("Info", speedtest.stdout)
            time.sleep(TEST_FAIL_INTERVAL)

if __name__ == '__main__':
    logger('Info', 'Speedtest CLI Data Logger to InfluxDB started')
    main()
