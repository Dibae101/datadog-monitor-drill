import requests
import json

# Datadog API details
api_key = "xxxxx"
app_key = "xxxx"
datadog_url = "https://us5.datadoghq.com/"


# Headers for authentication
headers = {
    "DD-API-KEY": api_key,
    "DD-APPLICATION-KEY": app_key,
    "Content-Type": "application/json"
}

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

def remove_unnecessary_fields(data):
    """Remove fields that should not be included in the update request for synthetic tests."""
    fields_to_remove = ['modified_at', 'created_at', 'creator', 'monitor_id', 'public_id']
    for field in fields_to_remove:
        if field in data:
            del data[field]
    return data

def revert_synthetic_test(test_id, backup_data):
    """Revert a synthetic API test to its previous state."""
    url = f"{datadog_url}/api/v1/synthetics/tests/{test_id}"
    backup_data = remove_unnecessary_fields(backup_data)
    response = requests.put(url, headers=headers, json=backup_data)
    
    if response.status_code == 200:
        print(f"Reverted synthetic API test ID: {test_id} to previous state.")
    else:
        print(f"Failed to revert synthetic API test ID: {test_id}, Status code: {response.status_code}")
        print(f"Response: {response.text}")

def main():
    # Load the backup JSON file
    backup_filename = input("Enter the filename of the JSON backup to revert from (e.g., previous_backup.json): ")
    with open(backup_filename, 'r') as file:
        backup_data = json.load(file)

    synthetic_api_tests_backup = backup_data if isinstance(backup_data, list) else backup_data.get('synthetic_api_tests', [])

    # Fetch the current state of all synthetic API tests
    current_synthetic_api_tests = fetch_all_synthetic_api_tests()

    # Revert changes if detected
    for current_test in current_synthetic_api_tests:
        current_id = current_test.get('public_id')
        for backup_test in synthetic_api_tests_backup:
            if current_id == backup_test.get('public_id'):
                if current_test != backup_test:
                    print(f"Detected changes in synthetic API test ID: {current_id}. Reverting...")
                    revert_synthetic_test(current_id, backup_test)
                    break

if __name__ == "__main__":
    main()