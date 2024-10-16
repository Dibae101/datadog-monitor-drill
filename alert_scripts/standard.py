import requests
import time
import threading
import csv
from datetime import datetime

api_key = "xxxx"
app_key = "xxxx"
datadog_url = "https://us5.datadoghq.com/"

headers = {
    "DD-API-KEY": api_key,
    "DD-APPLICATION-KEY": app_key,
    "Content-Type": "application/json"
}

# CSV file to store the output
csv_filename = 'standard_monitor_results.csv'

def initialize_csv():
    """Initialize the CSV file with headers."""
    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            'MonitorType', 'MonitorName', 'MonitorID', 'OriginalMonitorThreshold', 'ChangedMonitorThreshold',
            'MonitorAlertState', 'MonitorAlertStateTime', 'MonitorOkState', 'MonitorAlertOKStateTime', 
            'Recipient', 'Remarks'
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

def fetch_all_standard_monitors():
    """Fetch all standard monitors from Datadog, excluding synthetic monitors."""
    url = f"{datadog_url}/api/v1/monitor"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        all_monitors = response.json()
        # Filter out synthetic monitors
        standard_monitors = [
            monitor for monitor in all_monitors 
            if monitor.get('type') != 'synthetics alert'
        ]
        return standard_monitors
    else:
        print(f"Failed to fetch monitors, Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return []

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

def simulate_failure_and_revert(monitor):
    """Simulate a failure in the monitor by modifying its query, then revert it."""
    monitor_id = monitor.get("id")
    monitor_name = monitor.get("name")
    original_query = monitor['query']

    if not monitor_id or not monitor_name:
        print(f"Skipping monitor due to missing required fields.")
        return

    print(f"Handling monitor: {monitor_name} (ID: {monitor_id})")

    # Initialize CSV row
    csv_row = {
        'MonitorType': 'Standard',
        'MonitorName': monitor_name,
        'MonitorID': monitor_id,
        'OriginalMonitorThreshold': original_query,
        'ChangedMonitorThreshold': '',
        'MonitorAlertState': '',
        'MonitorAlertStateTime': '',
        'MonitorOkState': '',
        'MonitorAlertOKStateTime': '',
        'Recipient': '',
        'Remarks': ''
    }
    update_csv_row(monitor_id, csv_row)

    # Check initial monitor state
    initial_state, initial_state_time, _ = wait_for_state(monitor_id, 'OK')

    if initial_state != 'OK':
        remarks = 'Monitor not in OK state initially'
        csv_row['Remarks'] = remarks
        update_csv_row(monitor_id, csv_row)
        print(f"Monitor '{monitor_name}' is not in an OK state. Skipping...")
        return

    # Simulate failure by modifying the monitor query to a condition that will always trigger an alert
    changed_query = original_query.replace(">", "<")  # Modify threshold comparison to trigger alert

    # Save to CSV before modification
    csv_row['ChangedMonitorThreshold'] = changed_query
    update_csv_row(monitor_id, csv_row)

    monitor['query'] = changed_query

    # Update the monitor with the modified query to force an alert
    update_response = requests.put(f"{datadog_url}/api/v1/monitor/{monitor_id}", headers=headers, json=monitor)

    if update_response.status_code == 200:
        print(f"Monitor '{monitor_name}' updated to simulate failure. Waiting for the monitor to enter Alert state...")

        # Wait until the monitor enters the Alert state
        alert_state, alert_state_time, recipients = wait_for_state(monitor_id, 'Alert')
        
        if alert_state == 'Alert':
            print(f"Monitor '{monitor_name}' is now in Alert state. Reverting to original configuration...")

            # Save to CSV after entering Alert state
            csv_row['MonitorAlertState'] = 'Alert'
            csv_row['MonitorAlertStateTime'] = alert_state_time
            csv_row['Recipient'] = ', '.join(recipients) if recipients else 'No recipients found'
            update_csv_row(monitor_id, csv_row)

            # Revert the monitor to the original configuration
            monitor['query'] = original_query
            revert_response = requests.put(f"{datadog_url}/api/v1/monitor/{monitor_id}", headers=headers, json=monitor)

            if revert_response.status_code == 200:
                print(f"Reverted monitor '{monitor_name}' to its original configuration.")

                # Wait until the monitor returns to the OK state
                ok_state, ok_state_time, _ = wait_for_state(monitor_id, 'OK')

                if ok_state == 'OK':
                    print(f"Monitor '{monitor_name}' is now back to OK state.")
                    csv_row['MonitorOkState'] = 'OK'
                    csv_row['MonitorAlertOKStateTime'] = ok_state_time
                    csv_row['Remarks'] = 'Monitor reverted and back to OK state'
                    update_csv_row(monitor_id, csv_row)
                else:
                    remarks = 'Monitor did not return to OK state'
                    csv_row['Remarks'] = remarks
                    update_csv_row(monitor_id, csv_row)
                    print(f"Monitor '{monitor_name}' did not return to OK state within the expected time.")
            else:
                remarks = 'Error reverting the monitor'
                csv_row['Remarks'] = remarks
                update_csv_row(monitor_id, csv_row)
                print(f"Error reverting monitor '{monitor_name}': {revert_response.status_code} - {revert_response.text}")
        else:
            remarks = 'Monitor did not enter ALERT state'
            csv_row['Remarks'] = remarks
            update_csv_row(monitor_id, csv_row)
            print(f"Monitor '{monitor_name}' did not enter the Alert state within the expected time.")
    else:
        remarks = 'Error updating the monitor'
        csv_row['Remarks'] = remarks
        update_csv_row(monitor_id, csv_row)
        print(f"Error updating monitor '{monitor_name}' for failure simulation: {update_response.status_code} - {update_response.text}")

def main():
    initialize_csv()

    # Fetch the list of all standard monitors
    monitors = fetch_all_standard_monitors()
    
    if monitors:
        threads = []  # Reset threads list for monitors
        for monitor in monitors:
            thread = threading.Thread(target=simulate_failure_and_revert, args=(monitor,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        print("All standard monitors have been processed.")
    else:
        print("No monitors found or failed to fetch monitors.")

        
if __name__ == "__main__":
    main()