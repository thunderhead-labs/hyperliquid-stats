import json
from datetime import datetime
from typing import Optional, List

from cachetools import TTLCache
from databases import Database
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Query
from sqlalchemy import (
    create_engine,
    Table,
    MetaData,
    distinct,
    func,
    literal,
    union_all,
)
from sqlalchemy.sql.expression import desc, select
from sqlalchemy.sql.functions import coalesce
from starlette.middleware.cors import CORSMiddleware

from metrics import measure_api_latency, update_is_online

# Load configuration from JSON file
with open("./config.json", "r") as config_file:
    config = json.load(config_file)

DATABASE_URL = config["db_uri"]

database = Database(DATABASE_URL)
engine = create_engine(DATABASE_URL)

metadata = MetaData()

non_mm_ledger_updates = Table("non_mm_ledger_updates", metadata, autoload_with=engine)
non_mm_trades_cache = Table("non_mm_trades_cache", metadata, autoload_with=engine)
non_mm_ledger_updates_cache = Table(
    "non_mm_ledger_updates_cache", metadata, autoload_with=engine
)
liquidations_cache = Table("liquidations_cache", metadata, autoload_with=engine)
account_values_cache = Table("account_values_cache", metadata, autoload_with=engine)
funding_cache = Table("funding_cache", metadata, autoload_with=engine)
asset_ctxs_cache = Table("asset_ctxs_cache", metadata, autoload_with=engine)
market_data_cache = Table("market_data_cache", metadata, autoload_with=engine)

hlp_vault_addresses = [
    "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303",
    "0x010461c14e146ac35fe42271bdc1134ee31c703a",
    "0x31ca8395cf837de08b24da3f660e77761dfb974b",
    "0x63c621a33714ec48660e32f2374895c8026a3a00",
]

app = FastAPI()
scheduler = BackgroundScheduler()

origins = config["origins"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cache = TTLCache(maxsize=500, ttl=86400)


def get_data_from_cache(key):
    if key in cache:
        return cache[key]
    return None


def add_data_to_cache(key, data):
    cache[key] = data


@app.on_event("startup")
async def startup():
    await database.connect()
    scheduler.add_job(update_is_online, "interval", seconds=60)
    scheduler.start()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()
    scheduler.shutdown()


def apply_filters(
    query, table, start_date, end_date, coins: Optional[List[str]] = None
):
    if start_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        query = query.where(table.c.time >= start_date)
    if end_date:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        query = query.where(table.c.time <= end_date)
    if coins:
        query = query.where(table.c.coin.in_(coins))
    return query


async def get_cumulative_chart_data(table, column, start_date, end_date, coins):
    async with database.transaction():
        # First, create a subquery that groups by date and sums the column
        subquery = select(
            table.c.time,
            func.sum(table.c[column]).label(column),
        ).group_by(table.c.time)
        subquery = apply_filters(subquery, table, start_date, end_date, coins)

        # Now we create a cumulative sum based on the subquery
        query = select(
            subquery.c.time,
            func.sum(subquery.c[column])
            .over(order_by=subquery.c.time)
            .label("cumulative"),
        )

        # Execute the query and fetch all rows
        rows = await database.fetch_all(query)

        # Convert the rows to a dictionary format for the response
        chart_data = [
            {
                "time": row["time"],
                "cumulative": row["cumulative"],
            }
            for row in rows
        ]

        return chart_data


@app.get("/hyperliquid/total_users")
@measure_api_latency(endpoint="total_users")
async def get_total_users(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"total_users_{start_date}_{end_date}_{coins}"
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"total_users": cached_data}

    query = select(
        func.count(distinct(non_mm_trades_cache.c.user)).label("total_users")
    )
    query = apply_filters(query, non_mm_trades_cache, start_date, end_date, coins)
    result = await database.fetch_one(query)

    # Cache result
    add_data_to_cache(key, result["total_users"])

    return {"total_users": result["total_users"]}


@app.get("/hyperliquid/total_usd_volume")
@measure_api_latency(endpoint="total_usd_volume")
async def get_total_volume(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"total_usd_volume_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"total_usd_volume": cached_data}

    query = select(
        func.sum(non_mm_trades_cache.c.usd_volume).label("total_usd_volume")
    ).select_from(non_mm_trades_cache)
    query = apply_filters(query, non_mm_trades_cache, start_date, end_date, coins)
    result = await database.fetch_one(query)

    # Cache result
    add_data_to_cache(key, result["total_usd_volume"])

    return {"total_usd_volume": result["total_usd_volume"]}


@app.get("/hyperliquid/total_deposits")
@measure_api_latency(endpoint="total_deposits")
async def get_total_deposits(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"total_deposits_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"total_deposits": cached_data}

    query = (
        select(func.sum(non_mm_ledger_updates.c.delta_usd).label("total_deposits"))
        .where(non_mm_ledger_updates.c.delta_usd > 0)
        .select_from(non_mm_ledger_updates)
    )
    query = apply_filters(query, non_mm_ledger_updates, start_date, end_date)
    result = await database.fetch_one(query)

    # Cache result
    add_data_to_cache(key, result["total_deposits"])

    return {"total_deposits": result["total_deposits"]}


@app.get("/hyperliquid/total_withdrawals")
@measure_api_latency(endpoint="total_withdrawals")
async def get_total_withdrawals(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"total_withdrawals_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"total_withdrawals": cached_data}

    query = (
        select(func.sum(non_mm_ledger_updates.c.delta_usd).label("total_withdrawals"))
        .where(non_mm_ledger_updates.c.delta_usd < 0)
        .select_from(non_mm_ledger_updates)
    )
    query = apply_filters(query, non_mm_ledger_updates, start_date, end_date)
    result = await database.fetch_one(query)

    # Cache result
    add_data_to_cache(key, result["total_withdrawals"])

    return {"total_withdrawals": result["total_withdrawals"]}


@app.get("/hyperliquid/total_notional_liquidated")
@measure_api_latency(endpoint="total_notional_liquidated")
async def get_total_notional_liquidated(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"total_notional_liquidated_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"total_notional_liquidated": cached_data}

    query = select(
        func.sum(liquidations_cache.c.sum_liquidated_ntl_pos).label(
            "total_notional_liquidated"
        )
    ).select_from(liquidations_cache)
    query = apply_filters(query, liquidations_cache, start_date, end_date)
    result = await database.fetch_one(query)

    # Cache result
    add_data_to_cache(key, result["total_notional_liquidated"])

    return {"total_notional_liquidated": result["total_notional_liquidated"]}


@app.get("/hyperliquid/cumulative_usd_volume")
@measure_api_latency(endpoint="cumulative_usd_volume")
async def get_cumulative_usd_volume(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"cumulative_usd_volume_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    chart_data = await get_cumulative_chart_data(
        non_mm_trades_cache, "usd_volume", start_date, end_date, coins
    )

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_usd_volume")
@measure_api_latency(endpoint="daily_usd_volume")
async def get_daily_usd_volume(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"daily_usd_volume_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                non_mm_trades_cache.c.time,
                func.sum(non_mm_trades_cache.c.usd_volume).label("daily_usd_volume"),
            )
            .group_by(non_mm_trades_cache.c.time)
            .order_by(non_mm_trades_cache.c.time)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date, coins)
        result = await database.fetch_all(query)
        chart_data = [
            {"time": row["time"], "daily_usd_volume": row["daily_usd_volume"]}
            for row in result
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_usd_volume_by_coin")
@measure_api_latency(endpoint="daily_usd_volume_by_coin")
async def get_daily_usd_volume_by_coin(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"daily_usd_volume_by_coin_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                non_mm_trades_cache.c.time,
                non_mm_trades_cache.c.coin,
                func.sum(non_mm_trades_cache.c.usd_volume).label("daily_usd_volume"),
            )
            .group_by(non_mm_trades_cache.c.time, non_mm_trades_cache.c.coin)
            .order_by(non_mm_trades_cache.c.time)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date)
        result = await database.fetch_all(query)
        chart_data = [
            {
                "time": row["time"],
                "coin": row["coin"],
                "daily_usd_volume": row["daily_usd_volume"],
            }
            for row in result
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_usd_volume_by_crossed")
@measure_api_latency(endpoint="daily_usd_volume_by_crossed")
async def get_daily_usd_volume_by_crossed(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"daily_usd_volume_by_crossed_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                non_mm_trades_cache.c.time,
                non_mm_trades_cache.c.crossed,
                func.sum(non_mm_trades_cache.c.usd_volume).label("daily_usd_volume"),
            )
            .group_by(non_mm_trades_cache.c.time, non_mm_trades_cache.c.crossed)
            .order_by(non_mm_trades_cache.c.time)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date)
        result = await database.fetch_all(query)
        chart_data = [
            {
                "time": row["time"],
                "crossed": row["crossed"],
                "daily_usd_volume": row["daily_usd_volume"],
            }
            for row in result
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_usd_volume_by_user")
@measure_api_latency(endpoint="daily_usd_volume_by_user")
async def get_daily_usd_volume_by_user(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"daily_usd_volume_by_user_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        base_query = select(
            non_mm_trades_cache.c.time.label("date"),
            non_mm_trades_cache.c.user,
            func.sum(non_mm_trades_cache.c.usd_volume).label("total_usd_volume"),
        ).group_by(non_mm_trades_cache.c.time, non_mm_trades_cache.c.user)

        base_query = apply_filters(
            base_query, non_mm_trades_cache, start_date, end_date
        )

        subquery = base_query.alias("daily_volume")

        # Define a subquery to get total volume for all users
        total_usd_volume_subquery = (
            select(
                subquery.c.date,
                func.sum(subquery.c.total_usd_volume).label("total_usd_volume"),
            ).group_by(subquery.c.date)
        ).alias("total_usd_volume")

        rank_subquery = (
            select(
                subquery.c.date,
                subquery.c.user,
                subquery.c.total_usd_volume,
                func.rank()
                .over(
                    partition_by=subquery.c.date,
                    order_by=subquery.c.total_usd_volume.desc(),
                )
                .label("user_rank"),
            )
        ).alias("rank_subquery")

        top_10_users_subquery = (
            select(
                rank_subquery.c.date,
                rank_subquery.c.user,
                rank_subquery.c.total_usd_volume,
            ).where(rank_subquery.c.user_rank <= 10)
        ).alias("top_10_users")

        top_users_per_day_subquery = (
            select(
                top_10_users_subquery.c.date,
                func.sum(top_10_users_subquery.c.total_usd_volume).label(
                    "top_users_total_usd_volume"
                ),
            ).group_by(top_10_users_subquery.c.date)
        ).alias("top_users_per_day")

        other_subquery = (
            select(
                total_usd_volume_subquery.c.date,
                literal("Other").label("user"),
                (
                        total_usd_volume_subquery.c.total_usd_volume
                        - coalesce(
                    top_users_per_day_subquery.c.top_users_total_usd_volume, 0
                )
                ).label("total_usd_volume"),
            ).select_from(
                total_usd_volume_subquery.join(
                    top_users_per_day_subquery,
                    total_usd_volume_subquery.c.date
                    == top_users_per_day_subquery.c.date,
                    isouter=True,
                )
            )
        ).alias("other")

        query = union_all(
            select(
                top_10_users_subquery.c.date,
                top_10_users_subquery.c.user,
                top_10_users_subquery.c.total_usd_volume,
            ),
            select(
                other_subquery.c.date,
                other_subquery.c.user,
                other_subquery.c.total_usd_volume,
            ),
        ).order_by("date")

        result = await database.fetch_all(query)
        chart_data = [
            {
                "time": row["date"],
                "user": row["user"],
                "daily_usd_volume": row["total_usd_volume"],
            }
            for row in result
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/cumulative_trades")
@measure_api_latency(endpoint="cumulative_trades")
async def get_cumulative_trades(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"cumulative_trades_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    chart_data = await get_cumulative_chart_data(
        non_mm_trades_cache, "group_count", start_date, end_date, coins
    )

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_trades")
@measure_api_latency(endpoint="daily_trades")
async def get_daily_trades(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"daily_trades_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                non_mm_trades_cache.c.time,
                func.sum(non_mm_trades_cache.c.group_count).label("daily_trades"),
            )
            .group_by(non_mm_trades_cache.c.time)
            .order_by(non_mm_trades_cache.c.time)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date, coins)
        result = await database.fetch_all(query)
        chart_data = [
            {"time": row["time"], "daily_trades": row["daily_trades"]} for row in result
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_trades_by_coin")
@measure_api_latency(endpoint="daily_trades_by_coin")
async def get_daily_trades_by_coin(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"daily_trades_by_coin_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                non_mm_trades_cache.c.time,
                non_mm_trades_cache.c.coin,
                func.sum(non_mm_trades_cache.c.group_count).label("daily_trades"),
            )
            .group_by(non_mm_trades_cache.c.time, non_mm_trades_cache.c.coin)
            .order_by(non_mm_trades_cache.c.time)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date)
        result = await database.fetch_all(query)
        chart_data = [
            {
                "time": row["time"],
                "coin": row["coin"],
                "daily_trades": row["daily_trades"],
            }
            for row in result
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_trades_by_crossed")
@measure_api_latency(endpoint="daily_trades_by_crossed")
async def get_daily_trades_by_crossed(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"daily_trades_by_crossed_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                non_mm_trades_cache.c.time,
                non_mm_trades_cache.c.crossed,
                func.sum(non_mm_trades_cache.c.group_count).label("daily_trades"),
            )
            .group_by(non_mm_trades_cache.c.time, non_mm_trades_cache.c.crossed)
            .order_by(non_mm_trades_cache.c.time)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date)
        result = await database.fetch_all(query)
        chart_data = [
            {
                "time": row["time"],
                "crossed": row["crossed"],
                "daily_trades": row["daily_trades"],
            }
            for row in result
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_trades_by_user")
@measure_api_latency(endpoint="daily_trades_by_user")
async def get_daily_trades_by_user(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"daily_trades_by_user_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        base_query = select(
            non_mm_trades_cache.c.time.label("date"),
            non_mm_trades_cache.c.user,
            func.sum(non_mm_trades_cache.c.group_count).label("total_group_count"),
        ).group_by(non_mm_trades_cache.c.time, non_mm_trades_cache.c.user)

        base_query = apply_filters(
            base_query, non_mm_trades_cache, start_date, end_date
        )

        subquery = base_query.alias("daily_volume")

        # Define a subquery to get total volume for all users
        total_group_count_subquery = (
            select(
                subquery.c.date,
                func.sum(subquery.c.total_group_count).label("total_group_count"),
            ).group_by(subquery.c.date)
        ).alias("total_group_count")

        rank_subquery = (
            select(
                subquery.c.date,
                subquery.c.user,
                subquery.c.total_group_count,
                func.rank()
                .over(
                    partition_by=subquery.c.date,
                    order_by=subquery.c.total_group_count.desc(),
                )
                .label("user_rank"),
            )
        ).alias("rank_subquery")

        top_10_users_subquery = (
            select(
                rank_subquery.c.date,
                rank_subquery.c.user,
                rank_subquery.c.total_group_count,
            ).where(rank_subquery.c.user_rank <= 10)
        ).alias("top_10_users")

        top_users_per_day_subquery = (
            select(
                top_10_users_subquery.c.date,
                func.sum(top_10_users_subquery.c.total_group_count).label(
                    "top_users_total_group_count"
                ),
            ).group_by(top_10_users_subquery.c.date)
        ).alias("top_users_per_day")

        other_subquery = (
            select(
                total_group_count_subquery.c.date,
                literal("Other").label("user"),
                (
                        total_group_count_subquery.c.total_group_count
                        - coalesce(
                    top_users_per_day_subquery.c.top_users_total_group_count, 0
                )
                ).label("total_group_count"),
            ).select_from(
                total_group_count_subquery.join(
                    top_users_per_day_subquery,
                    total_group_count_subquery.c.date
                    == top_users_per_day_subquery.c.date,
                    isouter=True,
                )
            )
        ).alias("other")

        query = union_all(
            select(
                top_10_users_subquery.c.date,
                top_10_users_subquery.c.user,
                top_10_users_subquery.c.total_group_count,
            ),
            select(
                other_subquery.c.date,
                other_subquery.c.user,
                other_subquery.c.total_group_count,
            ),
        ).order_by("date")

        result = await database.fetch_all(query)
        chart_data = [
            {
                "time": row["date"],
                "user": row["user"],
                "daily_group_count": row["total_group_count"],
            }
            for row in result
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/cumulative_user_pnl")
@measure_api_latency(endpoint="cumulative_user_pnl")
async def get_cumulative_user_pnl(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"cumulative_user_pnl_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        # Exclude vault addresses and filter on 'is_vault=false'
        subquery = (
            select(
                [
                    account_values_cache.c.time,
                    account_values_cache.c.sum_account_value,
                    account_values_cache.c.sum_cum_ledger,
                    func.lag(account_values_cache.c.sum_account_value)
                    .over(order_by=account_values_cache.c.time)
                    .label("previous_sum_account_value"),
                    func.lag(account_values_cache.c.sum_cum_ledger)
                    .over(order_by=account_values_cache.c.time)
                    .label("previous_sum_cum_ledger"),
                ]
            )
            .where(account_values_cache.c.user.notin_(hlp_vault_addresses))
            .where(account_values_cache.c.is_vault == False)
            .order_by(account_values_cache.c.time)
            .alias("subquery")
        )

        query = (
            select(
                [
                    subquery.c.time,
                    func.sum(
                        subquery.c.sum_account_value
                        - subquery.c.previous_sum_account_value
                        - (
                                subquery.c.sum_cum_ledger
                                - subquery.c.previous_sum_cum_ledger
                        )
                    )
                    .over(order_by=subquery.c.time)
                    .label("cumulative_pnl"),
                ]
            )
            .distinct(subquery.c.time)
            .select_from(subquery)
        )

        query = apply_filters(query, subquery, start_date, end_date, None)

        results = await database.fetch_all(query)
        chart_data = [{"time": row[0], "cumulative_pnl": row[1]} for row in results]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/user_pnl")
@measure_api_latency(endpoint="user_pnl")
async def get_user_pnl(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"user_pnl_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        # Exclude vault addresses and filter on 'is_vault=false'
        subquery = (
            select(
                [
                    account_values_cache.c.time,
                    account_values_cache.c.sum_account_value,
                    account_values_cache.c.sum_cum_ledger,
                    func.lag(account_values_cache.c.sum_account_value)
                    .over(order_by=account_values_cache.c.time)
                    .label("previous_sum_account_value"),
                    func.lag(account_values_cache.c.sum_cum_ledger)
                    .over(order_by=account_values_cache.c.time)
                    .label("previous_sum_cum_ledger"),
                ]
            )
            .where(account_values_cache.c.user.notin_(hlp_vault_addresses))
            .where(account_values_cache.c.is_vault == False)
            .order_by(account_values_cache.c.time)
            .alias("subquery")
        )

        query = (
            select(
                [
                    subquery.c.time,
                    func.sum(
                        subquery.c.sum_account_value
                        - subquery.c.previous_sum_account_value
                        - (
                                subquery.c.sum_cum_ledger
                                - subquery.c.previous_sum_cum_ledger
                        )
                    ).label("total_pnl"),
                ]
            )
            .select_from(subquery)
            .group_by(subquery.c.time)
        )

        query = apply_filters(query, subquery, start_date, end_date, None)

        results = await database.fetch_all(query)
        chart_data = [{"time": row[0], "total_pnl": row[1]} for row in results]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/hlp_liquidator_pnl")
@measure_api_latency(endpoint="hlp_liquidator_pnl")
async def get_hlp_liquidator_pnl(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"hlp_liquidator_pnl_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        # Include only vault addresses
        subquery = (
            select(
                [
                    account_values_cache.c.time,
                    account_values_cache.c.sum_account_value,
                    account_values_cache.c.sum_cum_ledger,
                    func.lag(account_values_cache.c.sum_account_value)
                    .over(order_by=account_values_cache.c.time)
                    .label("previous_sum_account_value"),
                    func.lag(account_values_cache.c.sum_cum_ledger)
                    .over(order_by=account_values_cache.c.time)
                    .label("previous_sum_cum_ledger"),
                ]
            )
            .where(account_values_cache.c.user.in_(hlp_vault_addresses))
            .order_by(account_values_cache.c.time)
            .alias("subquery")
        )

        query = (
            select(
                [
                    subquery.c.time,
                    func.sum(
                        subquery.c.sum_account_value
                        - subquery.c.previous_sum_account_value
                        - (
                                subquery.c.sum_cum_ledger
                                - subquery.c.previous_sum_cum_ledger
                        )
                    ).label("total_pnl"),
                ]
            )
            .select_from(subquery)
            .group_by(subquery.c.time)
        )

        query = apply_filters(query, account_values_cache, start_date, end_date, None)

        results = await database.fetch_all(query)
        chart_data = [{"time": row[0], "total_pnl": row[1]} for row in results]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/cumulative_hlp_liquidator_pnl")
@measure_api_latency(endpoint="cumulative_hlp_liquidator_pnl")
async def get_cumulative_hlp_liquidator_pnl(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"cumulative_hlp_liquidator_pnl_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        # Include only vault addresses
        subquery = (
            select(
                [
                    account_values_cache.c.time,
                    account_values_cache.c.sum_account_value,
                    account_values_cache.c.sum_cum_ledger,
                    func.lag(account_values_cache.c.sum_account_value)
                    .over(order_by=account_values_cache.c.time)
                    .label("previous_sum_account_value"),
                    func.lag(account_values_cache.c.sum_cum_ledger)
                    .over(order_by=account_values_cache.c.time)
                    .label("previous_sum_cum_ledger"),
                ]
            )
            .where(account_values_cache.c.user.in_(hlp_vault_addresses))
            .order_by(account_values_cache.c.time)
            .alias("subquery")
        )

        query = (
            select(
                [
                    subquery.c.time,
                    func.sum(
                        subquery.c.sum_account_value
                        - subquery.c.previous_sum_account_value
                        - (
                                subquery.c.sum_cum_ledger
                                - subquery.c.previous_sum_cum_ledger
                        )
                    )
                    .over(order_by=subquery.c.time)
                    .label("cumulative_pnl"),
                ]
            )
            .distinct(subquery.c.time)
            .select_from(subquery)
        )

        query = apply_filters(query, account_values_cache, start_date, end_date, None)

        results = await database.fetch_all(query)
        chart_data = [{"time": row[0], "cumulative_pnl": row[1]} for row in results]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/cumulative_liquidated_notional")
@measure_api_latency(endpoint="cumulative_liquidated_notional")
async def get_cumulative_liquidated_notional(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"cumulative_liquidated_notional_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        chart_data = await get_cumulative_chart_data(
            liquidations_cache, "sum_liquidated_ntl_pos", start_date, end_date, None
        )

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_notional_liquidated_total")
@measure_api_latency(endpoint="daily_notional_liquidated_total")
async def get_daily_notional_liquidated_total(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"daily_notional_liquidated_total_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                liquidations_cache.c.time,
                func.sum(liquidations_cache.c.sum_liquidated_ntl_pos).label(
                    "daily_notional_liquidated"
                ),
            )
            .group_by(liquidations_cache.c.time)
            .order_by(liquidations_cache.c.time)
        )
        query = apply_filters(query, liquidations_cache, start_date, end_date)
        results = await database.fetch_all(query)
        chart_data = [
            {
                "time": row["time"],
                "daily_notional_liquidated": row["daily_notional_liquidated"],
            }
            for row in results
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_notional_liquidated_by_leverage_type")
@measure_api_latency(endpoint="daily_notional_liquidated_by_leverage_type")
async def get_daily_notional_liquidated_by_leverage_type(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"daily_notional_liquidated_by_leverage_type_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                liquidations_cache.c.time,
                liquidations_cache.c.leverage_type,
                func.sum(liquidations_cache.c.sum_liquidated_ntl_pos).label(
                    "daily_notional_liquidated"
                ),
            )
            .group_by(liquidations_cache.c.time, liquidations_cache.c.leverage_type)
            .order_by(liquidations_cache.c.time)
        )
        query = apply_filters(query, liquidations_cache, start_date, end_date)
        results = await database.fetch_all(query)
        chart_data = [
            {
                "time": row["time"],
                "leverage_type": row["leverage_type"],
                "daily_notional_liquidated": row["daily_notional_liquidated"],
            }
            for row in results
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_unique_users")
@measure_api_latency(endpoint="daily_unique_users")
async def get_daily_unique_users(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"daily_unique_users_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                non_mm_trades_cache.c.time,
                func.count(distinct(non_mm_trades_cache.c.user)).label(
                    "daily_unique_users"
                ),
            )
            .group_by(non_mm_trades_cache.c.time)
            .order_by(non_mm_trades_cache.c.time)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date, coins)
        results = await database.fetch_all(query)
        chart_data = [
            {"time": row["time"], "daily_unique_users": row["daily_unique_users"]}
            for row in results
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_unique_users_by_coin")
@measure_api_latency(endpoint="daily_unique_users_by_coin")
async def get_daily_unique_users_by_coin(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"daily_unique_users_by_coin_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        # Get the total unique users per day
        total_users_query = (
            select(
                non_mm_trades_cache.c.time,
                func.count(distinct(non_mm_trades_cache.c.user)).label(
                    "total_unique_users"
                ),
            )
            .group_by(non_mm_trades_cache.c.time)
            .order_by(non_mm_trades_cache.c.time)
        )
        total_users_query = apply_filters(
            total_users_query, non_mm_trades_cache, start_date, end_date
        )
        total_users_results = await database.fetch_all(total_users_query)
        total_users_data = {
            row["time"]: row["total_unique_users"] for row in total_users_results
        }

        # Get the daily unique users by coin
        query = (
            select(
                non_mm_trades_cache.c.time,
                non_mm_trades_cache.c.coin,
                func.count(distinct(non_mm_trades_cache.c.user)).label(
                    "daily_unique_users"
                ),
            )
            .group_by(non_mm_trades_cache.c.time, non_mm_trades_cache.c.coin)
            .order_by(non_mm_trades_cache.c.time)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date)
        results = await database.fetch_all(query)

        chart_data = []
        for row in results:
            time = row["time"]
            coin = row["coin"]
            daily_unique_users = row["daily_unique_users"]
            total_unique_users = total_users_data.get(
                time, 1
            )  # Default to 1 to avoid division by zero

            percentage_of_total_users = daily_unique_users / total_unique_users
            chart_data.append(
                {
                    "time": time,
                    "coin": coin,
                    "daily_unique_users": daily_unique_users,
                    "percentage_of_total_users": percentage_of_total_users,
                }
            )

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/open_interest")
@measure_api_latency(endpoint="open_interest")
async def get_open_interest(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    coins: Optional[List[str]] = None,
):
    # Create unique key using filters and endpoint name
    key = f"open_interest_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                asset_ctxs_cache.c.time,
                asset_ctxs_cache.c.coin,
                (func.sum(asset_ctxs_cache.c.sum_open_interest)
                 * func.avg(asset_ctxs_cache.c.avg_oracle_px)).label("open_interest"),
            )
            .group_by(
                asset_ctxs_cache.c.time,
                asset_ctxs_cache.c.coin,
            )
            .order_by(asset_ctxs_cache.c.time)
        )
        query = apply_filters(query, asset_ctxs_cache, start_date, end_date, coins)
        results = await database.fetch_all(query)
        chart_data = [
            {
                "time": row["time"],
                "coin": row["coin"],
                "open_interest": row["open_interest"],
            }
            for row in results
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/funding_rate")
@measure_api_latency(endpoint="funding_rate")
async def get_funding_rate(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"funding_rate_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        query = (
            select(
                funding_cache.c.time,
                funding_cache.c.coin,
                func.sum(funding_cache.c.sum_funding).label("sum_funding"),
            )
            .group_by(funding_cache.c.time, funding_cache.c.coin)
            .order_by(funding_cache.c.time)
        )
        query = apply_filters(query, funding_cache, start_date, end_date, coins)
        results = await database.fetch_all(query)
        chart_data = [
            {
                "time": row["time"],
                "coin": row["coin"],
                "sum_funding": row["sum_funding"] * 365,
            }
            for row in results
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/cumulative_new_users")
@measure_api_latency(endpoint="cumulative_new_users")
async def get_cumulative_new_users(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"cumulative_new_users_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        # Apply filters to non_mm_trades_cache
        filtered_trades = apply_filters(
            non_mm_trades_cache.select(),
            non_mm_trades_cache,
            start_date,
            end_date,
            coins,
        )

        # Create subquery to get the first trade date for each user
        subquery = (
            select(
                filtered_trades.c.user,
                func.min(filtered_trades.c.time).label("first_trade_date"),
            ).group_by(filtered_trades.c.user)
        ).alias("user_first_trade_dates")

        # Now select the date and count distinct users by date
        query = select(
            subquery.c.first_trade_date.label("date"),
            func.count(subquery.c.user).label("daily_new_users"),
        ).group_by(subquery.c.first_trade_date)

        # Then select date, daily_new_users, and the cumulative count of unique users
        final_query = select(
            query.c.date,
            query.c.daily_new_users,
            func.sum(query.c.daily_new_users)
            .over(order_by=query.c.date)
            .label("cumulative_new_users"),
        )

        # Execute the final query
        results = await database.fetch_all(final_query)

        # Convert result to JSON-serializable format
        chart_data = [
            {
                "time": row["date"],
                "daily_new_users": row["daily_new_users"],
                "cumulative_new_users": row["cumulative_new_users"],
            }
            for row in results
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/cumulative_inflow")
@measure_api_latency(endpoint="cumulative_inflow")
async def get_cumulative_inflow(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"cumulative_inflow_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        base_query = (
            select(
                non_mm_ledger_updates_cache.c.time,
                func.sum(non_mm_ledger_updates_cache.c.sum_delta_usd).label(
                    "inflow_per_day"
                ),
            )
            .group_by(non_mm_ledger_updates_cache.c.time)
            .order_by(non_mm_ledger_updates_cache.c.time)
        )

        filtered_base_query = apply_filters(
            base_query, non_mm_ledger_updates_cache, start_date, end_date
        )

        query = filtered_base_query.alias("inflows_per_day")

        cumulative_query = select(
            query.c.time,
            func.sum(query.c.inflow_per_day)
            .over(order_by=query.c.time)
            .label("cumulative_inflow"),
        ).order_by(query.c.time)

        results = await database.fetch_all(cumulative_query)
        chart_data = [
            {"time": row["time"], "cumulative_inflow": row["cumulative_inflow"]}
            for row in results
        ]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_inflow")
@measure_api_latency(endpoint="daily_inflow")
async def get_daily_inflow(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"daily_inflow_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"chart_data": cached_data}

    async with database.transaction():
        base_query = (
            select(
                non_mm_ledger_updates_cache.c.time,
                func.sum(non_mm_ledger_updates_cache.c.sum_delta_usd).label(
                    "inflow_per_day"
                ),
            )
            .group_by(non_mm_ledger_updates_cache.c.time)
            .order_by(non_mm_ledger_updates_cache.c.time)
        )

        filtered_base_query = apply_filters(
            base_query, non_mm_ledger_updates_cache, start_date, end_date
        )

        query = select(
            filtered_base_query.c.time.label("time"),
            filtered_base_query.c.inflow_per_day.label("inflow"),
        ).alias("inflows_per_day")

        results = await database.fetch_all(query)
        chart_data = [{"time": row["time"], "inflow": row["inflow"]} for row in results]

    # Cache result
    add_data_to_cache(key, chart_data)

    return {"chart_data": chart_data}


@app.get("/hyperliquid/liquidity_by_coin")
@measure_api_latency(endpoint="liquidity_by_coin")
async def get_liquidity_by_coin(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        notional_amounts: Optional[List[int]] = Query([1000, 3000, 10000]),
):
    # Create unique key using filters and endpoint name
    key = f"liquidity_by_coin_{start_date}_{end_date}_{notional_amounts}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return cached_data

    async with database.transaction():
        data = {}
        for notional in notional_amounts:
            query = (
                select(
                    market_data_cache.c.time,
                    market_data_cache.c.coin,
                    func.avg(market_data_cache.c.median_liquidity / notional).label(
                        "average_liquidity_percentage"
                    ),
                )
                .group_by(market_data_cache.c.time, market_data_cache.c.coin)
                .order_by(market_data_cache.c.time, market_data_cache.c.coin)
            )
            query = apply_filters(query, market_data_cache, start_date, end_date)

            results = await database.fetch_all(query)

            # Collect data
            for row in results:
                time = row[0]
                coin = row[1]
                average_liquidity_percentage = row[2]
                if coin not in data:
                    data[coin] = {}
                if notional not in data[coin]:
                    data[coin][notional] = []
                data[coin][notional].append(
                    {
                        "time": time,
                        "average_liquidity_percentage": average_liquidity_percentage,
                    }
                )

        # Cache result
        add_data_to_cache(key, data)

        return data


async def get_table_data(
    table, group_by_column, sum_column, start_date, end_date, coins, limit
):
    async with database.transaction():
        query = (
            select(
                table.c[group_by_column],
                func.sum(table.c[sum_column]).label(sum_column),
            )
            .group_by(table.c[group_by_column])
            .order_by(desc(sum_column))
            .limit(limit)
        )
        query = apply_filters(query, table, start_date, end_date, coins)
        results = await database.fetch_all(query)
        table_data = [
            {"name": row[group_by_column], "value": row[sum_column]} for row in results
        ]
        return table_data


@app.get("/hyperliquid/largest_users_by_usd_volume")
@measure_api_latency(endpoint="largest_users_by_usd_volume")
async def get_largest_users_by_usd_volume(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"largest_users_by_usd_volume_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"table_data": cached_data}

    table_data = await get_table_data(
        non_mm_trades_cache,
        "user",
        "usd_volume",
        start_date,
        end_date,
        coins,
        1000,
    )

    # Cache result
    add_data_to_cache(key, table_data)

    return {"table_data": table_data}


@app.get("/hyperliquid/largest_user_depositors")
@measure_api_latency(endpoint="largest_user_depositors")
async def get_largest_user_depositors(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"largest_user_depositors_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"table_data": cached_data}

    table_data = await get_table_data(
        non_mm_ledger_updates_cache,
        "user",
        "sum_delta_usd",
        start_date,
        end_date,
        None,
        1000,
    )

    # Cache result
    add_data_to_cache(key, table_data)

    return {"table_data": table_data}


@app.get("/hyperliquid/largest_liquidated_notional_by_user")
@measure_api_latency(endpoint="largest_liquidated_notional_by_user")
async def get_largest_liquidated_notional_by_user(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
):
    # Create unique key using filters and endpoint name
    key = f"largest_liquidated_notional_by_user_{start_date}_{end_date}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"table_data": cached_data}

    table_data = await get_table_data(
        liquidations_cache,
        "user",
        "sum_liquidated_account_value",
        start_date,
        end_date,
        None,
        1000,
    )

    # Cache result
    add_data_to_cache(key, table_data)

    return {"table_data": table_data}


@app.get("/hyperliquid/largest_user_trade_count")
@measure_api_latency(endpoint="largest_user_trade_count")
async def get_largest_user_trade_count(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        coins: Optional[List[str]] = Query(None),
):
    # Create unique key using filters and endpoint name
    key = f"largest_user_trade_count_{start_date}_{end_date}_{coins}"

    # Check if the data exists in the cache
    cached_data = get_data_from_cache(key)
    if cached_data:
        return {"table_data": cached_data}

    async with database.transaction():
        query = (
            select(
                non_mm_trades_cache.c["user"],
                func.sum(non_mm_trades_cache.c["group_count"]).label("trade_count"),
            )
            .group_by(non_mm_trades_cache.c["user"])
            .order_by(desc("trade_count"))
            .limit(1000)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date, coins)
        results = await database.fetch_all(query)
        table_data = [
            {"name": row["user"], "value": row["trade_count"]} for row in results
        ]

    # Cache result
    add_data_to_cache(key, table_data)

    return {"table_data": table_data}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
