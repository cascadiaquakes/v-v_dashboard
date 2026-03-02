import os
import json
import warnings
import zipfile
from datetime import datetime

import boto3
import pandas as pd
from io import StringIO, BytesIO

from sklearn.neighbors import KDTree
import numpy as np
from botocore.exceptions import NoCredentialsError, ClientError

# Initialize AWS clients
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table_name = os.environ["TABLE_NAME"]
table = dynamodb.Table(table_name)

def convert_seconds_to_time(seconds):
    years = seconds / (365.25 * 24 * 3600)
    days = seconds / (24 * 3600)
    hours = seconds / 3600
    return years, days, hours, seconds


def extract_header(file_header, prefix, content):
    if file_header is None:
        file_header = {}

    header_data = {}

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# File:"):
            continue
        if line.startswith("#"):
            if '=' in line:
                key, value = line[2:].strip().split('=', 1)
                header_data[key.strip()] = value.strip()
            else:
                header_data.setdefault("comments", []).append(line[2:].strip())
        else:
            break

    file_header[prefix] = header_data
    return file_header


def interpolate_data(
    df: pd.DataFrame,
    grid_params: dict,
    k: int = 3,
    power: float = 1.0,
    average_duplicates: bool = True,
) -> pd.DataFrame:
    """
    Regrid all numeric variables in df onto the 2D grid defined by `grid_params`.

    - Axis names are inferred from grid_params keys (expects exactly 2 axes).
    - Those axis columns must exist in df.
    - All numeric columns except the axes are interpolated (2D IDW).
    """
    axes = list(grid_params.keys())
    if len(axes) != 2:
        raise ValueError(f"grid_params must have exactly 2 axes, got: {axes}")

    a0, a1 = axes[0], axes[1]  # preserve naming from JSON
    if a0 not in df.columns or a1 not in df.columns:
        raise KeyError(
            f"Axis columns {a0!r}, {a1!r} must exist in df. "
            f"df columns: {list(df.columns)}"
        )

    # numeric variables to interpolate = all numeric except axes
    all_numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    variables = [c for c in all_numeric if c not in (a0, a1)]
    if not variables:
        raise ValueError("No numeric variables found to interpolate (besides the axes).")

    # Optionally average duplicate axis points
    if average_duplicates:
        work = (df[[a0, a1] + variables]
                .groupby([a0, a1], as_index=False)
                .mean(numeric_only=True))
    else:
        work = df[[a0, a1] + variables].copy()

    # Build query grid
    xi = np.linspace(grid_params[a0]["min"], grid_params[a0]["max"], int(grid_params[a0]["n"]))
    yi = np.linspace(grid_params[a1]["min"], grid_params[a1]["max"], int(grid_params[a1]["n"]))
    X, Y = np.meshgrid(xi, yi, indexing="xy")
    grid_points = np.column_stack([X.ravel(), Y.ravel()])

    # KDTree query
    pts = work[[a0, a1]].to_numpy()
    n_pts = len(pts)
    if n_pts == 0:
        raise ValueError("No input points to interpolate.")

    k_eff = min(int(k), n_pts)
    tree = KDTree(pts)
    dist, ind = tree.query(grid_points, k=k_eff)

    # Weights
    if power == 0:
        weights = np.full_like(dist, 1.0 / dist.shape[1], dtype=float)
    else:
        with np.errstate(divide="ignore"):
            w = 1.0 / (np.power(dist, power) + 1e-12)

        # exact matches: give all weight to the zero-distance neighbor(s)
        zero_rows = np.any(dist < 1e-12, axis=1)
        if np.any(zero_rows):
            w[zero_rows] = 0.0
            zmask = dist[zero_rows] < 1e-12
            w[zero_rows] = zmask / zmask.sum(axis=1, keepdims=True)

        row_sums = w.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        weights = w / row_sums

    # Interpolate
    out = {a0: grid_points[:, 0], a1: grid_points[:, 1]}
    for var in variables:
        vals = work[var].to_numpy()
        neigh_vals = vals[ind]
        out[var] = np.sum(weights * neigh_vals, axis=1)

    return pd.DataFrame(out)


def read_table_from_string(file_content: str) -> pd.DataFrame:
    return pd.read_csv(StringIO(file_content), comment="#", sep=r"\s+")


def read_seas_slip_long_from_string(
    content: str,
    *,
    z_name: str = "z",
    t_name: str = "t",
    slip_name: str = "slip",
    max_slip_rate_name: str = "max_slip_rate",
    keep_max_slip_rate: bool = True,
    n_header_zeros: int = 2,
    min_fields_for_axis_row: int = 10,
) -> pd.DataFrame:
    lines = content.splitlines(True)

    def is_float(s: str) -> bool:
        try:
            float(s)
            return True
        except ValueError:
            return False

    # find the axis row (many numeric fields)
    x_idx = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("#"):
            continue
        parts = ln.split()
        if len(parts) > min_fields_for_axis_row and all(is_float(p) for p in parts):
            x_idx = i
            break
    if x_idx is None:
        raise ValueError("Could not find axis row (many numeric fields).")

    z = np.array(lines[x_idx].split(), dtype=float)
    if n_header_zeros:
        z = z[n_header_zeros:]

    expected_len = len(z) + 2  # t + max_slip_rate + slip(z...)

    rows = []
    for ln in lines[x_idx + 1:]:
        if ln.lstrip().startswith("#"):
            continue
        parts = ln.split()
        if len(parts) != expected_len:
            continue
        if not all(is_float(p) for p in parts):
            continue
        rows.append(parts)

    if not rows:
        raise ValueError("No data rows found matching expected length.")

    data = np.array(rows, dtype=float)
    t = data[:, 0]
    max_sr = data[:, 1]
    slip = data[:, 2:]  # (nt, nz)

    out = {
        t_name: np.repeat(t, len(z)),
        z_name: np.tile(z, len(t)),
        slip_name: slip.reshape(-1),
    }
    if keep_max_slip_rate:
        out[max_slip_rate_name] = np.repeat(max_sr, len(z))

    return pd.DataFrame(out)

def read_data_for_template(file_content: str, file_info: dict) -> pd.DataFrame:
    """
    Choose how to parse file_content based on template config.
    Legacy default is the current whitespace-table reader.
    """
    reader = file_info.get("reader", "table")
    reader_kwargs = file_info.get("reader_kwargs", {}) or {}

    if reader == "table":
        return read_table_from_string(file_content)

    if reader in ("seas_slip_long", "seas_slip_long_from_axis"):
        return read_seas_slip_long_from_string(file_content, **reader_kwargs)

    raise ValueError(f"Unknown reader '{reader}' for prefix={file_info.get('prefix')}")

def process_zip(bucket_name, zip_key, benchmark_pb, code_name, version, user_metadata=None, **kwargs):
    output_folder = f"/tmp/{code_name}_{version}/"
    os.makedirs(output_folder, exist_ok=True)

    file_list = []
    file_header = {}  # Now accumulates header per prefix

    # Download and unzip the file
    zip_obj = s3.get_object(Bucket=bucket_name, Key=zip_key)
    # Load the JSON template
    template_key = f"benchmark_templates/{benchmark_pb}.json"
    try:
        response = s3.get_object(Bucket=bucket_name, Key=template_key)
        template_content = response['Body'].read().decode('utf-8')
        template = json.loads(template_content)
        print("template loaded successfully")
    except Exception as e:
        raise ValueError(f"Error loading template {template_key}: {e}")

    with zipfile.ZipFile(BytesIO(zip_obj['Body'].read())) as zip_obj:
        zip_file_list = zip_obj.namelist()
        for file_info in template['files']:
            prefix = file_info['prefix']
            file_type = file_info['file_type']
            expected_structure = file_info

            # Find matching files, even if they're in subdirectories
            matching_files = [
                f for f in zip_file_list
                if os.path.basename(f).startswith(prefix) and f.endswith(f".{file_type}")
            ]
            print(f"number of matching files for {prefix} {len(matching_files)}")
            for file_name in matching_files:
                # Read and validate file
                with zip_obj.open(file_name) as file:
                    file_content = file.read().decode('utf-8')

                    # Only extract header once per prefix (e.g., first matching file)
                    if prefix not in file_header:
                        file_header = extract_header(file_header, prefix, file_content)

                    df = read_data_for_template(file_content, expected_structure)

                    # Validate columns
                    var_list = expected_structure['var_list']
                    expected_columns = [var['name'].lower() for var in
                                        var_list]  # Convert expected columns to lowercase
                    df_columns_lowercase = [col.lower() for col in df.columns]  # Convert actual columns to lowercase

                    if df_columns_lowercase != expected_columns:
                        warnings.warn(
                            f"File {os.path.basename(file_name)} does not match the expected structure. Expected columns: {expected_columns}, found columns: {df_columns_lowercase}")
                        continue

                    # Force DataFrame column names to lowercase
                    df.columns = df.columns.str.lower()

                    if "grid" in expected_structure:
                        df = interpolate_data(df, expected_structure['grid'])
                    # Save as Parquet
                    output_path = os.path.join(output_folder,
                                               f"{os.path.splitext(os.path.basename(file_name))[0]}.parquet")
                    df.to_parquet(output_path, index=False)

                # Upload the Parquet file to the main bucket with the benchmark_pb structure
                target_key = f"public_ds/{benchmark_pb}/{code_name}_{version}/{os.path.basename(output_path)}"
                s3.upload_file(output_path, "benchmark-vv-data", target_key, ExtraArgs={"Metadata": user_metadata})
                file_list.append(file_name)
                os.remove(output_path)

    # Save metadata as JSON and upload it
    metadata = {**file_header, "processed_files": file_list}
    metadata_path = os.path.join(output_folder, "metadata.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=4)

    s3.upload_file(metadata_path, "benchmark-vv-data", f"public_ds/{benchmark_pb}/{code_name}_{version}/metadata.json",
                   ExtraArgs={"Metadata": user_metadata})


def handler(event, context):
    try:
        print(event)
        # for record in event['Records']:
        s3_detail = event.get("s3Event", {}).get("detail", {})
        bucket_name = s3_detail.get("bucket", {}).get("name", "unknown")
        zip_key = s3_detail.get("object", {}).get("key", "unknown")

        # Extract metadata from the uploaded file
        response = s3.head_object(Bucket=bucket_name, Key=zip_key)
        user_metadata = response.get('Metadata', {})
        print(f'Metadata: {user_metadata}')

        user_id = user_metadata.get("userid")
        file_id = os.path.basename(zip_key)
        if not user_id:
            print(f'No userid found for {zip_key}')
            return {"error": "userId not found in S3 object metadata"}

        # Write initial status to DynamoDB
        timestamp = datetime.utcnow().isoformat() + "Z"  # ISO format with UTC timezone

        table.put_item(
            Item={
                "userId": user_id,
                "fileId": file_id,
                "status": "processing",
                "timestamp": timestamp,  # Add timestamp if available
            }
        )

        # Extract benchmark_pb, code_name, and version from the zip key
        parts = zip_key.split('/')
        benchmark_pb = parts[1]  # e.g., bp1_qd
        zip_name = os.path.basename(zip_key)
        code_name, version = zip_name.rsplit('.', 1)[0].split('_', 1)
        print(f'Processing benchmark {benchmark_pb}, code {code_name}, version {version}')
        try:
            process_zip(bucket_name, zip_key, benchmark_pb, code_name, version, user_metadata)
        except Exception as e:
            print(f"Error processing {zip_key}: {e}")
            if user_id and file_id:
                table.update_item(
                    Key={"userId": user_id, "fileId": file_id},
                    UpdateExpression="SET #status = :status, #error = :error",
                    ExpressionAttributeNames={
                        "#status": "status",
                        "#error": "error",
                    },
                    ExpressionAttributeValues={
                        ":status": "failed",
                        ":error": str(e),
                    },
                )
            return {"error": f"Error processing {zip_key}: {e}"}

        # Update status to "completed"
        table.update_item(
            Key={"userId": user_id, "fileId": file_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "completed"},
        )
        return {"status": "completed"}

    except NoCredentialsError:
        return {"error": "AWS credentials not found"}
    except ClientError as e:
        return {"error": str(e)}
