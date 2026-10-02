import os
import io
import uuid
import logging
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from PIL import Image, ImageOps
import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)

# Configuración de optimización recomendada para e-commerce
MAX_DIMENSION = 1200  # Ancho o alto máximo en píxeles (ideal para pantallas y móviles)
JPEG_QUALITY = 82     # Calidad óptima: excelente nitidez con mínimo peso (100-200 KB)

def optimizar_archivo_imagen(archivo_subido):
    """
    Optimiza una imagen antes de enviarla a Cloudinary o guardarla en disco:
    1. Corrige la rotación automática de fotos tomadas con celulares (EXIF transpose).
    2. Reduce dimensiones gigantes (ej. fotos de 4000px de celulares se ajustan a max 1200px).
    3. Comprime el peso del archivo reduciéndolo en un 80% - 90% sin pérdida visual visible.
    """
    try:
        archivo_subido.seek(0)
        img = Image.open(archivo_subido)
        
        # Corregir orientación de cámaras/móviles
        img = ImageOps.exif_transpose(img)

        # Redimensionar proporcionalmente si supera el tamaño máximo
        if img.width > MAX_DIMENSION or img.height > MAX_DIMENSION:
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        ext = os.path.splitext(getattr(archivo_subido, 'name', 'img.jpg'))[1].lower()

        # Si tiene canal alfa / transparencia (PNG, WebP)
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img.save(output, format='PNG', optimize=True)
            new_ext = '.png'
        else:
            # Convertir a RGB y guardar como JPEG optimizado
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(output, format='JPEG', quality=JPEG_QUALITY, optimize=True)
            new_ext = '.jpg'

        output.seek(0)
        base_name = os.path.splitext(getattr(archivo_subido, 'name', 'img'))[0]
        return ContentFile(output.getvalue(), name=f"{base_name}{new_ext}")
    except Exception as e:
        logger.warning(f"No se pudo pre-optimizar imagen con Pillow: {e}")
        try:
            archivo_subido.seek(0)
        except Exception:
            pass
        return archivo_subido

def is_cloudinary_configured():
    """Verifica si las credenciales de Cloudinary están configuradas en el entorno."""
    config = cloudinary.config()
    return bool(config.cloud_name and config.api_key and config.api_secret)

def procesar_y_subir_imagen(archivo_o_url, subfolder="productos"):
    """
    Sube un archivo o descarga una URL externa y la guarda en Cloudinary con optimización.
    - Si se pasa un archivo subido: lo pre-optimiza con Pillow y lo sube.
    - Si se pasa una URL de texto: Cloudinary la descarga y la optimiza automáticamente.
    """
    if not archivo_o_url:
        return ""

    folder_path = f"full_piloto/{subfolder.strip('/')}"

    # Caso 1: Es una cadena de texto (URL)
    if isinstance(archivo_o_url, str):
        url = archivo_o_url.strip()
        if not url:
            return ""

        # Si ya está alojada en Cloudinary o es un archivo estático
        if "res.cloudinary.com" in url or url.startswith("/static/"):
            return url

        # Si es un archivo local en /media/
        if url.startswith(("/media/", "media/")):
            if is_cloudinary_configured():
                from django.conf import settings
                rel_path = url.replace('/media/', '', 1).lstrip('/')
                real_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                if not os.path.isfile(real_path):
                    real_path = os.path.join(settings.BASE_DIR, url.lstrip('/'))
                if os.path.isfile(real_path):
                    try:
                        with open(real_path, 'rb') as f:
                            archivo_optimizado = optimizar_archivo_imagen(f)
                            res = cloudinary.uploader.upload(
                                archivo_optimizado,
                                folder=folder_path,
                                resource_type="image",
                                transformation=[
                                    {'quality': 'auto', 'fetch_format': 'auto'}
                                ]
                            )
                            return res.get("secure_url", url)
                    except Exception as e:
                        logger.error(f"Error subiendo archivo local a Cloudinary ({real_path}): {e}")
                        return url
            return url

        # Si es una URL web externa (ej. de Infotec, Unsplash o cualquier proveedor)
        if url.startswith(("http://", "https://")):
            if is_cloudinary_configured():
                try:
                    res = cloudinary.uploader.upload(
                        url,
                        folder=folder_path,
                        resource_type="image",
                        transformation=[
                            {'width': MAX_DIMENSION, 'height': MAX_DIMENSION, 'crop': 'limit'},
                            {'quality': 'auto', 'fetch_format': 'auto'}
                        ]
                    )
                    return res.get("secure_url", url)
                except Exception as e:
                    logger.warning(f"Error subiendo URL remota a Cloudinary ({url}): {e}")
                    return url
            return url

        return url

    # Caso 2: Es un archivo subido (request.FILES)
    if hasattr(archivo_o_url, 'read'):
        # 1. Pre-optimizar en memoria con Pillow antes de subir
        archivo_optimizado = optimizar_archivo_imagen(archivo_o_url)

        if is_cloudinary_configured():
            try:
                res = cloudinary.uploader.upload(
                    archivo_optimizado,
                    folder=folder_path,
                    resource_type="image",
                    transformation=[
                        {'quality': 'auto', 'fetch_format': 'auto'}
                    ]
                )
                return res.get("secure_url", "")
            except Exception as e:
                logger.error(f"Error subiendo archivo a Cloudinary: {e}")
                pass

        # Fallback local (disco /media/):
        file_ext = os.path.splitext(getattr(archivo_optimizado, 'name', 'img.jpg'))[1].lower() or '.jpg'
        safe_filename = f"{subfolder}_{uuid.uuid4().hex[:8]}{file_ext}"
        saved_path = default_storage.save(f"{subfolder}/{safe_filename}", archivo_optimizado)
        return default_storage.url(saved_path)

    return ""

def procesar_lineas_galeria(texto_lineas, subfolder="productos/galeria"):
    """
    Toma un texto con URLs separadas por saltos de línea y, si Cloudinary está configurado,
    sube/descarga las URLs remotas externas o locales a Cloudinary para asegurar su persistencia.
    """
    if not texto_lineas:
        return ""
    lineas = [l.strip() for l in texto_lineas.splitlines() if l.strip()]
    nuevas = []
    for l in lineas:
        res = procesar_y_subir_imagen(l, subfolder=subfolder)
        if res:
            nuevas.append(res)
    return "\n".join(nuevas)

def obtener_estado_migracion_imagenes():
    """
    Retorna el estado de las imágenes en la base de datos:
    cuántas están en Cloudinary, cuántas locales, cuántas externas y total.
    """
    from inicio.models import Producto
    total_prods = Producto.objects.count()
    cloudinary_count = 0
    pendientes_locales = 0
    pendientes_externas = 0

    for p in Producto.objects.all():
        url = (p.imagen_url or '').strip()
        if 'res.cloudinary.com' in url:
            cloudinary_count += 1
        elif url.startswith(('/media/', 'media/')):
            pendientes_locales += 1
        elif url.startswith(('http://', 'https://')):
            pendientes_externas += 1

    return {
        'total': total_prods,
        'en_cloudinary': cloudinary_count,
        'pendientes': pendientes_locales + pendientes_externas,
        'pendientes_locales': pendientes_locales,
        'pendientes_externas': pendientes_externas,
    }

def migrar_todas_las_imagenes_a_cloudinary(progress_callback=None):
    """
    Recorre todos los productos en la base de datos y migra a Cloudinary:
    1. Imágenes principales locales (/media/...) o externas (http/https no-Cloudinary).
    2. Imágenes de galería secundarias.
    """
    from inicio.models import Producto

    if not is_cloudinary_configured():
        return {
            'success': False,
            'error': 'Cloudinary no está configurado en las variables de entorno (falta CLOUDINARY_URL).'
        }

    total_productos = Producto.objects.count()
    actualizados = 0
    fotos_principales_migradas = 0
    fotos_galeria_migradas = 0
    errores = []

    for p in Producto.objects.all().order_by('id'):
        cambio_en_producto = False
        img_principal = (p.imagen_url or '').strip()

        # 1. Migrar imagen principal si no está en Cloudinary
        if img_principal and 'res.cloudinary.com' not in img_principal:
            if img_principal.startswith(('http://', 'https://', '/media/', 'media/')):
                try:
                    nueva_url = procesar_y_subir_imagen(img_principal, subfolder="productos")
                    if nueva_url and 'res.cloudinary.com' in nueva_url:
                        p.imagen_url = nueva_url
                        cambio_en_producto = True
                        fotos_principales_migradas += 1
                except Exception as e:
                    errores.append(f"Prod #{p.id} ({p.nombre[:20]}): {e}")

        # 2. Migrar galería si tiene fotos no-Cloudinary
        sec = (p.imagenes_secundarias or '').strip()
        if sec:
            lineas = [l.strip() for l in sec.splitlines() if l.strip()]
            nuevas_lineas = []
            sec_cambio = False
            for l in lineas:
                if 'res.cloudinary.com' not in l and l.startswith(('http://', 'https://', '/media/', 'media/')):
                    try:
                        nueva_sec = procesar_y_subir_imagen(l, subfolder="productos/galeria")
                        if nueva_sec and 'res.cloudinary.com' in nueva_sec:
                            nuevas_lineas.append(nueva_sec)
                            fotos_galeria_migradas += 1
                            sec_cambio = True
                        else:
                            nuevas_lineas.append(l)
                    except Exception as e:
                        nuevas_lineas.append(l)
                        errores.append(f"Galeria Prod #{p.id}: {e}")
                else:
                    nuevas_lineas.append(l)

            if sec_cambio:
                p.imagenes_secundarias = "\n".join(nuevas_lineas)
                cambio_en_producto = True

        if cambio_en_producto:
            p.save()
            actualizados += 1

        if progress_callback:
            progress_callback(p, cambio_en_producto)

    return {
        'success': True,
        'total_productos': total_productos,
        'productos_actualizados': actualizados,
        'fotos_principales_migradas': fotos_principales_migradas,
        'fotos_galeria_migradas': fotos_galeria_migradas,
        'total_fotos_migradas': fotos_principales_migradas + fotos_galeria_migradas,
        'errores': errores
    }
