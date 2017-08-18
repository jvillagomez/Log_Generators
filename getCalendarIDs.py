import pycronofy

# Retrieve all OUTLOOK calendar IDs
if __name__ == '__main__':
    cronofy_token = os.environ['cronofy_token']
    cronofy = pycronofy.Client(access_token=cronofy_token) # Using a personal token for testing.
    outlook_calendars = client.list_calendars()
    for calendar in outlook_calendars:
        print(calendar['calendar_name'])
        print(calendar['calendar_id'])
        print("========================")
