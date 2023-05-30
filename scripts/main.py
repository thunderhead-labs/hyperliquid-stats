import datetime
import json
import os

import boto3
import lz4.frame
import pandas as pd
import requests
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

path = os.path.dirname(os.path.abspath(__file__))
slack_alerts_channel = "#hyperliquid-alerts"

table_to_file_name_map = {
    "non_mm_trades": "non_mm_trades",
    "non_mm_ledger_updates": "ledger_updates",
    "liquidations": "liquidations",
    "funding": "funding",
    "account_values": "account_values",
    "asset_ctxs": "asset_ctxs",
    "market_data_snapshot_details": "market_data",
}

# Load configuration from JSON file
with open("../config.json", "r") as config_file:
    config = json.load(config_file)


def get_asset_coin_map() -> dict[int, str]:
    asset_coin_map = {}

    url = "https://api.hyperliquid.xyz/info"
    headers = {
        "Content-Type": "application/json",
    }
    data = {"type": "meta"}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    for i, coin in enumerate(response.json()["universe"]):
        asset_coin_map[i] = coin["name"]

    return asset_coin_map


def download_data_from_s3(bucket_name: str, file_name: str):
    aws_access_key_id = config["aws_access_key_id"]
    aws_secret_access_key = config["aws_secret_access_key"]
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    s3 = session.resource("s3")
    my_bucket = s3.Bucket(bucket_name)

    # Construct the local file path, ensuring the /tmp directory exists
    local_file_path = os.path.join("../tmp", file_name)
    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

    my_bucket.download_file(file_name, local_file_path)


def load_data_to_db(db_uri: str, table_name: str, file_name: str):
    engine = create_engine(db_uri)
    if "market_data" in file_name:
        data = []
        with lz4.frame.open(f"../tmp/{file_name}", 'r') as f:
            for line in f:
                json_line = json.loads(line)
                data.append(json_line)
        df = pd.json_normalize(data)
        df_details = pd.DataFrame()  # Initialize an empty DataFrame

        for idx, row in df.iterrows():
            levels = row["raw.data.levels"]
            for level in levels:
                new_row = row.copy()  # Create a copy of the original row
                new_row = new_row.to_frame().T  # Convert the copied row to a DataFrame
                new_row[["px", "sz", "n"]] = pd.Series(level, index=["px", "sz", "n"])  # Assign level values to "px", "sz", and "n" columns
                df_details = df_details.append(new_row, ignore_index=True)

        # Loading market_data_snapshot_details
        df_details.to_sql('market_data_snapshot_details', con=engine, if_exists="append", index=False)
    else:
        with lz4.frame.open(f"../tmp/{file_name}", 'r') as f:
            df = pd.read_csv(f)
    df.to_sql(table_name, con=engine, if_exists="append", index=False)


def get_latest_date(db_uri: str, table_name: str):
    engine = create_engine(db_uri)
    with engine.connect() as connection:
        result = connection.execute(text(f"SELECT max(time) FROM {table_name}"))
        return result.scalar()


def send_alert(message: str):
    return
    slack_token = config["slack_token"]
    if slack_token != "":
        client = WebClient(token=slack_token)

        try:
            response = client.chat_postMessage(channel=slack_alerts_channel, text=message)
        except SlackApiError as e:
            print(f"Error sending alert: {e.response['error']}")


def generate_dates(start_date: datetime.date):
    end_date = datetime.date.today()
    date_list = [
        start_date + datetime.timedelta(days=x)
        for x in range((end_date - start_date).days + 1)
    ]
    return date_list


def update_market_data_snapshot_cache(db_uri: str, date: datetime.date):
    engine = create_engine(db_uri)
    with engine.connect() as connection:
        # Aggregate data from market_data_snapshot and market_data_snapshot_details tables
        query = text("""
        INSERT INTO market_data_snapshot_cache (time, user, coin, channel, n, mean_px, sum_sz)
        SELECT 
            DATE(mds."time") AS time,
            mds."user",
            mds.coin,
            mds.channel,
            mds.n,
            AVG(md_details.px) AS mean_px,
            SUM(md_details.sz) AS sum_sz,
        FROM 
            market_data_snapshot mds 
        JOIN 
            market_data_snapshot_details md_details 
        ON 
            mds.id = md_details.snapshot_id
        WHERE 
            DATE(mds."time") = :date
        GROUP BY 
            DATE(mds."time"), mds."user", mds.coin, mds.channel, mds.n
        """)
        connection.execute(query, date=date)


def update_cache_tables(db_uri: str, file_name: str, date: datetime.date):
    # Reads the file saved by s3 of date and cache table with the new data
    if "market_data" in file_name:
        update_market_data_snapshot_cache(db_uri, date)
    else:
        engine = create_engine(db_uri)
        with lz4.frame.open(f"../tmp/{file_name}", 'r') as f:
            df = pd.read_csv(f)

        if "trades" in file_name:
            df_agg = (
                df.groupby(["user", "coin", "side", "crossed", "special_trade_type"])
                .agg({"px": "mean", "sz": "sum"})
                .reset_index()
            )

            df_agg.columns = ["user", "coin", "side", "crossed", "special_trade_type", "mean_px", "sum_sz"]
            df_agg["group_count"] = df.groupby(["user", "coin", "side", "crossed", "special_trade_type"])[
                "user"].transform("count")
            df_agg["time"] = date
            df_agg["usd_volume"] = df_agg["mean_px"] * df_agg["sum_sz"]
            df_agg.to_sql(
                "non_mm_trades_cache", con=engine, if_exists="append", index=False
            )

        elif "ledger_updates" in file_name:
            df_agg = (
                df.groupby(["user"])
                .agg({"delta_usd": "sum"})
                .reset_index()
            )
            df_agg.columns = ["user", "sum_delta_usd"]
            df_agg["time"] = date
            df_agg.to_sql(
                "non_mm_ledger_updates_cache", con=engine, if_exists="append", index=False
            )

        elif "liquidations" in file_name:
            df_agg = (
                df.groupby(["user", "leverage_type"])
                .agg({"liquidated_ntl_pos": "sum", "liquidated_account_value": "sum"})
                .reset_index()
            )
            df_agg.columns = [
                "user",
                "leverage_type",
                "sum_liquidated_ntl_pos",
                "sum_liquidated_account_value",
            ]
            df_agg["time"] = date
            df_agg.to_sql("liquidations_cache", con=engine, if_exists="append", index=False)

        elif "funding" in file_name:
            df_agg = (
                df.groupby(["coin"])
                .agg({"funding": "sum", "premium": "sum"})
                .reset_index()
            )
            df_agg.columns = ["coin", "sum_funding", "sum_premium"]
            df_agg["time"] = date
            df_agg.to_sql("funding_cache", con=engine, if_exists="append", index=False)

        elif "account_values" in file_name:
            df_agg = (
                df.groupby(["user", "is_vault"])
                .agg({"account_value": "sum", "cum_vlm": "sum", "cum_ledger": "sum"})
                .reset_index()
            )
            df_agg.columns = [
                "user",
                "is_vault",
                "sum_account_value",
                "sum_cum_vlm",
                "sum_cum_ledger",
            ]
            df_agg["time"] = date
            df_agg.to_sql("account_values_cache", con=engine, if_exists="append", index=False)

        elif "asset_ctxs" in file_name:
            df_agg = (
                df.groupby(["coin"])
                .agg({
                    "funding": "sum",
                    "open_interest": "sum",
                    "prev_day_px": "mean",
                    "day_ntl_vlm": "sum",
                    "premium": "mean",
                    "oracle_px": "mean",
                    "mark_px": "mean",
                    "mid_px": "mean",
                    "impact_bid_px": "mean",
                    "impact_ask_px": "mean"
                })
                .reset_index()
            )
            df_agg.columns = [
                "coin",
                "sum_funding",
                "sum_open_interest",
                "avg_prev_day_px",
                "sum_day_ntl_vlm",
                "avg_premium",
                "avg_oracle_px",
                "avg_mark_px",
                "avg_mid_px",
                "avg_impact_bid_px",
                "avg_impact_ask_px"
            ]
            df_agg["time"] = date
            df_agg.to_sql("asset_ctxs_cache", con=engine, if_exists="append", index=False)


def process_file(db_uri: str, bucket_name: str, file_name: str, table: str, date: datetime.date):
    download_data_from_s3(bucket_name, file_name)
    load_data_to_db(db_uri, table, file_name)
    update_cache_tables(db_uri, file_name, date)
    tmp_file_path = os.path.join("../tmp", file_name)
    if os.path.isfile(tmp_file_path):
        os.remove(tmp_file_path)
    else:
        raise Exception(f"Error: {tmp_file_path} not found")


def main():
    bucket_name = config["bucket_name"]
    db_uri = config["db_uri"]
    tables = config["tables"]
    asset_coin_map = get_asset_coin_map()

    for table in tables:
        table_name = table_to_file_name_map[table]
        latest_date = get_latest_date(db_uri, table)
        latest_date = (
            latest_date.date()
            if latest_date
            else datetime.date.today() - datetime.timedelta(days=30)
        )
        dates = generate_dates(latest_date)
        if not len(dates):
            send_alert(f"Nothing to process for {table} at {latest_date}")
            print(f"Nothing to process for {table} at {latest_date}")
        for date in dates[1:]:
            try:
                if table_name == "market_data":
                    for i in range(24):
                        for asset in asset_coin_map.values():
                            file_name = f"{table_name}/{date.strftime('%Y%m%d')}/{i}/Snap/{asset}.lz4"
                            process_file(db_uri, bucket_name, file_name, table, date)
                else:
                    file_name = f"{table_name}/{date.strftime('%Y%m%d')}.csv.lz4"
                    process_file(db_uri, bucket_name, file_name, table, date)

                send_alert(f"Data processing completed successfully for {date, table}!")
                print(f"Data processing completed successfully for {date, table}!")
            except Exception as e:
                send_alert(
                    f"Data processing for {table} as {date} failed with error: {e}"
                )
                print(
                    f"Data processing for {table} as {date} failed with error: {e}"
                )

        # Check cache table max date and compare with the main table
        cache_max_date = get_latest_date(db_uri, f"{table}_cache")
        if cache_max_date and cache_max_date.date() != latest_date:
            send_alert(
                f"Cache table for {table} has a different max date ({cache_max_date}) than the main table ({latest_date})")


if __name__ == "__main__":
    main()
