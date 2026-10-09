from django.db import migrations


def agregar_categoria_impresoras(apps, schema_editor):
    Categoria = apps.get_model('inicio', 'Categoria')
    cat_data = {'id': 11, 'nombre': 'Impresoras', 'slug': 'impresoras'}

    # Buscar por slug, id o nombre para evitar duplicar
    cat = Categoria.objects.filter(slug=cat_data['slug']).first()
    if not cat:
        cat = Categoria.objects.filter(id=cat_data['id']).first()
    if not cat:
        cat = Categoria.objects.filter(nombre__iexact=cat_data['nombre']).first()

    if not cat:
        # Si el id 11 está libre, usarlo para mantener consistencia con los fixtures
        if not Categoria.objects.filter(id=cat_data['id']).exists():
            Categoria.objects.create(
                id=cat_data['id'],
                nombre=cat_data['nombre'],
                slug=cat_data['slug']
            )
        else:
            Categoria.objects.create(
                nombre=cat_data['nombre'],
                slug=cat_data['slug']
            )
    else:
        cat.nombre = cat_data['nombre']
        cat.slug = cat_data['slug']
        cat.save()

    # Si la base de datos es PostgreSQL (producción en Render), sincronizar la secuencia autoincremental
    if schema_editor.connection.vendor == 'postgresql':
        try:
            with schema_editor.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT setval(pg_get_serial_sequence('inicio_categoria', 'id'), COALESCE(MAX(id), 1)) FROM inicio_categoria;"
                )
        except Exception:
            pass


def revertir_categoria_impresoras(apps, schema_editor):
    Categoria = apps.get_model('inicio', 'Categoria')
    Categoria.objects.filter(slug='impresoras').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inicio', '0007_producto_url_origen'),
    ]

    operations = [
        migrations.RunPython(agregar_categoria_impresoras, revertir_categoria_impresoras),
    ]
