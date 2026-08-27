import asyncio
import base64
import io
import json
import urllib
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

import awswrangler as wr
import boto3
import pandas as pd
import plotly.express as px
from dash import html

# Global variable to store the cache object
cache = None

def set_cache(cache_obj):
    """Set the cache object for use in this module."""
    global cache
    cache = cache_obj

def memoize(timeout=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if cache is None:
                raise ValueError("Cache object is not initialized. Call set_cache() first.")

            # Generate a cache key based on the function name and arguments
            cache_key = f"{func.__name__}_{args!s}_{kwargs!s}"

            # Check if the data is already in the cache
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                print(f"Retrieving data from cache for key: {cache_key}")
                return cached_data

            # If not in cache, fetch the data and cache it
            print(f"Fetching data from S3 for key: {cache_key}")
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout)
            return result
        return wrapper
    return decorator

# Create a global S3 client for reuse across function calls
s3_client = boto3.client('s3')

# Helper function to parse the benchmark_id from the URL
def parse_benchmark_id(search):
    query_params = urllib.parse.parse_qs(search.lstrip('?'))
    return query_params.get('benchmark_id', [''])[0]  # Return first value or empty string


@memoize(timeout=3600)
def _get_s3_dataset_cached(bucket_name, s3_key, object_revision):
    """Fetch an S3 object, cached for a specific S3 revision."""
    try:
        df = wr.s3.read_parquet(f"s3://{bucket_name}/{s3_key}")
        return df

    except Exception as e:  # noqa: BLE001 - callers use None for any unreadable dataset
        print(f"Error fetching {s3_key}: {e}")
        return None


def get_s3_dataset(bucket_name, s3_key):
    """Fetch one S3 object, invalidating the cache when that object changes."""
    try:
        metadata = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        last_modified = metadata["LastModified"].isoformat()
        object_revision = (
            metadata.get("VersionId"),
            metadata.get("ETag"),
            last_modified,
            metadata.get("ContentLength"),
        )
    except Exception as e:  # noqa: BLE001 - callers use None for any unreadable dataset
        print(f"Error checking {s3_key}: {e}")
        return None

    return _get_s3_dataset_cached(bucket_name, s3_key, object_revision)


def convert_seconds_to_time(seconds):
    """
    Convert a time duration from seconds to years, days, hours, and seconds.

    Parameters:
    seconds (int): Time duration in seconds.

    Returns:
    tuple: A tuple containing years, days, hours, and seconds.
    """
    years = seconds / (365.25 * 24 * 3600)
    days = (seconds / (24 * 3600))
    hours = seconds / 3600
    return years, days, hours, seconds


def fetch_group_names_for_benchmark(benchmark_id):
    try:
        bucket_name = "benchmark-vv-data"
        prefix = f"public_ds/{parse_benchmark_id(benchmark_id)}/"

        print(f"getting data for benchmark {benchmark_id}")

        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix, Delimiter="/")

        group_names = []
        for page in pages:
            for cp in page.get("CommonPrefixes", []):
                # strip the prefix part, keep only the folder name
                folder = cp["Prefix"].split("/")[-2]
                group_names.append(folder)

        result = sorted(group_names)

    except Exception as e:  # noqa: BLE001 - return the UI fallback for any S3 failure
        print(f"Error fetching datasets: {e}")
        result = {'no datasets found'}
    return result


def get_plots_from_json(json_data, file_name):
    """
    Generate a list of variables to plot against time from the provided JSON.

    Parameters:
        json_data (dict): The JSON data containing file information.
        file_name (str): The file type to filter files (e.g., "surfdef").

    Returns:
        list: A list of dictionaries with variable names and units to plot against time.
    """
    plots = []
    if json_data is None:
        return plots
    for file_info in json_data['files']:
        if file_info['name'] == file_name:
            grid_axes = set((file_info.get('grid') or {}).keys())
            excluded_axes = grid_axes or {'x', 'y'}
            for var in file_info['var_list']:
                if var['name'] not in excluded_axes:
                    plots.append(var)
    return plots


def get_upload_df(data, filename, var_list):
    """
    Convert uploaded data to a DataFrame and add time columns.

    Parameters:
    data (str): Base64 encoded string of the uploaded data.
    filename (str): Name of the uploaded file.

    Returns:
    DataFrame: A pandas DataFrame containing the uploaded data with additional time columns.
    """
    if data is None:
        return None
    try:
        _content_type, content_string = data.split(',')
        decoded = base64.b64decode(content_string)
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), comment='#', delim_whitespace=True)
        expected_columns = [var['name'] for var in var_list]
        print(f"expected_columns: {expected_columns}")
        print(f"df.columns: {list(df.columns)}")
        if list(df.columns) != expected_columns:
            print("file does not have the expected columns")
            return None
        df['dataset_name'] = filename
        return df
    except Exception as e:  # noqa: BLE001 - reject any malformed upload as a unit
        print(f"Error reading uploaded data: {e}")
        return None


async def fetch_data_concurrently(bucket_name, benchmark_id, list_df, receiver):
    """Fetch data concurrently from S3."""
    all_data = []
    if not list_df:
        return None

    # Use a ThreadPoolExecutor to handle blocking I/O with pandas
    max_workers = min(8, len(list_df))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loop = asyncio.get_event_loop()
        tasks = []

        # Prepare S3 fetch tasks for all dataset-depth combinations
        for file_name in list_df:
            s3_key = f"public_ds/{benchmark_id}/{file_name}/{receiver}.parquet"
            tasks.append(
                loop.run_in_executor(
                    executor, get_s3_dataset, bucket_name, s3_key
                )
            )

        # Collect results as they complete
        results = await asyncio.gather(*tasks)

        # Process valid DataFrames
        for i, tmp_df in enumerate(results):
            if tmp_df is not None:
                file_name = list_df[i]
                tmp_df['dataset_name'] = f"{file_name}_rec{receiver}"
                all_data.append(tmp_df)
    return pd.concat(all_data, ignore_index=True, copy=False) if all_data else None



def get_df(benchmark_id, list_df, receiver):
    """Get a concatenated DataFrame from a list of datasets and depths."""
    if list_df and receiver:
        return asyncio.run(
            fetch_data_concurrently('benchmark-vv-data', parse_benchmark_id(benchmark_id), list_df, receiver))
    else:
        return None


def generate_color_mapping(datasets):
    """
    Generate a color mapping for a list of datasets.

    Parameters:
    datasets (list): List of dataset names.

    Returns:
    dict: A dictionary mapping dataset names to colors.
    """
    color_mapping = {}
    colors = px.colors.qualitative.D3
    for i, dataset in enumerate(datasets):
        color_mapping[dataset] = colors[i % len(colors)]
    return color_mapping


@memoize(timeout=3600)
def get_metadata(benchmark_id, dataset_name):
    """
    Get metadata for a dataset.

    Parameters:
    benchmark_id (str): The benchmark ID.
    dataset_name (str): The name of the dataset.

    Returns:
    dict: Metadata for the dataset.
    """
    try:
        bucket_name = 'benchmark-vv-data'
        s3_key = f"public_ds/{parse_benchmark_id(benchmark_id)}/{dataset_name}/metadata.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        metadata = response['Body'].read().decode('utf-8')
        return render_json(json.loads(metadata))
    except Exception as e:  # noqa: BLE001 - metadata is optional in the UI
        print(f"Error fetching metadata: {e}")
        return None


def wrap_text(text, max_len=100):
    """Wrap text at spaces before the max_len, preserving words."""
    import textwrap
    return html.Span([
        html.Span(line + "\n") for line in textwrap.wrap(text, width=max_len)
    ])

def render_json(data):
    if isinstance(data, dict):
        return html.Ul([
            html.Li([html.B(f"{key}: "), render_json(value)])
            for key, value in data.items()
        ])
    elif isinstance(data, list):
        return html.Ul([html.Li(render_json(item)) for item in data])
    elif isinstance(data, str) and len(data) > 100:
        return wrap_text(data)
    else:
        return html.Span(str(data))


@memoize(timeout=3600)
def _get_benchmark_params_cached(bucket_name, template_key, object_revision):
    """Fetch and parse a benchmark template cached for one S3 revision."""
    response = s3_client.get_object(Bucket=bucket_name, Key=template_key)
    template_content = response['Body'].read().decode('utf-8')
    return json.loads(template_content)


def get_benchmark_params(search):
    """Get benchmark parameters, invalidating the cache after an S3 update."""
    benchmark_id = parse_benchmark_id(search)
    bucket_name = 'benchmark-vv-data'
    template_key = f"benchmark_templates/{benchmark_id}.json"

    try:
        metadata = s3_client.head_object(Bucket=bucket_name, Key=template_key)
        last_modified = metadata["LastModified"].isoformat()
        object_revision = (
            metadata.get("VersionId"),
            metadata.get("ETag"),
            last_modified,
            metadata.get("ContentLength"),
        )
        return _get_benchmark_params_cached(
            bucket_name,
            template_key,
            object_revision,
        )
    except Exception as e:
        raise ValueError(f"Error loading benchmark params: {e}") from e

@memoize(timeout=3600)
def _get_benchmarks_list_cached(bucket_name, key, object_revision):
    """Fetch and parse the benchmark list cached for one S3 revision."""
    resp = s3_client.get_object(Bucket=bucket_name, Key=key)
    content = resp["Body"].read().decode("utf-8")
    return json.loads(content)


def get_benchmarks_list():
    """Get the benchmark list, invalidating the cache after an S3 update."""
    bucket_name = "benchmark-vv-data"
    key = "public_ds/benchmarks_list.json"

    metadata = s3_client.head_object(Bucket=bucket_name, Key=key)
    last_modified = metadata["LastModified"].isoformat()
    object_revision = (
        metadata.get("VersionId"),
        metadata.get("ETag"),
        last_modified,
        metadata.get("ContentLength"),
    )
    return _get_benchmarks_list_cached(bucket_name, key, object_revision)
