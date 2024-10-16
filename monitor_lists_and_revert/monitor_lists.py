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

def fetch_all_monitors():
    """Fetch all standard monitors (excluding synthetic monitors) from Datadog."""
    url = f"{datadog_url}/api/v1/monitor"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        all_monitors = response.json()
        # Filter out synthetic monitors
        standard_monitors = [
            monitor for monitor in all_monitors 
            if 'synthetics alert' not in monitor.get('type', '').lower()
        ]
        return standard_monitors
    else:
        print(f"Failed to fetch monitors, Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return []

def fetch_all_synthetic_tests():
    """Fetch all synthetic tests (both API and browser) from Datadog."""
    url = f"{datadog_url}/api/v1/synthetics/tests"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get('tests', [])
    else:
        print(f"Failed to fetch synthetic tests, Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return []

def save_to_json(data, filename):
    """Save data to a JSON file."""
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)
    print(f"Saved monitor details to {filename}")

def main():
    # Fetch monitors and synthetics
    standard_monitors = fetch_all_monitors()
    all_synthetics = fetch_all_synthetic_tests()

    # Separate synthetic API and browser tests
    synthetic_api_tests = [test for test in all_synthetics if test['type'] == 'api']
    synthetic_browser_tests = [test for test in all_synthetics if test['type'] == 'browser']

    # Combine all monitors into one master JSON structure
    master_monitors = {
        "standard_monitors": standard_monitors,
        "synthetic_api_tests": synthetic_api_tests,
        "synthetic_browser_tests": synthetic_browser_tests
    }

    # Filenames for the JSON outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    standard_monitors_filename = f"standard_monitors_{timestamp}.json"
    synthetic_api_tests_filename = f"synthetic_api_tests_{timestamp}.json"
    synthetic_browser_tests_filename = f"synthetic_browser_tests_{timestamp}.json"
    master_monitors_filename = f"master_monitors_{timestamp}.json"

    # Save each category to its respective JSON file
    save_to_json(standard_monitors, standard_monitors_filename)
    save_to_json(synthetic_api_tests, synthetic_api_tests_filename)
    save_to_json(synthetic_browser_tests, synthetic_browser_tests_filename)
    
    # Save the master JSON with all monitors combined
    save_to_json(master_monitors, master_monitors_filename)

if __name__ == "__main__":
    main()