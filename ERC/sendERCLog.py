import os
from slackclient import SlackClient
import time
import datetime
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Email server DNS
secureServerName = os.environ['outlook_server']
# Email server Username
secureAcctUsername = os.environ['outlook_username']
# Email server Password
secureAcctPassword = os.environ['outlook_password']
# Slack developer, Access Token
access_token = os.environ['slack_access_token']

# GuestAssistant information
user = { # Placed in a dict, incase other users were added
    "name":"Juan Antonio", # Used in email subject field
    # "channel": "C6GBXMMT8", # Slack Channel ID; unique for each chnnel/user
    "channel": os.environ['slack_channelID'],
    "email": "jvillagomez@ucx.ucr.edu" # used in email "from" field
}

recipients = [
    os.environ['recipient1'],
    os.environ['recipient2'],
    os.environ['recipient3'],
    os.environ['recipient4'],
    os.environ['recipient5'],
    os.environ['recipient6'],
    os.environ['outlook_username']
]

# ============================================================
# USE: Turns epoch timestamps (slack default) into 12-Hour AM/PM strings
# PARAMS: A single epoch timestamp string
# OUTPUT: Returns a single 12hr AM/PM string
def formatTime(timeSinceEpoch):
    timeSinceEpoch = float(timeSinceEpoch)
    # converting UTC time (Slack/AWS default) to Pacific time
    PST_time = datetime.datetime.fromtimestamp(timeSinceEpoch) - datetime.timedelta(hours=7)
    # format date obejct to only keey 'Hours:Minutes'
    hhmmss = PST_time.strftime('%H:%M')

    # TODO find out why I did this
    ampm = hhmmss.split(":")
    if (len(ampm) == 0) or (len(ampm) > 3):
        return hhmmss

    # TODO find out why I did this
    # is AM? from [00:00, 12:00]
    hour = int(ampm[0]) % 24
    isam = (hour >= 0) and (hour < 12)

    # TODO find out why I did this
    # 00:32 should be 12:32 AM not 00:32
    if isam:
        ampm[0] = ('12' if (hour == 0) else "%02d" % (hour))
    else:
        ampm[0] = ('12' if (hour == 12) else "%02d" % (hour-12))

    return ':'.join(ampm) + (' AM' if isam else ' PM')

# ============================================================
# USE: Retrieve messages from user's ERC channel
# PARAMS: Slack-client object, unique slack channelID
# OUTPUT: Returns an array of dictionaries; each dictionary contains one timestamp.
def getChannelMessages(client, channel_ID):
    # GET request for messages, using channelID
    response = client.api_call(
      "channels.history",
      channel=channel_ID
    )
    # Extract messages form response object
    messages = response['messages']
    # Message are by-default in time descending order (need to be ascending)
    messages.reverse()
    # Extract timestamp, formatted timestamp, message text from each message and add to an array that is to be returned
    messages_trimmed = []
    for message in messages:
        message_formatted = {
            "ts":message['ts'],
            "time":formatTime(message['ts']),
            "text":message['text']
        }
        messages_trimmed.append(message_formatted)
    return messages_trimmed

# ============================================================
# USE: Deletes all messages/log-entries in channel
# PARAMS: Slack-client object, unique slack channelID
# OUTPUT: Returns TRUE if channel is reset/emptied; FALSE if channel was not successfully reset.
def deleteSlackMessages(client, channel_ID):
    # retrieve messages thare to be deleted (all in channel)
    messages = getChannelMessages(client, channel_ID)
    # timestamps serve as record IDs in slack DB
    timestamps = [message['ts'] for message in messages]
    # delete each message
    for timestamp in timestamps:
        client.api_call(
            "chat.delete",
            channel=channel_ID,
            ts=timestamp
        )
    # verify that channel is empty; return FALSE if channel was not reset
    messages = getChannelMessages(client, channel_ID)
    if len(messages)==0:
        return False
    return True

# ============================================================
# USE: Parses the log-email to be sent. Both HTML and TEXT versions are sent.
# PARAMS: An array of Slack message objects (dicts), employee dict ('from' email,'subject' name)
# OUTPUT: Returns a dictionary with 'to','from','subject', 'body' text version, 'body' html version
def createERCLogEmail(slackMessages, employee):
    # obtain dates to be used in email subject
    to_date = datetime.datetime.utcnow()
    from_date = (datetime.datetime.utcnow() - datetime.timedelta(days=1))
    # format date time objects to strings
    to_date = to_date.strftime("%d/%Y")
    from_date = from_date.strftime("%m/%d")
    # Parse Subject field value
    subject = "ERC LOG " + from_date + "-" + to_date

    # init HTML and TEXT versions of body field value
    body_html = "<p>" + "<strong>" + subject + "<br><br>GA on Duty:</strong> " + employee['name'] + "</p>" + "<table>"
    body_text = subject + "\nGA on Duty: " + employee['name']

    # Parse a log entry form each individual message
    for logEntry in slackMessages:
        timestamp = logEntry['time']
        text = logEntry['text']

        entry_html = "<tr><td><strong>" + timestamp + "</strong></td>  " + "<td>" + text + "</td></tr>"
        entry_text = "\n" + timestamp + "  " + text

        body_html += entry_html
        body_text += entry_text

    # finalize body field values
    body_html += "</table><br><br><strong>Notes:</strong> Will return radio and GA phone by 09:00 AM.<br><br>Please let me know if you have any questions!<br><br><br>Sincerely,<br><br><br><br>Juan Antonio Villagomez"
    body_text += "\n\nNotes: Will return radio and GA phone by 09:00 AM.\n\nPlease let me know if you have any questions!\n\n\nSincerely,\n\n\n\nJuan Antonio Villagomez"

    # add styling for table borders
    HTMLStyling = "<head><style>table, th, td {border: 1px solid black;}td {padding: 5px;}</style></head>"
    body_html = "<html>" + HTMLStyling + "<body><div>" + body_html + "</div></body></html>"
    # create dict with all email field values
    email = {
        "to":employee['email'],
        "from":employee['email'],
        "subject":subject,
        "body_text":body_text,
        "body_html":body_html
    }
    return email

# ============================================================
# USE: Turns epoch timestamps (slack default) into 12-Hour AM/PM strings
# PARAMS: A single epoch timestamp string
# OUTPUT: Returns a single 12hr AM/PM string
def sendEmail(emailMessage):
    # DNS / credentials for smtp server instance
    servername = secureServerName
    username = secureAcctUsername
    password = secureAcctPassword

    # field values for email object
    from_email = emailMessage['from']
    to_email = recipients
    subject = emailMessage['subject']
    # attach both a html and text version of the email body
    text = emailMessage['body_text']
    html = emailMessage['body_html']

    # init server instance
    server = smtplib.SMTP(servername)
    # view communication
    server.set_debuglevel(True)
    # identify ourselves, prompting server for supported features
    server.ehlo()

    # If we can encrypt this session, do it
    if server.has_extn('STARTTLS'):
        server.starttls()
        # re-identify ourselves over TLS connection
        server.ehlo()

    # attempt to access server
    server.login(username, password)

    # attach email object and send using server instance
    msg = MIMEMultipart('alternative')
    msg.set_unixfrom(from_email)
    msg['To'] = email.utils.formataddr(('', ", ".join(recipients)))
    msg['From'] = email.utils.formataddr(('Juan A. Villagomez', from_email))
    msg['Subject'] = subject

    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')

    msg.attach(part1)
    msg.attach(part2)

    server.sendmail(from_email, to_email, msg.as_string())
    server.quit()

    return

# ============================================================
# Main Function executed on AWS
# def lambda_handler(event, context):
#     # Create slack-client object
#     slackClient = SlackClient(access_token)
#     # query ERC channel for log entries (messages)
#     messages = getChannelMessages(slackClient,user['channel'])
#     # if the channel contains no entries, do nothing
#     if len(messages) == 0:
#         return "No Log Entries"
#
#     # if the channel has entires, create the email object
#     email = createERCLogEmail(messages, user)
#     # send email with log
#     sendEmail(email)
#     # delete entries and reset channel for next the log
#     # deleteSlackMessages(slackClient, user['channel'])
#
#     return "Email Sent"

# Main Function executed locally
def main():
    # Create slack-client object
    slackClient = SlackClient(access_token)
    # query ERC channel for log entries (messages)
    messages = getChannelMessages(slackClient,user['channel'])
    # if the channel contains no entries, do nothing
    if len(messages) == 0:
        return "No Log Entries"

    # if the channel has entires, create the email object
    email = createERCLogEmail(messages, user)
    # send email with log
    sendEmail(email)
    # delete entries and reset channel for next the log
    # deleteSlackMessages(slackClient, user['channel'])

    return "Email Sent"

if __name__ == '__main__':
    main()
