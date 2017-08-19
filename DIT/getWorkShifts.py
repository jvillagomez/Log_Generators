import datetime
import uuid
import pycronofy
import boto3

# Notes: This will keep the CW event updated for every shift.
# For it to work initially, user must run script, log into console, and add the trigger manually to the function.
# AWS takes care of addig policy permissions.

# timezone id/token for Cronofy
timezone_id = 'US/Eastern'
cronofy_token = os.environ['CRONOFY_TOKEN']

# ============================================================
# USE: Initializes a cronofy client; needed to query calendar events.
# PARAMS: User acces token.
# OUTPUT: Returns cronofy client object.
def getCronofyClient(User_Token):
    cronofy = pycronofy.Client(access_token=User_Token) # Using a personal token for testing.
    return cronofy

# ============================================================
# USE: Gets the workshift scheduled within the next 24-hr shifts.
# PARAMS: A cronofy client object.
# OUTPUT: Return a shift dictionary {'name','startsAt','endsAt'}, or FALSE if not shifts are scheduled
def getCalendarEvent(client):
    # Date rnage will cover the next 24 hrs [12AM-12AM]
    to_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=52))
    from_date = datetime.datetime.utcnow()
    # calendar id associated to calendar where work events (shifts) are created
    cal_ID = os.environ['UNEX_DITSW_CALENDAR_ID']
    # query the calendar for events (shifts)
    events = client.read_events(calendar_ids=(cal_ID,),
        from_date=from_date,
        to_date=to_date,
        tzid=timezone_id # This argument sets the timezone to local, vs utc.
    ).json()['events'] # convert response to json format to allow us to interact with object

    # ietaret through events looking for the work shift event (incase others types of events are present)
    for event in events:
        if event['organizer']['email']==os.environ['DITSW_EMAIL']:
            shift = {
                "name":event['summary'],
                "startsAt":event['start'],
                "endsAt":event['end']
            }
            return shift
    # return false if no shifts are found in calendar
    return False

# ============================================================
# USE: Creates a CRON time expression for use with AWS CloudWatch
# PARAMS: DateTime string i.e -> '2017-08-19T15:30:00Z'
# OUTPUT: Returns a cron expression string i.e -> cron(30 23 19 08 ? 2017)
def getCronExpression(EndTime):
    # split DateTime string
    month = EndTime[5:7]
    day = EndTime[8:10]
    year = EndTime[0:4]
    hour = EndTime[11:13]
    minute = EndTime[14:16]
    # month = "8"
    # day = "18"
    # year = EndTime[0:4]
    # hour = "4"
    # minute = "5"

    # Create CRON time expression string -> cron(Minutes Hours Day-of-month Month Day-of-week Year)
    cronTimeExpression = " ".join([minute,hour,day,month,"?",year]) # '?' specifies=='Any'
    cronTimeExpression = "cron(" + cronTimeExpression + ")"
    print(cronTimeExpression)
    return cronTimeExpression

# ============================================================
# USE: Posts a new rule to AWS CloudWatch, scheduled using CRON.
# PARAMS: AWS-CW client object, shift dict (containing the shift-end time, trigger time).
# OUTPUT: Outputs the name of the CW rule that was created.
def scheduleCloudWatchTrigger(client,shift):
    # Create corn expression string
    cronEx = getCronExpression(shift['endsAt'])
    # AWS CloudWatch rule name
    triggerName = 'DITlog_trigger'
    # Put an event rule
    response = client.put_rule(
        Name=triggerName,
        RoleArn=os.environ['AWS_ADMINROLE_ARN'],
        ScheduleExpression=cronEx,
        State='ENABLED'
    )
    # returns rule name, to use later in attaching a target
    return triggerName

# ============================================================
# USE: Attaches an AWS Lambda target function to an AWS CloudWatch rule.
# PARAMS: client=AWS-CW client object, trigger=CW rule name
# OUTPUT: Returns the request response dict
def addLambdaTarget(client,trigger):
    response = client.put_targets(
        Rule=trigger,
        Targets=[
            {
                'Arn': os.environ['SENDDITLOG_LAMBDA_ARN'],
                'Id': os.environ['SENDDITLOG_LAMBDA_NAME'],
            }
        ]
    )
    return response

def main():
    # init cronofy client to begin querying Outlook Calendar
    client_obj = getCronofyClient(cronofy_token)
    # grab work shift, if any present for the day
    shift = getCalendarEvent(client_obj)
    # quit the program if no work shifts are scheduled
    if not shift:
        print("No shifts Scheduled today")
        exit
    # Init cloudwatch client to begin interacting with AWS
    cw_client = boto3.client('events')
    # Schedule a cloudwatch event to occur at cronTime
    trigger = scheduleCloudWatchTrigger(cw_client,shift)
    # Attaches a the SendDITLog function to be targeted by cloudwatch trigger
    response = addLambdaTarget(cw_client,trigger)
    if response['FailedEntryCount']==0:
        print('Success placing trigger/target')

    return

if __name__ == '__main__':
    main()
