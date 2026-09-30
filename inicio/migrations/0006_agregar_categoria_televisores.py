from django.db import migrations


def asegurar_categorias(apps, schema_editor):
    Categoria = apps.get_model('inicio', 'Categoria')
    categorias_requeridas = [
        {'id': 1, 'nombre': 'Laptops', 'slug': 'laptops-pc'},
        {'id': 2, 'nombre': 'Periféricos', 'slug': 'perifericos'},
        {'id': 3, 'nombre': 'Almacenamiento', 'slug': 'almacenamiento'},
        {'id': 4, 'nombre': 'Audio', 'slug': 'audio'},
        {'id': 5, 'nombre': 'Software & Antivirus', 'slug': 'software-antivirus'},
        {'id': 6, 'nombre': 'Partes de PC', 'slug': 'partes-pc'},
        {'id': 7, 'nombre': 'Zona Gamer', 'slug': 'zona-gamer'},
        {'id': 8, 'nombre': 'Monitores', 'slug': 'monitores'},
        {'id': 9, 'nombre': 'Computadoras & PCs', 'slug': 'pcs-escritorio'},
        {'id': 10, 'nombre': 'Televisores', 'slug': 'televisores'},
    ]
    for cat_data in categorias_requeridas:
        # Buscar por id o slug para evitar duplicar
        cat = Categoria.objects.filter(slug=cat_data['slug']).first()
        if not cat:
            cat = Categoria.objects.filter(id=cat_data['id']).first()
        if not cat:
            Categoria.objects.create(
                id=cat_data['id'],
                nombre=cat_data['nombre'],
                slug=cat_data['slug']
            )
        else:
            cat.nombre = cat_data['nombre']
            cat.slug = cat_data['slug']
            cat.save()

def revertir_categorias(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inicio', '0005_producto_almacenamiento_and_more'),
    ]

    operations = [
        migrations.RunPython(asegurar_categorias, revertir_categorias),
    ]

