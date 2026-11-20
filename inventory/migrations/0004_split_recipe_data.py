from django.db import migrations, models
import django.db.models.deletion


# Move raw standards only; existing stock documents and movements stay untouched.
def split_recipes(apps, schema_editor):
    BOM = apps.get_model("inventory", "BOM")
    Recipe = apps.get_model("inventory", "Recipe")
    RecipeLine = apps.get_model("inventory", "RecipeLine")
    for bom in BOM.objects.select_related("sku__item"):
        recipe = Recipe.objects.create(code=bom.sku.item.code + "-RECIPE", version=bom.version)
        for line in bom.lines.filter(item__category="raw"):
            RecipeLine.objects.create(recipe=recipe, item_id=line.item_id, quantity=line.quantity)
        bom.lines.filter(item__category="raw").delete()
        bom.recipe = recipe
        bom.save(update_fields=["recipe"])


# Reconstruct the old per-SKU raw BOM lines when reversing the master-data split.
def merge_recipes(apps, schema_editor):
    BOM = apps.get_model("inventory", "BOM")
    BOMLine = apps.get_model("inventory", "BOMLine")
    for bom in BOM.objects.select_related("recipe"):
        for line in bom.recipe.lines.all():
            BOMLine.objects.create(bom=bom, item_id=line.item_id, quantity=line.quantity)
        bom.recipe = None
        bom.save(update_fields=["recipe"])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0003_recipe_bom_recipe_recipeline")]
    operations = [
        migrations.RunPython(split_recipes, merge_recipes),
        migrations.AlterField(model_name="bom", name="recipe", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="inventory.recipe")),
    ]
