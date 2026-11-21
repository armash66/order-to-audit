"""Verify an existing database before adopting its unchanged schema into Alembic."""

from sqlalchemy import text


def signature(conn):
    queries = {
        "columns": """SELECT table_name,column_name,data_type,is_nullable,column_default,is_identity
            FROM information_schema.columns WHERE table_schema='public' AND table_name<>'alembic_version' AND table_name NOT LIKE 'factory_%'
            ORDER BY table_name,ordinal_position""",
        "constraints": """SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k
            JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname<>'alembic_version' AND c.relname NOT LIKE 'factory_%' ORDER BY c.relname,k.conname""",
        "indexes": """SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public'
            AND tablename<>'alembic_version' AND tablename NOT LIKE 'factory_%' ORDER BY tablename,indexname""",
        "triggers": """SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid),p.prosrc,t.tgenabled FROM pg_trigger t
            JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname='public' AND NOT t.tgisinternal
            ORDER BY c.relname,t.tgname""",
    }
    return {
        key: [list(row) for row in conn.execute(text(sql)).all()]
        for key, sql in queries.items()
    }
