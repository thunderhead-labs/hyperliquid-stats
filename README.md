Apologies for the oversight. Here's an updated version of the README.md file with the correct number of endpoints and including the missing tables in the "Database Tables" section:

# HyperLiquid Stats

HyperLiquid Stats is a data analysis and visualization tool for HyperLiquid. It provides various insights and metrics related to trading activities, user behavior, and financial data. This README.md file provides detailed information on how to install, set up, and use the HyperLiquid Stats project.

## Summary

HyperLiquid Stats project is built to analyze and visualize data from the HyperLiquid platform. It consists of several components, including scripts, database tables, API endpoints, and Docker configurations. The main functionalities of this project include:

- Data extraction from AWS S3
- Data loading into a PostgreSQL database
- Calculation of various metrics and insights
- API endpoints for retrieving data and metrics
- Web-based visualization of data using charts and tables

## Installation

1. Clone the project repository from GitHub:

   ```bash
   git clone https://github.com/thunderhead-labs/hyperliquid-stats.git
   ```

2. Navigate to the project directory:

   ```bash
   cd hyperliquid-stats
   ```

3. Install the required Python packages by running the following command:

   ```bash
   pip install -r requirements.txt
   ```

4. Set up the project configuration file. Copy the `config.example.json` file and rename it to `config.json`. Modify the configuration values according to your environment and requirements.

5. Install Docker and Docker Compose if they are not already installed. Docker is required to run the project in a containerized environment.

## Setup

Before using HyperLiquid Stats, you need to set up the database and configure the necessary components. Follow the steps below to complete the setup process:

1. Create a PostgreSQL database. You can either use an existing database or create a new one.

2. Update the `config.json` file with the database connection details. Set the `db_uri` field to the appropriate database connection URL.

3. Create the required database tables by executing the SQL script `tables.sql` in your PostgreSQL database. This script contains the necessary table definitions and indexes.

4. (Optional) If you want to run the project using Docker, make sure you have Docker and Docker Compose installed. The project includes a `Dockerfile` and a `docker-compose.yml` file to simplify the containerization process.

## Usage

HyperLiquid Stats provides an API that exposes various endpoints for retrieving data and metrics. To start the project, follow the steps below:

1. If you're not using Docker, you can run the project directly using Uvicorn. Execute the following command in the project directory:

   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```

   This will start the API server on `http://localhost:8000`.

2. If you prefer running the project using Docker, use the following command to start the project:

   ```bash
   docker-compose up
   ```

   Docker Compose will build the project image and start the containers. The API server will be accessible at `http://localhost:8000`.

3. Once the project is running, you can access the API endpoints using a tool like cURL or a web browser. The available endpoints and their descriptions are as follows:

   - **GET /hyperliquid/total_users**: Retrieves the total number of users. Part of `Total Users` metric.
   - **GET /hyperliquid/total_usd_volume**: Retrieves the total USD trading volume. Part of `Total USD Volume` metric.
   - **GET /hyperliquid/total_deposits**: Retrieves the total amount of deposits. Part of `Total Deposits` metric.
   - **GET /hyperliquid/total_withdrawals**: Retrieves the total amount of withdrawals. Part of `Total Withdrawals` metric.
   - **GET /hyperliquid/total_notional_liquidated**: Retrieves the total notional value liquidated. Part of `Total Notional Liquidated` metric.
   - **GET /hyperliquid/cumulative_usd_volume**: Retrieves the cumulative USD trading volume over time. The line chart of `Cumulative total non-MM USD Volume` chart.
   - **GET /hyperliquid/daily_usd_volume**: Retrieves the daily USD trading volume over time. The bar chart of `Cumulative total non-MM USD Volume` chart.
   - **GET /hyperliquid/daily_usd_volume_by_coin**: Retrieves the daily USD trading volume by coin over time. Overlay of bar chart in `Cumulative total non-MM USD Volume` chart.
   - **GET /hyperliquid/daily_usd_volume_by_crossed**: Retrieves the daily USD trading volume by crossed over time. Overlay of bar chart in `Cumulative total non-MM USD Volume` chart.
   - **GET /hyperliquid/daily_usd_volume_by_user**: Retrieves the daily USD trading volume by top 10 user and the rest are summed and marked as other. Overlay of bar chart in `Cumulative total non-MM USD Volume` chart.
   - **GET /hyperliquid/cumulative_trades**: Retrieves the cumulative number of trades over time. The line chart of `Cumulative total trades` chart.
   - **GET /hyperliquid/daily_trades**: Retrieves the daily number of trades. The bar chart of `Cumulative total trades` chart.
   - **GET /hyperliquid/daily_trades_by_coin**: Retrieves the daily number of trades by coin. Overlay of bar chart in `Cumulative total trades` chart.
   - **GET /hyperliquid/daily_trades_by_crossed**: Retrieves the daily number of trades by crossed. Overlay of bar chart in `Cumulative total trades` chart.
   - **GET /hyperliquid/daily_trades_by_user**: Retrieves the daily number of trades by top 10 user and the rest are summed and marked as other. Overlay of bar chart in `Cumulative total trades` chart.
   - **GET /hyperliquid/user_pnl**: Retrieves the profit and loss (PnL) for all users daily. The bar chart of `User PnL` chart.
   - **GET /hyperliquid/cumulative_user_pnl**: Retrieves the cumulative PnL for all users over time. The line chart of `User PnL` chart.
   - **GET /hyperliquid/hlp_liquidator_pnl**: Retrieves the PnL for liquidators daily. The bar chart of `HLP Liquidator PnL` chart.
   - **GET /hyperliquid/cumulative_hlp_liquidator_pnl**: Retrieves the cumulative PnL for liquidators over time. The line chart of `HLP Liquidator PnL` chart.
   - **GET /hyperliquid/cumulative_liquidated_notional**: Retrieves the cumulative liquidated notional value over time. The line chart of `Cumulative total notional liquidated` chart.
   - **GET /hyperliquid/daily_liquidated_notional**: Retrieves the daily liquidated notional value. The bar chart of `Cumulative total notional liquidated` chart.
   - **GET /hyperliquid/daily_notional_liquidated_by_leverage_type**: Retrieves the daily liquidated notional value by leverage type. Overlay of bar chart in `Cumulative total notional liquidated` chart.
   - **GET /hyperliquid/cumulative_unique_users**: Retrieves the cumulative number of unique users over time. The line chart of `Daily unique users` chart.
   - **GET /hyperliquid/daily_unique_users**: Retrieves the daily number of unique users. The bar chart of `Daily unique users` chart.
   - **GET /hyperliquid/daily_unique_users_by_coin**: Retrieves the daily number of unique users by coin. Overlay of bar chart in `Daily unique users` chart.
   - **GET /hyperliquid/cumulative_inflow**: Retrieves the cumulative inflow of funds over time. The line chart of `Cumulative inflow` chart.
   - **GET /hyperliquid/daily_inflow**: Retrieves the daily inflow of funds. The bar chart of `Cumulative inflow` chart.
   - **GET /hyperliquid/open_interest**: Retrieves the open interest data. The line chart of `Open interest` chart.
   - **GET /hyperliquid/funding_rate**: Retrieves the funding rate data. The line chart of `Funding rate` chart.
   - **GET /hyperliquid/liquidity_per_symbol**: Retrieves the liquidity data per symbol. The line chart of `Liquidity per symbol` chart.
   - **GET /hyperliquid/largest_users_by_usd_volume**: Retrieves the largest users by USD trading volume. The table of `Largest users by USD volume` table.
   - **GET /hyperliquid/largest_user_depositors**: Retrieves the largest user depositors. The table of `Largest user depositors` table.
   - **GET /hyperliquid/largest_liquidated_notional_by_user**: Retrieves the largest liquidated notional by user. The table of `Largest liquidated notional by user` table.
   - **GET /hyperliquid/largest_user_trade_count**: Retrieves the users with the highest trade counts. The table of `Largest user trade count` table.

   ### Note: The above endpoints support optional query parameters to filter the data based on specific criteria such as `start_date`, `end_date`, and `coins`.

4. Send HTTP requests to the desired endpoint(s) and retrieve the data or metrics in the response or navigate to `/hyperliquid/dashboard/` for the UI.

## Additional Information

### Directory Structure

The project follows the following directory structure:

```
.
├── app.py
├── config.example.json
├── config.json
├── docker-compose.yml
├── Dockerfile
├── pgdata
├── README.md
├── requirements.txt
├── scripts
│   └── main.py
└── tables.sql
```

- `app.py`: The main file that defines the FastAPI application and the API endpoints.
- `config.example.json`: An example configuration file. Copy and rename it to `config.json` and modify the values accordingly.
- `config.json`: The project configuration file. Contains database connection details and other configuration options.
- `docker-compose.yml`: The Docker Compose file for running the project containers.
- `Dockerfile`: The Dockerfile used to build the project image.
- `pgdata`: A directory used to persist the PostgreSQL database data.
- `README.md`: This README file providing detailed information about the project.
- `requirements.txt`: The file listing the Python dependencies required for the project.
- `scripts/main.py`: The script responsible for data extraction, loading, and caching.
- `tables.sql`: The SQL script containing the table definitions and indexes.

### Cron Job

To automate the data processing, you can set up a cron job to run the `main.py` script periodically. The script is located in the `scripts` directory. Use the following cron job configuration to execute the script every day at 3:00 AM:

```
0 3 * * * python /app/scripts/main.py
```

Make sure to adjust the path to the script based on your project's directory structure.

### Configuration

The project's configuration is stored in the `config.json` file. It includes the following settings:

- `db_uri`: The URI for connecting to the PostgreSQL database. Modify this based on your database configuration.
- `bucket_name`: The name of the AWS S3 bucket where the data files are stored.
- `aws_access_key_id`: The AWS access key ID for accessing the S3 bucket.
- `aws_secret_access_key`: The AWS secret access key for accessing the S3 bucket.
- `slack_token` (optional): The token for the Slack workspace where alerts will be sent, set to `""` to ignore.
- `tables`: List of tables to create data for from S3.

Update these settings according to your environment and requirements.

### Database Tables

The SQL script `tables.sql` contains the table definitions and indexes used by the project. The following tables are created:

- `liquidations`: Stores information about liquidations, including time, user, liquidated notional position, liquidated account value, and leverage type.
- `liquidations_cache`: Caches aggregated data for liquidations.
- `non_mm_ledger_updates`: Stores information about non-market-maker ledger updates, including time, user, and delta USD.
- `non_mm_trades`: Stores information about non-market-maker trades, including time, user, coin, side, price, size, and whether it was a crossed trade.
- `non_mm_trades_cache`: Caches aggregated data for non-market-maker trades.
- `non_mm_ledger_updates_cache`: Caches aggregated data for non-market-maker ledger updates.
- `account_values`: Stores account values, including time, user, is_vault flag, account value, cumulative volume, and cumulative ledger value.
- `account_values_cache`: Caches aggregated data for account values.
- `funding`: Stores funding information, including time, asset, funding rate, and premium.
- `funding_cache`: Caches aggregated data for funding.
- `asset_ctxs`: Stores asset contexts, including open interest, etc.
- `asset_ctxs_cache`: Caches aggregated data for asset contexts.
- `market_data`: Stores market data, including time, coin, median liquidity, and spread.
- `market_data_cache`: Caches aggregated data for market data.

These tables are used by the scripts and API endpoints to retrieve and process data.
