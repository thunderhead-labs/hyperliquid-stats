CREATE TABLE IF NOT EXISTS public.liquidations
(
    "time" timestamp with time zone NOT NULL,
    "user" character varying(255) COLLATE pg_catalog."default" NOT NULL,
    liquidated_ntl_pos double precision NOT NULL,
    liquidated_account_value double precision NOT NULL,
    leverage_type character varying(255) COLLATE pg_catalog."default" NOT NULL
);

CREATE TABLE IF NOT EXISTS public.non_mm_ledger_updates
(
    "time" timestamp with time zone NOT NULL,
    "user" character varying(255) COLLATE pg_catalog."default" NOT NULL,
    delta_usd double precision NOT NULL
);

CREATE TABLE IF NOT EXISTS public.non_mm_trades
(
    "time" timestamp with time zone NOT NULL,
    "user" character varying(255) COLLATE pg_catalog."default" NOT NULL,
    coin character varying(255) COLLATE pg_catalog."default" NOT NULL,
    side character varying(255) COLLATE pg_catalog."default" NOT NULL,
    px double precision NOT NULL,
    sz double precision NOT NULL,
    crossed boolean NOT NULL,
    special_trade_type character varying(255) COLLATE pg_catalog."default" NOT NULL
);

-- create indexes for liquidations table
CREATE INDEX IF NOT EXISTS idx_liquidations_time ON public.liquidations ("time");
CREATE INDEX IF NOT EXISTS idx_liquidations_user ON public.liquidations ("user");

-- create indexes for non_mm_ledger_updates table
CREATE INDEX IF NOT EXISTS idx_ledger_updates_time ON public.non_mm_ledger_updates ("time");
CREATE INDEX IF NOT EXISTS idx_ledger_updates_user ON public.non_mm_ledger_updates ("user");

-- create indexes for non_mm_trades table
CREATE INDEX IF NOT EXISTS idx_trades_time ON public.non_mm_trades ("time");
CREATE INDEX IF NOT EXISTS idx_trades_user ON public.non_mm_trades ("user");

CREATE TABLE IF NOT EXISTS public.non_mm_trades_cache
(
    "time" timestamp NOT NULL,
    "user" character varying(255) COLLATE pg_catalog."default" NOT NULL,
    coin character varying(255) COLLATE pg_catalog."default" NOT NULL,
    side character varying(255) COLLATE pg_catalog."default" NOT NULL,
    crossed boolean NOT NULL,
    special_trade_type character varying(255) COLLATE pg_catalog."default" NOT NULL,
    mean_px double precision NOT NULL,
    sum_sz double precision NOT NULL,
    usd_volume double precision NOT NULL,
    group_count integer NOT NULL
);

CREATE INDEX idx_non_mm_trades_cache
ON public.non_mm_trades_cache ("time", "user", coin, side, crossed);


CREATE TABLE IF NOT EXISTS public.non_mm_ledger_updates_cache
(
    "time" timestamp NOT NULL,
    "user" character varying(255) COLLATE pg_catalog."default" NOT NULL,
    sum_delta_usd double precision NOT NULL
);

CREATE INDEX idx_non_mm_ledger_updates_cache
ON public.non_mm_ledger_updates_cache ("time", "user");


CREATE TABLE IF NOT EXISTS public.liquidations_cache
(
    "time" timestamp NOT NULL,
    "user" character varying(255) COLLATE pg_catalog."default" NOT NULL,
    leverage_type character varying(255) COLLATE pg_catalog."default" NOT NULL,
    sum_liquidated_ntl_pos double precision NOT NULL,
    sum_liquidated_account_value double precision NOT NULL
);

CREATE INDEX idx_liquidations_cache
ON public.liquidations_cache ("time", "user", leverage_type);

CREATE TABLE account_values (
    "time" TIMESTAMP WITH TIME ZONE NOT NULL,
    "user" VARCHAR(255) NOT NULL,
    is_vault BOOLEAN NOT NULL,
    account_value FLOAT NOT NULL,
    cum_vlm FLOAT NOT NULL,
    cum_ledger FLOAT NOT NULL
);

CREATE INDEX idx_userdata_time ON account_values ("time");
CREATE INDEX idx_userdata_user ON account_values ("user");

CREATE TABLE IF NOT EXISTS public.account_values_cache
(
    "time" timestamp NOT NULL,
    "user" character varying(255) COLLATE pg_catalog."default" NOT NULL,
    is_vault BOOLEAN NOT NULL,
    last_account_value double precision NOT NULL,
    last_cum_vlm double precision NOT NULL,
    last_cum_ledger double precision NOT NULL
);

CREATE INDEX idx_account_values_cache
ON public.account_values_cache ("time", "user", is_vault);

CREATE TABLE funding (
    "time" TIMESTAMP WITH TIME ZONE NOT NULL,
    coin character varying(255) COLLATE pg_catalog."default" NOT NULL,
    funding FLOAT NOT NULL,
    premium FLOAT NOT NULL
);

CREATE INDEX idx_assetdata_time ON funding ("time");
CREATE INDEX idx_assetdata_asset ON funding (coin);

CREATE TABLE IF NOT EXISTS public.funding_cache
(
    "time" timestamp NOT NULL,
    coin character varying(255) COLLATE pg_catalog."default" NOT NULL,
    sum_funding double precision NOT NULL,
    sum_premium double precision NOT NULL
);

CREATE INDEX idx_funding_cache
ON public.funding_cache ("time", coin);

CREATE TABLE IF NOT EXISTS public.asset_ctxs
(
    "time" timestamp with time zone NOT NULL,
    "coin" character varying(255) COLLATE pg_catalog."default" NOT NULL,
    "funding" double precision NOT NULL,
    "open_interest" double precision NOT NULL,
    "prev_day_px" double precision NOT NULL,
    "day_ntl_vlm" double precision NOT NULL,
    "premium" double precision NOT NULL,
    "oracle_px" double precision NOT NULL,
    "mark_px" double precision NOT NULL,
    "mid_px" double precision NOT NULL,
    "impact_bid_px" double precision NOT NULL,
    "impact_ask_px" double precision NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_asset_ctxs_time ON public.asset_ctxs ("time");
CREATE INDEX IF NOT EXISTS idx_asset_ctxs_coin ON public.asset_ctxs ("coin");

CREATE TABLE IF NOT EXISTS public.asset_ctxs_cache
(
    "time" timestamp NOT NULL,
    "coin" character varying(255) COLLATE pg_catalog."default" NOT NULL,
    sum_funding double precision NOT NULL,
    avg_open_interest double precision NOT NULL,
    avg_prev_day_px double precision NOT NULL,
    sum_day_ntl_vlm double precision NOT NULL,
    avg_premium double precision NOT NULL,
    avg_oracle_px double precision NOT NULL,
    avg_mark_px double precision NOT NULL,
    avg_mid_px double precision NOT NULL,
    avg_impact_bid_px double precision NOT NULL,
    avg_impact_ask_px double precision NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_asset_ctxs_cache_time ON public.asset_ctxs_cache ("time");
CREATE INDEX IF NOT EXISTS idx_asset_ctxs_cache_coin ON public.asset_ctxs_cache ("coin");

CREATE TABLE market_data (
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    ver_num INTEGER NOT NULL,
    channel VARCHAR(255) NOT NULL,
    coin VARCHAR(255) NOT NULL,
    raw_time BIGINT NOT NULL,
    liquidity double precision NOT NULL,
    levels JSON NOT NULL
);

CREATE INDEX idx_market_data_time ON market_data(time);
CREATE INDEX idx_market_data_channel ON market_data(channel);
CREATE INDEX idx_market_data_coin ON market_data(coin);

CREATE TABLE market_data_cache (
    time DATE NOT NULL,
    coin VARCHAR(255) NOT NULL,
    mid_price DOUBLE PRECISION NOT NULL,
    median_liquidity DOUBLE PRECISION NOT NULL,
    median_slippage_0 DOUBLE PRECISION NOT NULL,
    median_slippage_1000 DOUBLE PRECISION NOT NULL,
    median_slippage_3000 DOUBLE PRECISION NOT NULL,
    median_slippage_10000 DOUBLE PRECISION NOT NULL
);

CREATE INDEX idx_market_data_cache_time ON market_data_cache(time);
CREATE INDEX idx_market_data_cache_coin ON market_data_cache(coin);

