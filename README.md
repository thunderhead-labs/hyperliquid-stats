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

   - **GET /hyperliquid/total_users**: Retrieves the total number of users.
   - **GET /hyperliquid/total_usd_volume**: Retrieves the total USD trading volume.
   - **GET /hyperliquid/total_deposits**: Retrieves the total amount of deposits.
   - **GET /hyperliquid/total_withdrawals**: Retrieves the total amount of withdrawals.
   - **GET /hyperliquid/total_notional_liquidated**: Retrieves the total notional value liquidated.
   - **GET /hyperliquid/cumulative_usd_volume**: Retrieves the cumulative USD trading volume over time.
   - **GET /hyperliquid/daily_usd_volume**: Retrieves the daily USD trading volume over time.
   - **GET /hyperliquid/daily_usd_volume_by_coin**: Retrieves the daily USD trading volume by coin over time.
   - **GET /hyperliquid/daily_usd_volume_by_crossed**: Retrieves the daily USD trading volume by crossed over time.
   - **GET /hyperliquid/daily_usd_volume_by_user**: Retrieves the daily USD trading volume by top 10 user and the rest are summed and marked as other.
   - **GET /hyperliquid/daily_trades**: Retrieves the daily number of trades.
   - **GET /hyperliquid/daily_trades_by_coin**: Retrieves the daily number of trades by coin.
   - **GET /hyperliquid/daily_trades_by_crossed**: Retrieves the daily number of trades by crossed.
   - **GET /hyperliquid/daily_trades_by_user**: Retrieves the daily number of trades by top 10 user and the rest are summed and marked as other.
   - **GET /hyperliquid/user_pnl**: Retrieves the profit and loss (PnL) for all users daily.
   - **GET /hyperliquid/cumulative_user_pnl**: Retrieves the cumulative PnL for all users over time.
   - **GET /hyperliquid/hlp_liquidator_pnl**: Retrieves the PnL for liquidators daily.
   - **GET /hyperliquid/cumulative_hlp_liquidator_pnl**: Retrieves the cumulative PnL for liquidators over time.
   - **GET /hyperliquid/cumulative_liquidated_notional**: Retrieves the cumulative liquidated notional value over time.
   - **GET /hyperliquid/daily_unique_users**: Retrieves the daily number of unique users.
   - **GET /hyperliquid/cumulative_users**: Retrieves the cumulative number of users over time.
   - **GET /hyperliquid/cumulative_inflow**: Retrieves the cumulative inflow of funds over time.
   - **GET /hyperliquid/open_interest**: Retrieves the open interest data.
   - **GET /hyperliquid/funding_rate**: Retrieves the funding rate data.
   - **GET /hyperliquid/cumulative_unique_users**: Retrieves the cumulative number of unique users over time.
   - **GET /hyperliquid/cumulative_inflow**: Retrieves the cumulative inflow of funds over time.
   - **GET /hyperliquid/daily_inflow**: Retrieves the daily inflow of funds.
   - **GET /hyperliquid/liquidity_per_symbol**: Retrieves the liquidity data per symbol.
   - **GET /hyperliquid/largest_users_by_usd_volume**: Retrieves the largest users by USD trading volume.
   - **GET /hyperliquid/largest_user_depositors**: Retrieves the largest user depositors.
   - **GET /hyperliquid/largest_liquidated_notional_by_user**: Retrieves the largest liquidated notional by user.
   - **GET /hyperliquid/largest_user_trade_count**: Retrieves the users with the highest trade counts.

   ### Note: The above endpoints support optional query parameters to filter the data based on specific criteria such as `start_date`, `end_date`, and `coins`.

4. Send HTTP requests to the desired endpoint(s) and retrieve the data or metrics in the response or navigate to `/hyperliquid/dashboard/` for the UI.
