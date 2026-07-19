import asyncpg

# Store references to original functions
original_connect = asyncpg.connect
original_create_pool = asyncpg.create_pool

def _clean_dsn_and_get_ssl(dsn: str, kwargs: dict) -> str:
    if not dsn or not isinstance(dsn, str):
        return dsn

    # Normalize driver prefix
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    # Detect sslmode=require and set ssl="require" in kwargs if not already set
    if "sslmode=require" in dsn and "ssl" not in kwargs:
        kwargs["ssl"] = "require"

    # Strip parameters that asyncpg's connection parser doesn't support
    if "?" in dsn:
        base, query = dsn.split("?", 1)
        params = [p for p in query.split("&") if not p.startswith(("sslmode=", "channel_binding="))]
        if params:
            return f"{base}?{'&'.join(params)}"
        return base

    return dsn

async def patched_connect(dsn=None, *args, **kwargs):
    dsn = _clean_dsn_and_get_ssl(dsn, kwargs)
    return await original_connect(dsn, *args, **kwargs)

async def patched_create_pool(dsn=None, *args, **kwargs):
    dsn = _clean_dsn_and_get_ssl(dsn, kwargs)
    return await original_create_pool(dsn, *args, **kwargs)

# Apply the monkeypatch globally
asyncpg.connect = patched_connect
asyncpg.create_pool = patched_create_pool
