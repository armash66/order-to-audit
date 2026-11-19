from django.db import migrations


# A pre-existing singleton avoids first-post races when acquiring the factory lock.
def create_control(apps, schema_editor):
    apps.get_model("inventory", "FactoryControl").objects.create(id=1)


class Migration(migrations.Migration):
    dependencies = [("inventory", "0001_initial")]
    operations = [
        migrations.RunPython(create_control, migrations.RunPython.noop),
        migrations.RunSQL(
            """CREATE FUNCTION reject_stock_movement_change() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Stock movements are immutable; append a correction';
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER stock_movement_immutable
            BEFORE UPDATE OR DELETE ON inventory_stockmovement
            FOR EACH ROW EXECUTE FUNCTION reject_stock_movement_change();""",
            """DROP TRIGGER stock_movement_immutable ON inventory_stockmovement;
            DROP FUNCTION reject_stock_movement_change();""",
        ),
    ]
