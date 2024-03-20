# Analysis Docker Container Action

This GitHub Action performs data analysis on time series data stored in Supabase, using Python for statistical analysis. 
It is designed to analyze changes between two sets of data (e.g., comparing performance metrics of software versions) and 
determine if the newer set meets predefined thresholds for acceptance. The analysis includes bootstrap analysis for 
confidence intervals and mean difference calculation, as well as Wilcoxon signed-rank tests for statistical significance.
This Action is meant to be used with our other GitHub Action for continuous benchmarking which can be found [here](https://github.com/ADSP-EMPIRIS/benchmark-gh-action).

## Features

- **Bootstrap Analysis**: Estimates the mean and confidence intervals of performance metrics to evaluate the stability and variability of changes.
- **Wilcoxon Signed-Rank Test**: Assesses the statistical significance of the difference between two sets of observations, useful for comparing metrics from different application versions.
- **Threshold-Based Acceptance**: Determines if changes in performance metrics, such as latency or throughput, exceed predefined thresholds, aiding in automated decision-making about version releases.
- **Supabase Integration**: Seamlessly fetches and stores experiment and metric data from a Supabase database.

## Prerequisites

- A Supabase account and an initialized project.
- A `.env` file containing your Supabase URL (`NEXT_PUBLIC_SUPABASE_URL`), Service Role Key (`SUPABASE_SERVICE_ROLE_KEY`), and any other necessary environment variables.

## Environment Variables

Ensure the following environment variables are set in your `.env` file or GitHub Secrets:

- `NEXT_PUBLIC_SUPABASE_URL`: The Supabase project URL.
- `SUPABASE_SERVICE_ROLE_KEY`: The Supabase Service Role API Key for secure access.
- `UNKEY_API_ID`: Your specific API key for identifying the user and associated data.
- `THRESHOLD`: The acceptable percentage change in performance metrics, used to flag significant deviations.

## Usage

1. **Setting up the `.env` file**:
   - Create a `.env` file in your project root with the required environment variables.

2. **GitHub Action Configuration**:
   - Configure this script as a GitHub Action by creating a workflow file in `.github/workflows/` directory of your repository.

An example workflow file can be found [here](https://github.com/ADSP-EMPIRIS/benchmark-gh-action/blob/main/.github/workflows/test.yml).

## Functionality Details

- The script begins by loading the necessary environment variables and establishing a connection to the Supabase client.
- It then proceeds to fetch relevant experiment data based on API keys and app names, preparing datasets for analysis.
- Bootstrap analysis and the Wilcoxon signed-rank test are conducted to evaluate performance changes between the latest two versions of the application.
- Based on the analysis results and predefined thresholds, decisions are made on whether the performance changes are acceptable.
- Finally, the script logs the analysis outcome, which includes whether the new version's performance is accepted or rejected based on the metrics evaluated.

