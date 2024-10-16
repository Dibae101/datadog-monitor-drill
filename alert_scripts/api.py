import requests
import time
import threading
import csv
from datetime import datetime

# Datadog API details
api_key = "xxxx"
app_key = "xxxx"
datadog_url = "https://us5.datadoghq.com/"

# Headers for authentication
headers = {
    "DD-API-KEY": api_key,
    "DD-APPLICATION-KEY": app_key,
    "Content-Type": "application/json"
}

fields_to_remove = ['modified_at', 'created_at', 'creator', 'monitor_id', 'public_id']

# CSV file to store the output
csv_filename = 'api_monitor_results.csv'

def initialize_csv():
    """Initialize the CSV file with headers."""
    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            'MonitorType', 'MonitorName', 'MonitorID', 'OriginalMonitorURL', 'ChangedMonitorURL',
            'MonitorAlertState', 'MonitorAlertStateTime', 'MonitorOkState',
            'MonitorAlertOKStateTime', 'Recipient', 'Remarks'
        ])

def update_csv_row(monitor_id, updated_data):
    """Update the CSV row for a specific monitor ID."""
    rows = []
    updated = False

    try:
        with open(csv_filename, mode='r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['MonitorID'] == str(monitor_id):
                    row.update(updated_data)
                    updated = True
                rows.append(row)
    except FileNotFoundError:
        pass  # The CSV file will be created when we write the rows back.

    if not updated:
        rows.append(updated_data)

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

def remove_unnecessary_fields(test):
    """Remove fields that should not be included in the update request."""
    for field in fields_to_remove:
        if field in test:
            del test[field]
    return test

def fetch_monitor_state(monitor_id):
    """Fetch the current state of the monitor."""
    url = f"{datadog_url}/api/v1/monitor/{monitor_id}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        monitor = response.json()
        return monitor.get('overall_state'), monitor.get('message')
    else:
        print(f"Failed to fetch monitor state for ID: {monitor_id}, Status code: {response.status_code}")
        return None, None

def parse_recipients(message):
    """Extract recipients from the monitor's message field."""
    recipients = []
    if message:
        lines = message.split("\n")
        for line in lines:
            if '@' in line:
                recipients.append(line.strip())
    return recipients

def wait_for_state(monitor_id, desired_state, polling_interval=10, max_wait_time=600):
    """Wait until the monitor enters the desired state (e.g., ALERT or OK)."""
    elapsed_time = 0
    state_time = None

    while elapsed_time < max_wait_time:
        current_state, message = fetch_monitor_state(monitor_id)
        print(f"Monitor ID: {monitor_id} is currently in state: {current_state}")
        if current_state == desired_state:
            state_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            recipients = parse_recipients(message)
            return current_state, state_time, recipients
        time.sleep(polling_interval)
        elapsed_time += polling_interval

    print(f"Timed out waiting for monitor ID: {monitor_id} to enter {desired_state} state.")
    return None, None, None

def trigger_synthetic_test(test_public_id, test_name):
    """Manually trigger the synthetic test."""
    trigger_response = requests.post(f"{datadog_url}/api/v1/synthetics/tests/trigger", headers=headers, json={"tests": [{"public_id": test_public_id}]})
    
    if trigger_response.status_code == 200:
        print(f"  Synthetic test '{test_name}' triggered successfully.")
    else:
        print(f"  Error triggering synthetic test '{test_name}': {trigger_response.status_code} - {trigger_response.text}")

def handle_api_test(test):
    test_public_id = test.get('public_id')
    test_name = test.get('name')
    monitor_id = test.get('monitor_id')  # Assuming monitor_id is available in the test data
    
    if not test_public_id or not test_name or not monitor_id:
        print(f"Skipping API test due to missing required fields.")
        return

    original_url = test['config']['request']['url']
    changed_url = "https://invalid-url-for-testing.com"
    remarks = ''

    print(f"Handling API test: {test_name} (ID: {test_public_id})")

    # Initialize CSV row
    csv_row = {
        'MonitorType': 'API',
        'MonitorName': test_name,
        'MonitorID': monitor_id,
        'OriginalMonitorURL': original_url,
        'ChangedMonitorURL': '',
        'MonitorAlertState': '',
        'MonitorAlertStateTime': '',
        'MonitorOkState': '',
        'MonitorAlertOKStateTime': '',
        'Recipient': '',
        'Remarks': ''
    }
    update_csv_row(monitor_id, csv_row)

    # Fetch the initial state of the monitor
    initial_state, initial_state_time, _ = wait_for_state(monitor_id, 'OK')

    if initial_state != 'OK':
        remarks = 'Monitor not in OK state initially'
        csv_row['Remarks'] = remarks
        update_csv_row(monitor_id, csv_row)
        print(f"API test '{test_name}' is not in an OK state. Skipping...")
        return

    # Save to CSV before modification
    csv_row['ChangedMonitorURL'] = changed_url
    update_csv_row(monitor_id, csv_row)

    # Simulate failure by modifying the test URL to an invalid one
    test['config']['request']['url'] = changed_url

    # Remove unnecessary fields before updating
    test = remove_unnecessary_fields(test)

    # Update the test with the modified URL to force a failure
    update_response = requests.put(f"{datadog_url}/api/v1/synthetics/tests/{test_public_id}", headers=headers, json=test)

    if update_response.status_code == 200:
        print(f"Triggering the API test: {test_name}")

        # Immediately trigger the API test to ensure it enters the ALERT state
        trigger_synthetic_test(test_public_id, test_name)

        # Save to CSV after triggering the test
        update_csv_row(monitor_id, csv_row)

        print(f"  API test triggered successfully for '{test_name}'. Waiting for the test to fail and trigger an alert...")

        # Wait until the monitor enters the ALERT state
        alert_state, alert_state_time, recipients = wait_for_state(monitor_id, 'Alert')
        
        if alert_state == 'Alert':
            print(f"API test '{test_name}' is now in ALERT state. Reverting to original configuration...")

            # Save to CSV after entering Alert state
            csv_row['MonitorAlertState'] = 'Alert'
            csv_row['MonitorAlertStateTime'] = alert_state_time
            csv_row['Recipient'] = ', '.join(recipients) if recipients else 'No recipients found'
            update_csv_row(monitor_id, csv_row)

            # Revert the API test to the original configuration
            test['config']['request']['url'] = original_url
            revert_response = requests.put(f"{datadog_url}/api/v1/synthetics/tests/{test_public_id}", headers=headers, json=test)

            if revert_response.status_code == 200:
                print(f"  Reverted '{test_name}' to its original configuration.")

                # Manually trigger the test again to bring it back online
                trigger_synthetic_test(test_public_id, test_name)

                # Wait until the monitor returns to the OK state
                ok_state, ok_state_time, _ = wait_for_state(monitor_id, 'OK')

                if ok_state == 'OK':
                    print(f"API test '{test_name}' is now back to OK state.")
                    csv_row['MonitorOkState'] = 'OK'
                    csv_row['MonitorAlertOKStateTime'] = ok_state_time
                    csv_row['Remarks'] = 'Monitor reverted and back to OK state'
                    update_csv_row(monitor_id, csv_row)
                else:
                    remarks = 'Monitor did not return to OK state'
                    csv_row['Remarks'] = remarks
                    update_csv_row(monitor_id, csv_row)
                    print(f"API test '{test_name}' did not return to OK state within the expected time.")
            else:
                remarks = 'Error reverting the test'
                csv_row['Remarks'] = remarks
                update_csv_row(monitor_id, csv_row)
                print(f"  Error reverting '{test_name}': {revert_response.status_code} - {revert_response.text}")
        else:
            remarks = 'Monitor did not enter ALERT state'
            csv_row['Remarks'] = remarks
            update_csv_row(monitor_id, csv_row)
            print(f"  API test '{test_name}' did not enter the ALERT state within the expected time.")
    else:
        remarks = 'Error updating the test'
        csv_row['Remarks'] = remarks
        update_csv_row(monitor_id, csv_row)
        print(f"  Error updating ‘{test_name}’ for failure simulation: {update_response.status_code} - {update_response.text}")

def main():
    initialize_csv()
    # Fetch the list of synthetic API tests
    synthetics_tests_endpoint = f"{datadog_url}/api/v1/synthetics/tests"
    synthetics_tests_response = requests.get(synthetics_tests_endpoint, headers=headers)

    if synthetics_tests_response.status_code == 200:
        synthetics_tests = synthetics_tests_response.json().get('tests', [])
        threads = []  # Reset threads list for synthetic tests
        for test in synthetics_tests:
            if test['type'] == 'api':  # Ensure only API tests are handled
                thread = threading.Thread(target=handle_api_test, args=(test,))
                threads.append(thread)
                thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        print("All synthetic API tests have been processed.")
    else:
        print(f"Failed to connect to synthetic tests, status code: {synthetics_tests_response.status_code}")
        print("Response:", synthetics_tests_response.text)
        print("\n" + "-"*50 + "\n")

def main():
    initialize_csv()
# Fetch the list of synthetic API tests
    synthetics_tests_endpoint = f"{datadog_url}/api/v1/synthetics/tests"
    synthetics_tests_response = requests.get(synthetics_tests_endpoint, headers=headers)

    if synthetics_tests_response.status_code == 200:
        synthetics_tests = synthetics_tests_response.json().get('tests', [])
        threads = []  # Reset threads list for synthetic tests
        for test in synthetics_tests:
            if test['type'] == 'api':  # Ensure only API tests are handled
                thread = threading.Thread(target=handle_api_test, args=(test,))
                threads.append(thread)
                thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        print("All synthetic API tests have been processed.")
    else:
        print(f"Failed to connect to synthetic tests, status code: {synthetics_tests_response.status_code}")
        print("Response:", synthetics_tests_response.text)
        print("\n" + "-"*50 + "\n")

if __name__ == "__main__":
    main()