from dotenv import load_dotenv
import os
from supabase import create_client, Client
import numpy as np
from scipy.stats import wilcoxon
import heapq

# Load environment variables from ..env file
load_dotenv()

# Get Supabase URL and Key from environment variables
supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Create Supabase client
supabase: Client = create_client(supabase_url, supabase_key)


def bootstrap_analysis(data, n_bootstrap=10000, confidence_level=0.99):
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(data, size=len(data), replace=True)
        bootstrap_means.append(np.mean(sample))
    alpha = 100 - confidence_level * 100
    confidence_interval = np.percentile(bootstrap_means, [alpha / 2, 100 - alpha / 2])
    return np.mean(bootstrap_means), confidence_interval


def wilcoxon_test(x, y):
    stat, p = wilcoxon(x, y, zero_method="wilcox", correction=False, alternative="two-sided", method="auto")
    return stat, p

def get_next_dataset_id():
    # Fetch the last dataset_id from the analysis_results table
    last_entry = supabase.table('analysis_results').select('id').order('id', desc=True).limit(1).execute()

    if last_entry.data:
        last_id = last_entry.data[0]['id']
        return last_id + 1
    else:
        # If there are no entries in the table, start with 1
        return 1

def insert_analysis_results(run_id, bootstrap_mean, bootstrap_ci, wilcoxon_stat, wilcoxon_p, accepted, metric):
    result = supabase.table('analysis_results').insert({
        'id': get_next_dataset_id(),
        'experiment_run_id': run_id,  # Add the run_id to the database record
        'bootstrap_mean': bootstrap_mean,
        'bootstrap_ci_low': bootstrap_ci[0],
        'bootstrap_ci_high': bootstrap_ci[1],
        'wilcoxon_stat': wilcoxon_stat,
        'wilcoxon_p': wilcoxon_p,
        'accepted': accepted,
        'metric': metric
    }).execute()


def fetch_data(api_key, app_name):
    # Query the api_keys table to get user_id
    user_data = supabase.table('apikeys').select('user_id').eq('key_id', api_key).execute()

    # Extract user_id
    user_id = user_data.data[0]['user_id'] if user_data.data else None

    if not user_id:
        return "User ID not found for the given API key."

    # Query the experiment_run table for data specific to this user
    experiment_data = supabase.table('experiment_run').select('*').eq('user_id', user_id).order('id',
                                                                                                desc=True).execute()

    if experiment_data.data:
        # Filter the results based on the app_name within general_data

        filtered_data = []

        for entry in experiment_data.data:

            general_data = entry.get('general_data') or []

            has_matching_app_name = False
            for item in general_data:
                if len(item) >= 2 and item[0] == "Application name" and item[1] == app_name:
                    has_matching_app_name = True
                    break

            if has_matching_app_name:
                filtered_data.append(entry)

        return filtered_data if filtered_data else "No data found for the specified app."
    else:
        return "No data found for the user."


def get_run_ids(api_key, app_name):
    data = fetch_data(api_key, app_name)
    if isinstance(data, str):
        return data
    runs = [run['id'] for run in data]
    return runs


def extract_values(data_input, key_name):
    all_values = []
    for entry in data_input.data:
        timeseries_data = entry.get('timeseries_data', {})
        nested_data = timeseries_data.get('data', [])

        values = []
        for item in nested_data:
            if key_name in item:
                values.append(item[key_name])
            else:
                values.append(None)
        all_values.append(values)
    return all_values


def analyze_data(api_key, app_name):
    run_ids = get_run_ids(api_key, app_name)
    # Print fetched Run IDs for debugging
    print("Fetched Run IDs: ", run_ids)

    # Check if run_ids is a string, indicating an error message
    if isinstance(run_ids, str):
        return run_ids  # Return the error message

    # Check if there are fewer than 2 run IDs
    if len(run_ids) < 2:
        return ("Not enough data available for comparison. Please ensure there are at least two experiment runs "
                "before attempting analysis.")


    # print("RUN IDS: ", run_ids)
    threshold_str = os.getenv("THRESHOLD")
    threshold = float(threshold_str) if threshold_str else 0.0
    print("THRESHOLD: ", threshold)
    if len(run_ids) < 1:
        return "No previous runs found for the specified app."
    else:
        compare_ids = heapq.nlargest(2, run_ids)
        print("COMPARE IDS: ", compare_ids)
        data_new = supabase.table("timeseries").select("timeseries_data, metric").eq("experiment_run_id", str(compare_ids[0])).execute()
        data_old = supabase.table("timeseries").select("timeseries_data, metric").eq("experiment_run_id", str(compare_ids[1])).execute()

        metrics_new = [item['metric'] for item in data_new.data]
        metrics_old = [item['metric'] for item in data_old.data]

        metrics = list(set(metrics_new).intersection(set(metrics_old)))

        # If there are no common metrics, we cannot compare
        if len(metrics) == 0:
            print("No common metrics found. Cannot compare.")
            return

        print("METRICS: ", metrics)

        for metric in metrics:
            new = list(map(lambda o: o[metric], [item['timeseries_data'] for item in data_new.data if item['metric'] == metric][0]["data"]))
            old = list(map(lambda o: o[metric], [item['timeseries_data'] for item in data_old.data if item['metric'] == metric][0]["data"]))

            bootstrap_mean_new, bootstrap_ci_new = bootstrap_analysis(new)
            bootstrap_mean_old, bootstrap_ci_old = bootstrap_analysis(old)

            mean_change = (bootstrap_mean_new - bootstrap_mean_old) / bootstrap_mean_old if bootstrap_mean_old else float(
                'inf')
            ci_low_change = (bootstrap_ci_new[0] - bootstrap_ci_old[0]) / bootstrap_ci_old[0] if bootstrap_ci_old[
                0] else float('inf')
            ci_high_change = (bootstrap_ci_new[1] - bootstrap_ci_old[1]) / bootstrap_ci_old[1] if bootstrap_ci_old[
                1] else float('inf')

            accepted = True

            if metric == "Latency" and (
                  mean_change > threshold or ci_low_change > threshold or ci_high_change > threshold):
                accepted = False
                print(
                    f"Bootstrap: Latency increased by {mean_change * 100}%, which is more than the allowed threshold of "
                    f"{threshold * 100}%, new version not accepted.")
            if metric == "Throughput" and (
                    mean_change < -threshold or ci_low_change < -threshold or ci_high_change < -threshold):
                accepted = False
                print(
                    f"Bootstrap: Throughput decreased by {mean_change * 100}%, which is more than the allowed threshold of "
                    f"{threshold * 100}%, new version not accepted.")

            # Make sure new and old have the same length
            if len(new) > len(old):
                new = new[:len(old)]
            elif len(old) > len(new):
                old = old[:len(new)]

            wilcoxon_stat, wilcoxon_p = wilcoxon_test(new, old)

            if wilcoxon_p < 0.05:
                print(f"Wilcoxon: Significant difference detected (p={wilcoxon_p:.4f}).")
                median_new = np.median(new)
                median_old = np.median(old)

                median_change = (median_new - median_old) / median_old if median_old else float('inf')

                if metric == "Latency" and median_change > threshold:
                    accepted = False
                    print("Wilcoxon: New version has significantly higher latency, which is not accepted.")
                if metric == "Throughput" and median_change < -threshold:
                    accepted = False
                    print("Wilcoxon: New version has significantly lower throughput, which is not accepted.")

            insert_analysis_results(compare_ids[0], bootstrap_mean_new, bootstrap_ci_new, wilcoxon_stat, wilcoxon_p,
                                    accepted, metric)


response = supabase.table("experiment_run").select("general_data").order("id", desc=True).limit(1).execute()

data = response.data

if data and 'general_data' in data[0]:
    general_data = data[0]['general_data']
    # Look for the entry with 'Application Name' and get its value
    app_name = next((item[1] for item in general_data if item[0] == 'Application name'), None)

    if app_name:
        print(f"App name: {app_name}")
    else:
        print("Application Name not found in general_data.")
else:
    print("No data found or unexpected data structure.")

api_key = os.getenv("UNKEY_API_ID")

# Only call analyze_data if app_name is defined
if app_name:
    analyze_data(api_key, app_name)
else:
    print("App name is undefined, skipping analyze_data call.")

