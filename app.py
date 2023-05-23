import json
from typing import Optional, List

from fastapi import FastAPI, Query
from sqlalchemy import create_engine, Table, MetaData, distinct
from sqlalchemy.sql import select, func
from sqlalchemy.sql.expression import desc

# Load configuration from JSON file
with open("./config.json", "r") as config_file:
    config = json.load(config_file)

DATABASE_URL = config["db_uri"]
engine = create_engine(DATABASE_URL)

metadata = MetaData()

non_mm_trades_cache = Table("non_mm_trades_cache", metadata, autoload_with=engine)
non_mm_ledger_updates_cache = Table(
    "non_mm_ledger_updates_cache", metadata, autoload_with=engine
)
liquidations_cache = Table("liquidations_cache", metadata, autoload_with=engine)

hlp_vault_addresses = [
    "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303",
    "0x010461c14e146ac35fe42271bdc1134ee31c703a",
    "0x31ca8395cf837de08b24da3f660e77761dfb974b",
    "0x63c621a33714ec48660e32f2374895c8026a3a00"
]

app = FastAPI()


def apply_filters(query, table, start_date, end_date, coins: Optional[List[str]] = None):
    if start_date:
        query = query.where(table.c.time >= start_date)
    if end_date:
        query = query.where(table.c.time <= end_date)
    if coins:
        query = query.where(table.c.coin.in_(coins))
    return query


@app.get("/hyperliquid/total_users")
async def get_total_users(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    coins: Optional[List[str]] = Query(None),
):
    with engine.begin() as connection:
        query = select(func.count().label("total_users")).select_from(
            non_mm_trades_cache
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date, coins)
        result = connection.execute(query)
        return {"total_users": result.scalar()}


@app.get("/hyperliquid/total_usd_volume")
async def get_total_volume(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    coins: Optional[List[str]] = Query(None),
):
    with engine.begin() as connection:
        query = select(
            func.sum(
                non_mm_trades_cache.c.usd_volume
            ).label("total_usd_volume")
        ).select_from(non_mm_trades_cache)
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date, coins)
        result = connection.execute(query)
        return {"total_usd_volume": result.scalar()}


@app.get("/hyperliquid/total_notional_liquidated")
async def get_total_notional_liquidated(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    with engine.begin() as connection:
        query = select(
            func.sum(liquidations_cache.c.sum_liquidated_ntl_pos).label(
                "total_notional_liquidated"
            )
        ).select_from(liquidations_cache)
        query = apply_filters(query, liquidations_cache, start_date, end_date)
        result = connection.execute(query)
        return {"total_notional_liquidated": result.scalar()}


@app.get("/hyperliquid/daily_trades")
async def get_daily_trades(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    coins: Optional[List[str]] = Query(None),
):
    with engine.begin() as connection:
        query = (
            select(
                non_mm_trades_cache.c.time,
                func.count(non_mm_trades_cache.c.user).label("daily_trades"),
            )
            .group_by(non_mm_trades_cache.c.time)
            .order_by(non_mm_trades_cache.c.time)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date, coins)
        result = connection.execute(query)
        chart_data = [
            {"date": row.time, "daily_trades": row.daily_trades} for row in result
        ]
        return {"chart_data": chart_data}


@app.get("/hyperliquid/daily_unique_users")
async def get_daily_unique_users(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    coins: Optional[List[str]] = Query(None),
):
    with engine.begin() as connection:
        query = (
            select(
                non_mm_trades_cache.c.time,
                func.count(distinct(non_mm_trades_cache.c.user)).label("daily_unique_users"),
            )
            .group_by(non_mm_trades_cache.c.time)
            .order_by(non_mm_trades_cache.c.time)
        )
        query = apply_filters(query, non_mm_trades_cache, start_date, end_date, coins)
        result = connection.execute(query)
        chart_data = [
            {"time": row.time, "daily_unique_users": row.daily_unique_users}
            for row in result
        ]
        return {"chart_data": chart_data}


def get_table_data(table, group_by_column, sum_column, start_date, end_date, coins, limit):
    with engine.begin() as connection:
        query = (
            select(table.c[group_by_column], func.sum(table.c[sum_column]).label(sum_column))
            .group_by(table.c[group_by_column])
            .order_by(desc(sum_column))
            .limit(limit)
        )
        query = apply_filters(query, table, start_date, end_date, coins)
        result = connection.execute(query)
        table_data = [
            {"name": row[group_by_column], "value": row[sum_column]} for row in result
        ]
        return table_data


@app.get("/hyperliquid/largest_users_by_usd_volume")
async def get_largest_users_by_usd_volume(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    coins: Optional[List[str]] = Query(None),
):
    return {
        "table_data": get_table_data(
            non_mm_trades_cache, "user", "usd_volume", start_date, end_date, coins, 10
        )
    }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
