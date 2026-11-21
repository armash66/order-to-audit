"""Read-only row counts and content hashes for proving an in-place migration kept data."""

import json
from sqlalchemy import inspect, text
from api.database import engine


with engine.connect() as conn:
    with conn.begin():
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        result = {}
        for name in sorted(inspect(conn).get_table_names(schema="public")):
            if name == "alembic_version":
                continue
            identifier = conn.dialect.identifier_preparer.quote(name)
            row = conn.execute(
                text(
                    f"SELECT COUNT(*),md5(COALESCE(string_agg(row_to_json(t)::text,',' ORDER BY row_to_json(t)::text),'')) FROM public.{identifier} t"
                )
            ).one()
            result[name] = list(row)
        print(json.dumps(result, sort_keys=True))
