import requests
import json

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

def fetch_all_synthetic_api_tests():
    """Fetch all synthetic API tests from Datadog."""
    url = f"{datadog_url}/api/v1/synthetics/tests"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        all_tests = response.json().get('tests', [])
        return [test for test in all_tests if test['type'] == 'api']
    else:
        print(f"Failed to fetch synthetic API tests, Status code: {response.status_code}")
        return []

def fetch_all_synthetic_browser_tests():
    """Fetch all synthetic browser tests from Datadog."""
    url = f"{datadog_url}/api/v1/synthetics/tests"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        all_tests = response.json().get('tests', [])
        return [test for test in all_tests if test['type'] == 'browser']
    else:
        print(f"Failed to fetch synthetic browser tests, Status code: {response.status_code}")
        return []

def remove_unnecessary_fields(data):
    """Remove fields that should not be included in the update request for synthetic tests."""
    fields_to_remove = ['modified_at', 'created_at', 'creator', 'monitor_id', 'public_id']
    for field in fields_to_remove:
        if field in data:
            del data[field]
    return data

def revert_monitor(monitor_id, backup_data):
    """Revert a standard monitor to its previous state."""
    url = f"{datadog_url}/api/v1/monitor/{monitor_id}"
    response = requests.put(url, headers=headers, json=backup_data)
    
    if response.status_code == 200:
        print(f"Reverted standard monitor ID: {monitor_id} to previous state.")
    else:
        print(f"Failed to revert standard monitor ID: {monitor_id}, Status code: {response.status_code}")
        print(f"Response: {response.text}")

def revert_synthetic_test(test_id, backup_data):
    """Revert a synthetic test (API or browser) to its previous state."""
    url = f"{datadog_url}/api/v1/synthetics/tests/{test_id}"
    backup_data = remove_unnecessary_fields(backup_data)
    response = requests.put(url, headers=headers, json=backup_data)
    
    if response.status_code == 200:
        print(f"Reverted synthetic test ID: {test_id} to previous state.")
    else:
        print(f"Failed to revert synthetic test ID: {test_id}, Status code: {response.status_code}")
        print(f"Response: {response.text}")

def compare_and_revert(current_items, backup_items, item_type):
    """Compare current items with backup items and revert if changes are detected."""
    for current_item in current_items:
        current_id = current_item.get('id') if item_type == "standard monitor" else current_item.get('public_id')
        for backup_item in backup_items:
            backup_id = backup_item.get('id') if item_type == "standard monitor" else backup_item.get('public_id')
            if current_id == backup_id:
                if current_item != backup_item:
                    print(f"Detected changes in {item_type} ID: {current_id}. Reverting...")
                    if item_type == "standard monitor":
                        revert_monitor(current_id, backup_item)
                    else:
                        revert_synthetic_test(current_id, backup_item)
                    break

def main():
    # Load the backup JSON file
    backup_filename = input("Enter the filename of the JSON backup to revert from (e.g., previous_backup.json): ")
    with open(backup_filename, 'r') as file:
        backup_data = json.load(file)

    # Separate the data from the backup
    standard_monitors_backup = backup_data.get('standard_monitors', [])
    synthetic_api_tests_backup = backup_data.get('synthetic_api_tests', [])
    synthetic_browser_tests_backup = backup_data.get('synthetic_browser_tests', [])

    # Fetch the current state of all monitors and tests
    current_standard_monitors = fetch_all_standard_monitors()
    current_synthetic_api_tests = fetch_all_synthetic_api_tests()
    current_synthetic_browser_tests = fetch_all_synthetic_browser_tests()

    # Compare and revert for standard monitors
    compare_and_revert(current_standard_monitors, standard_monitors_backup, "standard monitor")
    # Compare and revert for synthetic API tests
    compare_and_revert(current_synthetic_api_tests, synthetic_api_tests_backup, "synthetic API test")
    # Compare and revert for synthetic browser tests
    compare_and_revert(current_synthetic_browser_tests, synthetic_browser_tests_backup, "synthetic browser test")

if __name__ == "__main__":
    main()