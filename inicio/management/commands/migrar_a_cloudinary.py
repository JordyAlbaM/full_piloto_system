from django.core.management.base import BaseCommand
from inicio.cloudinary_service import migrar_todas_las_imagenes_a_cloudinary, is_cloudinary_configured

class Command(BaseCommand):
    help = 'Migra todas las imágenes locales y URLs externas a Cloudinary para asegurar su persistencia en producción.'

    def handle(self, *args, **options):
        if not is_cloudinary_configured():
            self.stderr.write(self.style.ERROR('❌ Error: Cloudinary no está configurado. Asegúrate de tener CLOUDINARY_URL en el entorno o archivo .env.'))
            return

        self.stdout.write(self.style.NOTICE('Iniciando migración de imágenes a Cloudinary con optimización...'))

        def progress(producto, cambio):
            if cambio:
                self.stdout.write(self.style.SUCCESS(f'  ✔ Actualizado #{producto.id}: {producto.nombre[:40]}'))

        res = migrar_todas_las_imagenes_a_cloudinary(progress_callback=progress)

        if not res.get('success'):
            self.stderr.write(self.style.ERROR(f"Error: {res.get('error')}"))
            return

        self.stdout.write(self.style.SUCCESS('\n========================================'))
        self.stdout.write(self.style.SUCCESS('🎉 ¡MIGRACIÓN COMPLETADA CON ÉXITO!'))
        self.stdout.write(self.style.SUCCESS(f"• Productos analizados: {res['total_productos']}"))
        self.stdout.write(self.style.SUCCESS(f"• Productos actualizados: {res['productos_actualizados']}"))
        self.stdout.write(self.style.SUCCESS(f"• Fotos principales migradas: {res['fotos_principales_migradas']}"))
        self.stdout.write(self.style.SUCCESS(f"• Fotos de galería migradas: {res['fotos_galeria_migradas']}"))
        self.stdout.write(self.style.SUCCESS(f"• Total fotos subidas a Cloudinary: {res['total_fotos_migradas']}"))
        if res['errores']:
            self.stdout.write(self.style.WARNING(f"\nAdvertencias ({len(res['errores'])}):"))
            for err in res['errores']:
                self.stdout.write(self.style.WARNING(f"  - {err}"))
        self.stdout.write(self.style.SUCCESS('========================================\n'))
