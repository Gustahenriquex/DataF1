"""PostgreSQL access and idempotent loads into the `raw` schema."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pandas as pd
from sqlalchemy import Engine, create_engine, inspect, text

from f1i.config import Settings

logger = logging.getLogger(__name__)
RAW_SCHEMA = "raw"


def get_engine(settings: Settings) -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


def replace_partition(
    engine: Engine, df: pd.DataFrame, table: str, keys: Sequence[str], schema: str = RAW_SCHEMA
) -> int:
    """Delete the rows matching `df`'s key values, then insert `df`, in one transaction.

    Re-running a load therefore replaces data instead of duplicating it.
    """
    if df.empty:
        logger.warning("nothing to load", extra={"table": table})
        return 0
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        if inspect(conn).has_table(table, schema=schema):
            where = " AND ".join(f'"{k}" = :{k}' for k in keys)
            for values in df[list(keys)].drop_duplicates().to_dict("records"):
                conn.execute(text(f'DELETE FROM "{schema}"."{table}" WHERE {where}'), values)
        df.to_sql(table, conn, schema=schema, if_exists="append", index=False, chunksize=2000)
    logger.info("loaded", extra={"table": f"{schema}.{table}", "rows": len(df)})
    return len(df)
