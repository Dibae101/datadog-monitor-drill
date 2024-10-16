import requests
import json
import os
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

def fetch_all_standard_monitors():
    """Fetch all standard monitors from Datadog, excluding synthetic monitors."""
    url = f"{datadog_url}/api/v1/monitor"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        all_monitors = response.json()
        standard_monitors = [monitor for monitor in all_monitors if 'synthetics alert' not in monitor.get('type', '').lower()]
        return standard_monitors
    else:
        print(f"Failed to fetch monitors, Status code: {response.status_code}")
        return []

def revert_monitor(monitor_id, backup_data):
    """Revert a standard monitor to its previous state."""
    url = f"{datadog_url}/api/v1/monitor/{monitor_id}"
    response = requests.put(url, headers=headers, json=backup_data)
    
    if response.status_code == 200:
        print(f"Reverted standard monitor ID: {monitor_id} to previous state.")
    else:
        print(f"Failed to revert standard monitor ID: {monitor_id}, Status code: {response.status_code}")
        print(f"Response: {response.text}")

def main():
    # Load the backup JSON file
    backup_filename = input("Enter the filename of the JSON backup to revert from (e.g., previous_backup.json): ")
    with open(backup_filename, 'r') as file:
        backup_data = json.load(file)

    standard_monitors_backup = backup_data if isinstance(backup_data, list) else backup_data.get('standard_monitors', [])

    # Fetch the current state of all standard monitors
    current_standard_monitors = fetch_all_standard_monitors()

    # Revert changes if detected
    for current_monitor in current_standard_monitors:
        current_id = current_monitor.get('id')
        for backup_monitor in standard_monitors_backup:
            if current_id == backup_monitor.get('id'):
                if current_monitor != backup_monitor:
                    print(f"Detected changes in standard monitor ID: {current_id}. Reverting...")
                    revert_monitor(current_id, backup_monitor)
                    break

if __name__ == "__main__":
    main()