import asyncio

import asyncpg


async def main():
    conn = await asyncpg.connect(
        user="postgres",
        password="Maha_251",
        host="localhost",
        port=5432,
        database="postgres",
    )
    await conn.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'lifelink_db' AND pid <> pg_backend_pid()"
    )
    await conn.execute("DROP DATABASE IF EXISTS lifelink_db")
    await conn.execute("CREATE DATABASE lifelink_db")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
