from django.db import migrations


def actualizar_marcas_productos(apps, schema_editor):
    Producto = apps.get_model('inicio', 'Producto')

    # Mapeo específico por IDs conocidos
    marcas_por_id = {
        1: 'Lenovo',
        2: 'Logitech',
        3: 'Redragon',
        4: 'Kingston',
        5: 'HyperX',
        6: 'Seagate',
        7: 'ASUS',
        8: 'HP',
        9: 'ASUS',
        10: 'Redragon',
        11: 'Redragon',
        12: 'Kingston',
        101: 'Lenovo',
        102: 'Lenovo',
        103: 'Lenovo',
        104: 'Lenovo',
        105: 'ESET',
        106: 'HP',
        107: 'HP',
        108: 'Lenovo',
        109: 'HP',
        110: 'Lenovo',
        111: 'PNY',
        112: 'Hiksemi',
        113: 'Hiksemi',
        114: 'Samsung',
        115: 'Samsung',
        116: 'ASUS',
        117: 'Lenovo',
        118: 'HP',
    }

    # Marcas a inferir por palabras clave en el nombre si no coinciden por ID
    palabras_clave = [
        ('Lenovo', 'Lenovo'),
        ('HP', 'HP'),
        ('ASUS', 'ASUS'),
        ('Samsung', 'Samsung'),
        ('Hiksemi', 'Hiksemi'),
        ('PNY', 'PNY'),
        ('Logitech', 'Logitech'),
        ('Kingston', 'Kingston'),
        ('Redragon', 'Redragon'),
        ('HyperX', 'HyperX'),
        ('Seagate', 'Seagate'),
        ('ESET', 'ESET'),
        ('Epson', 'Epson'),
        ('Canon', 'Canon'),
    ]

    for prod in Producto.objects.all():
        nueva_marca = None
        if prod.id in marcas_por_id:
            nueva_marca = marcas_por_id[prod.id]
        elif not prod.marca:
            nombre_upper = (prod.nombre or '').upper()
            for kw, brand in palabras_clave:
                if kw.upper() in nombre_upper:
                    nueva_marca = brand
                    break

        if nueva_marca and prod.marca != nueva_marca:
            prod.marca = nueva_marca
            prod.save()


def revertir_actualizacion_marcas(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inicio', '0008_agregar_categoria_impresoras'),
    ]

    operations = [
        migrations.RunPython(actualizar_marcas_productos, revertir_actualizacion_marcas),
    ]
