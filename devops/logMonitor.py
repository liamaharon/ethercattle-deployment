import gzip
import base64
import json
import re
import boto3
import datetime
import os

client = boto3.client('cloudwatch')
MASTER_BLOCK_NUM_RE = re.compile(r"number=(\d+)")
PEER_BLOCK_NUM_RE = re.compile(r"blockNumber: (\d+)")
BLOCK_AGE_RE = re.compile(r"age=(\d+w)?(\d+d)?(\d+h)?(\d+m)?(\d+s)?")
BLOCK_AGE_REP_RE = re.compile(r"blockAge=(\d+w)?(\d+d)?(\d+h)?(\d+m)?(\d+s)?")
BLOCK_NUM_REP_RE = re.compile("num=(\d+)")
OFFSET_NUM_RE = re.compile("offset=(\d+)")
OFFSET_AGE_RE = re.compile(r"offsetAge=(\d+w)?(\d+d)?(\d+h)?(\d+m)?(\d+s)?")
PEER_COUNT_RE = re.compile(r"peerCount: (\d+)")


def numberFromRe(message, regex):
    m = regex.search(message)
    if not m:
        raise ValueError("Message does not match regex")
    return int(m.groups()[0])


def ageFromRe(message, regex):
    m = regex.search(message)
    if not m:
        raise ValueError("Message does not match regex")
    ageSec = 0
    week, day, hour, minute, second = m.groups()
    if week:
        ageSec += int(week[:-1]) * 60 * 60 * 24 * 7
    if day:
        ageSec += int(day[:-1]) * 60 * 60 * 24
    if hour:
        ageSec += int(hour[:-1]) * 60 * 60
    if minute:
        ageSec += int(minute[:-1]) * 60
    if second:
        ageSec += int(second[:-1])
    return ageSec


def appendMetric(item, metricData, metricName, value, unit="None", stream=None):
    dimensions = [
        {
            'Name': 'clusterId',
            'Value': os.environ.get("CLUSTER_ID")
        },
    ]
    if stream:
        dimensions.append({
            'Name': 'instanceId',
            'Value': stream
        })
    metricData.append({
        'MetricName': metricName,
        'Dimensions': dimensions,
        'Timestamp': datetime.datetime.utcfromtimestamp(
            item["timestamp"] / 1000
        ),
        'Value': value,
        'Unit': unit,
    })


def masterHandler(event, context):
    eventData = json.loads(gzip.decompress(base64.b64decode(
        event["awslogs"]["data"])
    ))
    for item in eventData["logEvents"]:
        metricData = []
        try:
            if "Imported new chain segment" in item["message"]:
                appendMetric(item, metricData, "number",
                             numberFromRe(item["message"], MASTER_BLOCK_NUM_RE))
            else:
                appendMetric(item, metricData, "number",
                             numberFromRe(item["message"], PEER_BLOCK_NUM_RE))
        except ValueError:
            pass
        try:
            appendMetric(item, metricData, "age",
                         ageFromRe(item["message"], BLOCK_AGE_RE), "Seconds")
        except ValueError:
            pass
        try:
            appendMetric(item, metricData, "peerCount",
                         numberFromRe(item["message"], PEER_COUNT_RE))
        except ValueError:
            pass

        if metricData:
            client.put_metric_data(
                Namespace='BlockData',
                MetricData=metricData
            )


def replicaHandler(event, context):
    eventData = json.loads(gzip.decompress(base64.b64decode(
        event["awslogs"]["data"])
    ))
    for item in eventData["logEvents"]:
        metricData = []
        try:
            appendMetric(item, metricData, "num",
                         numberFromRe(item["message"], BLOCK_NUM_REP_RE),
                         stream=eventData["logStream"])
            appendMetric(item, metricData, "num",
                         numberFromRe(item["message"], BLOCK_NUM_REP_RE))
        except ValueError:
            pass
        try:
            appendMetric(item, metricData, "age",
                         ageFromRe(item["message"], BLOCK_AGE_REP_RE),
                         "Seconds", stream=eventData["logStream"])
            appendMetric(item, metricData, "age",
                         ageFromRe(item["message"], BLOCK_AGE_REP_RE),
                         "Seconds")
        except ValueError:
            pass
        try:
            appendMetric(item, metricData, "offset",
                         numberFromRe(item["message"], OFFSET_NUM_RE),
                         stream=eventData["logStream"])
            appendMetric(item, metricData, "offset",
                         numberFromRe(item["message"], OFFSET_NUM_RE))
        except ValueError:
            pass
        try:
            appendMetric(item, metricData, "offsetAge",
                         ageFromRe(item["message"], OFFSET_AGE_RE), "Seconds",
                         stream=eventData["logStream"])
            appendMetric(item, metricData, "offsetAge",
                         ageFromRe(item["message"], OFFSET_AGE_RE), "Seconds")
        except ValueError:
            pass

        if metricData:
            client.put_metric_data(
                Namespace='ReplicaData',
                MetricData=metricData
            )
