import os
import uuid
import urllib.request
import urllib.parse
import re
import json
import html
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib import messages
from django.db.models import Q, F
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Categoria, Producto
from .forms import RegistroClienteForm, LoginClienteForm, ProductoForm
from .cloudinary_service import (
    procesar_y_subir_imagen,
    procesar_lineas_galeria,
    obtener_estado_migracion_imagenes,
    migrar_todas_las_imagenes_a_cloudinary,
    iniciar_migracion_segundo_plano,
    esta_migrando,
    obtener_info_migracion_activa
)


def normalizar_url_infotec(url):
    """Estandariza una URL de Infotec para comparaciones precisas (elimina parámetros extras, trailing slash, unifica www/https)."""
    if not url:
        return ''
    u = url.strip().strip('\'"<> \t\n\r')
    if not u.startswith('http://') and not u.startswith('https://'):
        u = 'https://' + u
    try:
        parsed = urllib.parse.urlparse(u)
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        path = parsed.path.rstrip('/')
        return f"https://{netloc}{path}"
    except Exception:
        return u.rstrip('/')


def extraer_id_producto_infotec(url):
    """Extrae el ID numérico del producto en URLs de Infotec (ej: /110519-nombre-laptop.html -> 110519)"""
    if not url:
        return None
    match = re.search(r'/(\d+)-', url)
    if match:
        return match.group(1)
    return None


def buscar_producto_duplicado(url, nombre_extraido=None, modelo_extraido=None):
    """
    Busca si ya existe un producto registrado en la base de datos que coincida
    con este enlace de Infotec, su ID numérico, su nombre o modelo.
    Retorna la instancia de Producto si existe, o None si es nuevo.
    """
    url_norm = normalizar_url_infotec(url)
    if not url_norm:
        return None

    # 1. Búsqueda directa por enlace de origen exacto o normalizado
    prod = Producto.objects.filter(url_origen=url_norm).first()
    if prod:
        return prod

    # 2. Búsqueda por ID numérico de Infotec (ej: 110519)
    infotec_id = extraer_id_producto_infotec(url_norm)
    if infotec_id:
        prod = Producto.objects.filter(url_origen__icontains=f"/{infotec_id}-").first()
        if prod:
            return prod
        prod = Producto.objects.filter(imagen_url__icontains=f"/{infotec_id}-").first()
        if prod:
            return prod
        prod = Producto.objects.filter(imagenes_secundarias__icontains=f"/{infotec_id}-").first()
        if prod:
            return prod

    # 3. Búsqueda por coincidencia de nombre si se proporcionó
    if nombre_extraido:
        nombre_clean = nombre_extraido.strip()
        if len(nombre_clean) > 5:
            prod = Producto.objects.filter(nombre__iexact=nombre_clean).first()
            if prod:
                return prod

    # 4. Búsqueda por modelo específico
    if modelo_extraido:
        mod_clean = modelo_extraido.strip()
        if len(mod_clean) >= 6:
            prod = Producto.objects.filter(modelo_codigo__iexact=mod_clean).first()
            if prod:
                return prod

    return None


def obtener_datos_infotec(url):
    """Extrae automáticamente nombre, precio, descripción e imágenes de una URL de Infotec"""
    try:
        url_limpia = (url or '').strip().strip('\'"<> \t\n\r')
        if not url_limpia:
            return {'success': False, 'error': 'No se proporcionó un enlace válido.'}

        # Si el usuario pegó el enlace sin https:// (ej: infotec.com.pe/...)
        if not url_limpia.startswith('http://') and not url_limpia.startswith('https://'):
            url_limpia = 'https://' + url_limpia

        # Validar que sea del dominio infotec
        if 'infotec.com.pe' not in url_limpia:
            return {'success': False, 'error': 'El enlace ingresado no corresponde a infotec.com.pe.'}

        req = urllib.request.Request(
            url_limpia,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        )
        content = urllib.request.urlopen(req, timeout=14).read().decode('utf-8', errors='ignore')
        
        # 1. Extraer JSON-LD de Producto
        product_info = {}
        matches = re.findall(r'<script type=\"application/ld\+json\">(.*?)</script>', content, re.DOTALL)
        for m in matches:
            try:
                data = json.loads(m.strip())
                if data.get('@type') == 'Product':
                    product_info = data
                    break
            except Exception:
                pass
        
        nombre = html.unescape(product_info.get('name', '')).strip()
        precio = str(product_info.get('offers', {}).get('price', '')).strip()
        desc = html.unescape(product_info.get('description', '')).strip()
        main_img = product_info.get('image', '').strip()
        
        # 2. Extraer todas las imágenes del carrusel/galería
        imgs = re.findall(r'data-image-large-src=\"([^\"]+)\"', content)
        if not imgs:
            imgs = re.findall(r'src=\"(https://infotec\.com\.pe/\d+-large_default/[^\"]+\.jpg)\"', content)
        
        gallery = []
        seen = set()
        for im in imgs:
            im_clean = im.strip()
            if im_clean and im_clean not in seen:
                seen.add(im_clean)
                gallery.append(im_clean)
                
        if not main_img and gallery:
            main_img = gallery[0]
            gallery = gallery[1:]
        elif main_img and main_img in gallery:
            gallery.remove(main_img)

        # 3. Extraer especificaciones y características de la ficha técnica de Infotec
        features = {}
        # A) Infotec suele tener <dl class="data-sheet"><dt class="name">...</dt><dd class="value">...</dd></dl>
        dt_matches = re.findall(r'<dt[^>]*class=[\'"][^\'"]*name[^\'"]*[\'"][^>]*>(.*?)</dt>\s*<dd[^>]*class=[\'"][^\'"]*value[^\'"]*[\'"][^>]*>(.*?)</dd>', content, re.DOTALL | re.IGNORECASE)
        for dt, dd in dt_matches:
            k = re.sub(r'<[^>]+>', '', dt).strip()
            v = re.sub(r'<[^>]+>', '', dd).strip()
            if k and v:
                features[k.lower()] = v

        # B) Extraer de la ficha técnica rápida / lista de componentes de PCs y laptops (<ul class="ficha-tecnica"> o product-description-short)
        short_match = re.search(r'product-description-short[^>]*>(.*?)</div>', content, re.DOTALL | re.IGNORECASE)
        if short_match:
            short_html = short_match.group(1)
            li_matches = re.findall(r'<li[^>]*>(.*?)</li>', short_html, re.DOTALL | re.IGNORECASE)
            for li in li_matches:
                txt = html.unescape(re.sub(r'<[^>]+>', '', li)).strip()
                txt = re.sub(r'\s+', ' ', txt)
                if ':' in txt:
                    parts = txt.split(':', 1)
                    k = parts[0].strip().lower()
                    v = parts[1].strip()
                    if k and v and 'importante' not in k:
                        # Si ya existía pero esta versión es más detallada (ej: procesador con núcleos), se prioriza
                        features[k] = v

        # C) Si no hubo en data-sheet ni lista, buscar en tablas tradicionales
        if not features:
            tr_matches = re.findall(r'<tr[^>]*>\s*<t[dh][^>]*>(.*?)</t[dh]>\s*<td[^>]*>(.*?)</td>\s*</tr>', content, re.DOTALL | re.IGNORECASE)
            for td1, td2 in tr_matches:
                k = re.sub(r'<[^>]+>', '', td1).strip()
                v = re.sub(r'<[^>]+>', '', td2).strip()
                if k and v and len(k) < 50:
                    features[k.lower()] = v

        marca = features.get('marca', '')
        if not marca:
            # En setups armados o PCs, la marca puede ser la línea o ensamblado gamer
            if 'linea' in features:
                marca = features['linea']
            elif 'setup' in nombre.lower() or 'pc' in nombre.lower():
                marca = 'Custom PC / Ensamblado'

        modelo = features.get('modelo', '') or features.get('skup', '') or features.get('linea', '')
        procesador = features.get('procesador', '')
        ram = features.get('memoria ram', '') or features.get('ram', '')
        disco = features.get('almacenamiento', '') or features.get('disco duro', '') or features.get('ssd', '')
        pantalla = features.get('pantalla', '')
        if not pantalla and ('pc' in nombre.lower() or 'setup' in nombre.lower()):
            # Detectar si incluye monitor en el nombre (ej: '+ 27 FHD 144HZ' o 'Monitor 24...')
            mon_combo_match = re.search(r'(?:monitor\s*[:\+]?|(?:\+\s*))(\d+(?:\.\d+)?[\'\"\s]*(?:fhd|qhd|ips|hz|[0-9]{2,3}hz)[^\+]*)', nombre, re.IGNORECASE)
            if mon_combo_match:
                pantalla = f"Incluye Monitor {mon_combo_match.group(1).strip()}"
            elif 'monitor' in nombre.lower():
                pantalla = "Incluye Monitor (Revisar modelo en título)"
            else:
                pantalla = "No incluye monitor (Solo Torre / Case)"

        grafica = features.get('tarjeta de video', '') or features.get('gráficos', '') or features.get('grafica', '')
        garantia = features.get('garantia', '') or features.get('garantía', '') or '12 Meses Oficial en tienda Caraz'
        
        # Generar texto de especificaciones adicionales estructuradas
        extras_lines = []
        # Campos que ya van en sus inputs dedicados
        campos_principales = {
            'marca', 'modelo', 'skup', 'linea', 'procesador', 'memoria ram', 'ram',
            'almacenamiento', 'disco duro', 'ssd', 'pantalla', 'tarjeta de video',
            'gráficos', 'grafica', 'garantia', 'garantía'
        }

        # Dar formato visual ordenado si existen componentes de hardware específicos
        orden_componentes_pc = [
            ('mainboard', 'Placa Madre (Mainboard)'),
            ('placa madre', 'Placa Madre'),
            ('cooler', 'Refrigeración / Cooler'),
            ('enfriamiento liquido', 'Refrigeración Líquida'),
            ('case', 'Case / Gabinete'),
            ('fuente de poder', 'Fuente de Poder'),
            ('fuente', 'Fuente de Poder'),
            ('producto', 'Tipo de Producto'),
        ]

        componentes_agregados = set()
        etiquetas_agregadas = set()
        for key_cand, label_custom in orden_componentes_pc:
            if key_cand in features and label_custom not in etiquetas_agregadas:
                extras_lines.append(f"{label_custom}: {features[key_cand]}")
                etiquetas_agregadas.add(label_custom)
                componentes_agregados.add(key_cand)

        # Cualquier otra especificación técnica no contemplada arriba (conectividad, peso, batería, etc.)
        for k_raw, v_raw in features.items():
            if k_raw not in campos_principales and k_raw not in componentes_agregados:
                k_title = k_raw.capitalize()
                extras_lines.append(f"{k_title}: {v_raw}")

        return {
            'success': True,
            'nombre': nombre,
            'precio': precio,
            'descripcion': desc,
            'imagen_url': main_img,
            'imagenes_secundarias': "\n".join(gallery),
            'total_fotos': (1 if main_img else 0) + len(gallery),
            'marca': marca,
            'modelo_codigo': modelo,
            'procesador': procesador,
            'ram': ram,
            'almacenamiento': disco,
            'pantalla': pantalla,
            'grafica': grafica,
            'garantia': garantia,
            'especificaciones_adicionales': "\n".join(extras_lines)
        }
    except Exception as e:
        return {'success': False, 'error': f'No se pudo extraer la información del enlace: {str(e)}'}

def inicio(request):
    query = request.GET.get('q', '').strip()
    if not query:
        query = request.GET.get('nombre', '').strip()
    categoria_slug = request.GET.get('categoria', '').strip()
    precio_min_str = request.GET.get('precio_min', '').strip()
    precio_max_str = request.GET.get('precio_max', '').strip()
    marca = request.GET.get('marca', '').strip()
    orden = request.GET.get('orden', 'recientes').strip()
    en_stock = request.GET.get('en_stock', '').strip()
    solo_ofertas = request.GET.get('solo_ofertas', '').strip()

    productos = Producto.objects.filter(disponible=True).select_related('categoria')
    categoria_actual = None

    # 1. Filtro por categoría
    if categoria_slug and categoria_slug != 'todas':
        categoria_actual = Categoria.objects.filter(slug=categoria_slug).first()
        if categoria_slug == 'zona-gamer' or 'gamer' in categoria_slug:
            productos = productos.filter(
                Q(categoria__slug=categoria_slug) |
                Q(nombre__icontains='gamer') |
                Q(nombre__icontains='gaming') |
                Q(nombre__icontains='juego') |
                Q(nombre__icontains='juegos')
            )
        else:
            productos = productos.filter(categoria__slug=categoria_slug)

    # 2. Filtro por búsqueda de texto (nombre, descripción, marca, modelo)
    if query:
        q_lower = query.lower()
        if q_lower in ['zona gamer', 'zona-gamer', 'zona_gamer']:
            productos = productos.filter(
                Q(categoria__slug='zona-gamer') |
                Q(nombre__icontains='gamer') |
                Q(nombre__icontains='gaming') |
                Q(nombre__icontains='juego') |
                Q(nombre__icontains='juegos')
            )
        else:
            productos = productos.filter(
                Q(nombre__icontains=query) |
                Q(descripcion__icontains=query) |
                Q(marca__icontains=query) |
                Q(modelo_codigo__icontains=query)
            )

    procesador = request.GET.get('procesador', '').strip()
    ram = request.GET.get('ram', '').strip()
    almacenamiento = request.GET.get('almacenamiento', '').strip()

    # 3. Filtro por marca
    if marca and marca != 'todas':
        productos = productos.filter(
            Q(marca__iexact=marca) |
            Q(marca__icontains=marca) |
            Q(nombre__icontains=marca)
        )

    # 4. Filtro por procesador
    if procesador and procesador != 'todos':
        productos = productos.filter(
            Q(procesador__icontains=procesador) |
            Q(nombre__icontains=procesador) |
            Q(descripcion__icontains=procesador)
        )

    # 5. Filtro por memoria RAM
    if ram and ram != 'todas':
        ram_clean = ram.replace(' ', '')
        ram_spaced = ram_clean.replace('GB', ' GB')
        productos = productos.filter(
            Q(ram__icontains=ram_clean) |
            Q(ram__icontains=ram_spaced) |
            Q(nombre__icontains=ram_clean) |
            Q(nombre__icontains=ram_spaced) |
            Q(descripcion__icontains=ram_clean) |
            Q(descripcion__icontains=ram_spaced)
        )

    # 6. Filtro por almacenamiento
    if almacenamiento and almacenamiento != 'todos':
        almacenamiento_clean = almacenamiento.replace(' ', '')
        almacenamiento_spaced = almacenamiento_clean.replace('GB', ' GB').replace('TB', ' TB')
        productos = productos.filter(
            Q(almacenamiento__icontains=almacenamiento_clean) |
            Q(almacenamiento__icontains=almacenamiento_spaced) |
            Q(nombre__icontains=almacenamiento_clean) |
            Q(nombre__icontains=almacenamiento_spaced) |
            Q(descripcion__icontains=almacenamiento_clean) |
            Q(descripcion__icontains=almacenamiento_spaced)
        )

    # 7. Filtro por rango de precio
    precio_min_val = None
    if precio_min_str:
        try:
            precio_min_val = Decimal(precio_min_str)
            if precio_min_val >= 0:
                productos = productos.filter(precio__gte=precio_min_val)
        except (InvalidOperation, ValueError):
            precio_min_str = ''

    precio_max_val = None
    if precio_max_str:
        try:
            precio_max_val = Decimal(precio_max_str)
            if precio_max_val > 0:
                productos = productos.filter(precio__lte=precio_max_val)
        except (InvalidOperation, ValueError):
            precio_max_str = ''

    # 8. Filtro solo productos en stock
    if en_stock in ['1', 'true', 'on', 'si']:
        productos = productos.filter(stock__gt=0)

    # 9. Filtro solo ofertas / descuento
    if solo_ofertas in ['1', 'true', 'on', 'si']:
        productos = productos.filter(precio_tachado__gt=F('precio'))

    # 10. Ordenamiento dinámico
    if orden == 'precio_asc':
        productos = productos.order_by('precio', '-id')
    elif orden == 'precio_desc':
        productos = productos.order_by('-precio', '-id')
    elif orden == 'nombre_asc':
        productos = productos.order_by('nombre')
    elif orden == 'nombre_desc':
        productos = productos.order_by('-nombre')
    elif orden == 'descuento':
        productos = productos.order_by(F('precio_tachado') - F('precio')).reverse()
    else:
        orden = 'recientes'
        productos = productos.order_by('-id')

    categorias = Categoria.objects.all()

    # Extraer marcas disponibles dinámicamente para chips de filtro
    marcas_db = set(Producto.objects.filter(disponible=True).exclude(marca='').values_list('marca', flat=True))
    marcas_populares = ['Lenovo', 'HP', 'ASUS', 'Samsung', 'Hiksemi', 'PNY', 'Logitech', 'Kingston', 'Redragon', 'HyperX', 'Seagate', 'ESET', 'Epson', 'Canon']
    nombres_prods = list(Producto.objects.filter(disponible=True).values_list('nombre', flat=True))
    marcas_disponibles = set()
    for m in marcas_db:
        if m.strip():
            marcas_disponibles.add(m.strip())
    for mp in marcas_populares:
        mp_lower = mp.lower()
        if any(mp_lower in n.lower() for n in nombres_prods):
            marcas_disponibles.add(mp)
    marcas_disponibles = sorted(list(marcas_disponibles))

    producto_destacado = productos.first() or Producto.objects.filter(disponible=True).select_related('categoria').first()

    # Paginación (8 productos por página)
    paginator = Paginator(productos, 8)
    page_number = request.GET.get('page', 1)
    try:
        productos_paginados = paginator.page(page_number)
    except PageNotAnInteger:
        productos_paginados = paginator.page(1)
    except EmptyPage:
        productos_paginados = paginator.page(paginator.num_pages)

    # Query string para preservar filtros activos en la paginación
    params = request.GET.copy()
    if 'page' in params:
        del params['page']
    if 'ajax' in params:
        del params['ajax']
    filtros_querystring = params.urlencode()

    # Contador de filtros activos
    filtros_activos_count = 0
    if query: filtros_activos_count += 1
    if categoria_slug and categoria_slug != 'todas': filtros_activos_count += 1
    if precio_min_str: filtros_activos_count += 1
    if precio_max_str: filtros_activos_count += 1
    if marca and marca != 'todas': filtros_activos_count += 1
    if procesador and procesador != 'todos': filtros_activos_count += 1
    if ram and ram != 'todas': filtros_activos_count += 1
    if almacenamiento and almacenamiento != 'todos': filtros_activos_count += 1
    if orden and orden != 'recientes': filtros_activos_count += 1
    if en_stock in ['1', 'true', 'on', 'si']: filtros_activos_count += 1
    if solo_ofertas in ['1', 'true', 'on', 'si']: filtros_activos_count += 1

    context = {
        'productos': productos_paginados,
        'total_productos': paginator.count,
        'categorias': categorias,
        'query': query,
        'categoria_seleccionada': categoria_slug,
        'categoria_actual': categoria_actual,
        'precio_min': precio_min_str,
        'precio_max': precio_max_str,
        'marca_seleccionada': marca,
        'procesador_seleccionado': procesador,
        'ram_seleccionada': ram,
        'almacenamiento_seleccionado': almacenamiento,
        'orden_seleccionado': orden,
        'en_stock': en_stock,
        'solo_ofertas': solo_ofertas,
        'marcas_disponibles': marcas_disponibles,
        'procesadores_disponibles': [
            ('Core i3', 'Core i3'),
            ('Core i5', 'Core i5'),
            ('Core i7', 'Core i7 / Ultra'),
            ('Ryzen 3', 'Ryzen 3'),
            ('Ryzen 5', 'Ryzen 5'),
            ('Ryzen 7', 'Ryzen 7'),
        ],
        'rams_disponibles': ['4GB', '8GB', '16GB', '32GB'],
        'almacenamientos_disponibles': ['256GB', '512GB', '1TB', '2TB'],
        'filtros_querystring': filtros_querystring,
        'filtros_activos_count': filtros_activos_count,
        'producto_destacado': producto_destacado,
    }

    # Si es petición AJAX / Fetch, devolver JSON con el fragmento HTML del catálogo
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1':
        html_catalogo = render_to_string('catalogo_productos_partial.html', context, request=request)
        return JsonResponse({
            'status': 'success',
            'html': html_catalogo,
            'total_productos': paginator.count,
            'page': productos_paginados.number,
            'num_pages': paginator.num_pages,
            'has_previous': productos_paginados.has_previous(),
            'has_next': productos_paginados.has_next(),
            'filtros_activos_count': filtros_activos_count,
        })

    return render(request, 'index.html', context)

def detalle_producto(request, producto_id):
    producto = get_object_or_404(Producto.objects.select_related('categoria'), id=producto_id, disponible=True)
    productos_relacionados = Producto.objects.filter(
        disponible=True
    ).exclude(id=producto.id).select_related('categoria')

    # Si es un producto gamer, priorizar otros productos gamer relacionados
    es_gamer = (
        'gamer' in producto.nombre.lower() or
        'gaming' in producto.nombre.lower() or
        'juego' in producto.nombre.lower() or
        (producto.categoria and 'gamer' in producto.categoria.slug)
    )
    if es_gamer:
        gamer_rel = productos_relacionados.filter(
            Q(categoria__slug='zona-gamer') |
            Q(nombre__icontains='gamer') |
            Q(nombre__icontains='gaming') |
            Q(nombre__icontains='juego') |
            Q(nombre__icontains='juegos')
        )
        if gamer_rel.exists():
            productos_relacionados = gamer_rel
        elif producto.categoria:
            productos_relacionados = productos_relacionados.filter(categoria=producto.categoria)
    elif producto.categoria:
        productos_relacionados = productos_relacionados.filter(categoria=producto.categoria)

    productos_relacionados = productos_relacionados[:4]
    
    # Galería dinámica para el producto
    galeria_fotos = producto.get_galeria_imagenes()
    
    # Lista estructurada de especificaciones técnicas
    specs_list = producto.get_lista_especificaciones()

    return render(request, 'detalle.html', {
        'producto': producto,
        'productos_relacionados': productos_relacionados,
        'galeria_fotos': galeria_fotos,
        'specs_list': specs_list,
    })

def carrito(request):
    return render(request, 'carrito.html')

def login_view(request):
    # Si el usuario es administrador/superuser, por defecto su pestaña es 'add_product'
    es_admin = request.user.is_authenticated and (request.user.is_superuser or request.user.rol == 'admin')
    default_tab = 'add_product' if es_admin else 'login'
    active_tab = request.GET.get('tab', default_tab)
    edit_id = request.GET.get('edit')
    return_url = request.GET.get('return_url', '')
    producto_a_editar = None
    if edit_id and es_admin:
        producto_a_editar = Producto.objects.filter(id=edit_id).first()
        if producto_a_editar:
            active_tab = 'edit_product'

    login_form = LoginClienteForm()
    register_form = RegistroClienteForm()
    
    producto_form = None
    if request.user.is_authenticated and (request.user.is_superuser or request.user.rol == 'admin'):
        if producto_a_editar:
            producto_form = ProductoForm(instance=producto_a_editar)
        else:
            producto_form = ProductoForm()

    productos_admin = Producto.objects.all().order_by('-id') if request.user.is_authenticated and (request.user.is_superuser or request.user.rol == 'admin') else []

    # Si un usuario común ya está autenticado, va a inicio. Pero si es superusuario o admin, se le permite ver y gestionar
    if request.user.is_authenticated and not (request.user.is_superuser or request.user.rol == 'admin'):
        return redirect('inicio')

    if request.method == 'POST':
        action = request.POST.get('action')
        post_return_url = request.POST.get('return_url', '').strip()
        
        # Acción 1: Registro de cliente
        if action == 'register':
            active_tab = 'register'
            register_form = RegistroClienteForm(request.POST)
            if register_form.is_valid():
                user = register_form.save()
                auth_login(request, user)
                messages.success(request, f'¡Bienvenido a Full Piloto System, {user.first_name or user.email}!')
                next_url = request.GET.get('next') or request.POST.get('next') or 'inicio'
                return redirect(next_url)
            else:
                messages.error(request, 'Por favor corrige los errores señalados en el registro.')
        
        # Acción 2: Agregar producto (Solo Superusuario / Admin)
        elif action == 'add_product':
            active_tab = 'add_product'
            if not request.user.is_authenticated or not (request.user.is_superuser or request.user.rol == 'admin'):
                messages.error(request, '⛔ Solo el Administrador / Superusuario tiene permisos para agregar productos.')
                return redirect('login')
            
            # Verificación de seguridad para evitar duplicados por enlace
            url_origen_post = request.POST.get('url_origen', '').strip()
            if url_origen_post:
                url_norm = normalizar_url_infotec(url_origen_post)
                prod_dup = buscar_producto_duplicado(url_norm)
                if prod_dup:
                    messages.error(request, f'⛔ No se guardó el producto: el enlace ya fue importado para "{prod_dup.nombre}" (ID: #{prod_dup.id}). Evita registrar productos duplicados.')
                    return redirect('/login/?tab=add_product')

            producto_form = ProductoForm(request.POST, request.FILES)
            if producto_form.is_valid():
                nuevo_prod = producto_form.save(commit=False)
                if url_origen_post:
                    nuevo_prod.url_origen = normalizar_url_infotec(url_origen_post)

                # Si el usuario subió una imagen principal desde su equipo o ingresó URL
                if 'imagen_archivo' in request.FILES:
                    nuevo_prod.imagen_url = procesar_y_subir_imagen(request.FILES['imagen_archivo'], subfolder="productos")
                elif nuevo_prod.imagen_url:
                    nuevo_prod.imagen_url = procesar_y_subir_imagen(nuevo_prod.imagen_url, subfolder="productos")

                # Procesar fotos de galería (archivos y/o URLs de texto)
                urls_nuevas = []
                if 'imagenes_secundarias_archivos' in request.FILES:
                    sec_files = request.FILES.getlist('imagenes_secundarias_archivos')
                    for f in sec_files:
                        url_sec = procesar_y_subir_imagen(f, subfolder="productos/galeria")
                        if url_sec:
                            urls_nuevas.append(url_sec)

                if nuevo_prod.imagenes_secundarias:
                    nuevo_prod.imagenes_secundarias = procesar_lineas_galeria(nuevo_prod.imagenes_secundarias, subfolder="productos/galeria")

                if urls_nuevas:
                    existentes = (nuevo_prod.imagenes_secundarias or '').strip()
                    if existentes:
                        nuevo_prod.imagenes_secundarias = existentes + "\n" + "\n".join(urls_nuevas)
                    else:
                        nuevo_prod.imagenes_secundarias = "\n".join(urls_nuevas)

                nuevo_prod.save()
                messages.success(request, f'✨ ¡Producto "{nuevo_prod.nombre}" registrado exitosamente en la tienda!')
                return redirect('/login/?tab=recent_products')
            else:
                messages.error(request, 'Por favor verifica los datos del producto. Revisa los campos en rojo.')

        # Acción 2.1: Editar producto existente (Solo Superusuario / Admin)
        elif action == 'edit_product':
            active_tab = 'edit_product'
            if not request.user.is_authenticated or not (request.user.is_superuser or request.user.rol == 'admin'):
                messages.error(request, '⛔ Solo el Administrador / Superusuario tiene permisos para editar productos.')
                return redirect('login')

            p_id = request.POST.get('producto_id')
            prod_instance = get_object_or_404(Producto, id=p_id)
            producto_form = ProductoForm(request.POST, request.FILES, instance=prod_instance)
            if producto_form.is_valid():
                prod_guardado = producto_form.save(commit=False)
                url_origen_post = request.POST.get('url_origen', '').strip()
                if url_origen_post:
                    prod_guardado.url_origen = normalizar_url_infotec(url_origen_post)

                # Si sube nueva foto principal o editó la URL
                if 'imagen_archivo' in request.FILES:
                    prod_guardado.imagen_url = procesar_y_subir_imagen(request.FILES['imagen_archivo'], subfolder="productos")
                elif prod_guardado.imagen_url:
                    prod_guardado.imagen_url = procesar_y_subir_imagen(prod_guardado.imagen_url, subfolder="productos")

                # Si sube nuevas fotos de galería o editó URLs existentes
                urls_nuevas = []
                if 'imagenes_secundarias_archivos' in request.FILES:
                    sec_files = request.FILES.getlist('imagenes_secundarias_archivos')
                    for f in sec_files:
                        url_sec = procesar_y_subir_imagen(f, subfolder="productos/galeria")
                        if url_sec:
                            urls_nuevas.append(url_sec)

                if prod_guardado.imagenes_secundarias:
                    prod_guardado.imagenes_secundarias = procesar_lineas_galeria(prod_guardado.imagenes_secundarias, subfolder="productos/galeria")

                if urls_nuevas:
                    existentes = (prod_guardado.imagenes_secundarias or '').strip()
                    if existentes:
                        prod_guardado.imagenes_secundarias = existentes + "\n" + "\n".join(urls_nuevas)
                    else:
                        prod_guardado.imagenes_secundarias = "\n".join(urls_nuevas)

                prod_guardado.save()
                messages.success(request, f'✅ ¡Producto "{prod_guardado.nombre}" actualizado con éxito!')
                if post_return_url:
                    return redirect(post_return_url)
                return redirect(f'/producto/{prod_guardado.id}/')
            else:
                producto_a_editar = prod_instance
                err_list = [f"{field}: {', '.join(errs)}" for field, errs in producto_form.errors.items()]
                messages.error(request, f"Error al actualizar el producto: {' | '.join(err_list)}")

        # Acción 2.2: Eliminar producto (Solo Superusuario / Admin)
        elif action == 'delete_product':
            if not request.user.is_authenticated or not (request.user.is_superuser or request.user.rol == 'admin'):
                messages.error(request, '⛔ No tienes permisos para eliminar productos.')
                return redirect('login')
            p_id = request.POST.get('producto_id')
            prod_instance = get_object_or_404(Producto, id=p_id)
            nombre_del = prod_instance.nombre
            prod_instance.delete()
            messages.info(request, f'🗑️ El producto "{nombre_del}" ha sido eliminado del catálogo.')
            return redirect('/login/?tab=recent_products')

        # Acción 2.3: Migrar todas las imágenes a Cloudinary (Solo Superusuario / Admin)
        elif action == 'migrate_cloudinary':
            if not request.user.is_authenticated or not (request.user.is_superuser or request.user.rol == 'admin'):
                messages.error(request, '⛔ Solo el Administrador tiene permisos para realizar esta migración.')
                return redirect('login')
            ok, msg = iniciar_migracion_segundo_plano()
            if ok:
                messages.success(request, '🚀 ¡Migración iniciada en segundo plano! Las fotos se están procesando y subiendo a Cloudinary sin bloquear el servidor. Recarga la página en unos momentos para ver los avances.')
            else:
                messages.warning(request, f'⏳ {msg}')
            return redirect('/login/?tab=recent_products')

        # Acción 3: Login estándar
        else:
            active_tab = 'login'
            login_form = LoginClienteForm(request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                remember = request.POST.get('remember')
                if not remember:
                    request.session.set_expiry(0) # Expira al cerrar navegador
                else:
                    request.session.set_expiry(1209600) # 2 semanas
                auth_login(request, user)
                messages.success(request, f'¡Hola de nuevo, {user.first_name or user.email}!')
                
                # Si es superusuario o admin, lo dejamos en la pestaña de agregar productos
                if user.is_superuser or user.rol == 'admin':
                    return redirect('/login/?tab=add_product')
                
                next_url = request.GET.get('next') or request.POST.get('next') or 'inicio'
                return redirect(next_url)
            else:
                messages.error(request, 'Correo electrónico o contraseña incorrectos.')

    # Estado de imágenes para el panel de administración
    estado_cloudinary = None
    migracion_en_progreso = False
    if request.user.is_authenticated and (request.user.is_superuser or getattr(request.user, 'rol', '') == 'admin'):
        estado_cloudinary = obtener_estado_migracion_imagenes()
        migracion_en_progreso = esta_migrando()

    return render(request, 'login.html', {
        'login_form': login_form,
        'register_form': register_form,
        'producto_form': producto_form,
        'productos_recientes': productos_admin,
        'producto_a_editar': producto_a_editar,
        'estado_cloudinary': estado_cloudinary,
        'migracion_en_progreso': migracion_en_progreso,
        'active_tab': active_tab,
        'next': request.GET.get('next', ''),
        'return_url': return_url
    })

def logout_view(request):
    if request.user.is_authenticated:
        auth_logout(request)
        messages.info(request, 'Has cerrado sesión con éxito.')
    return redirect('inicio')

def api_importar_infotec(request):
    """Endpoint AJAX para validar enlace, detectar duplicados y autocompletar el formulario"""
    if not request.user.is_authenticated or not (request.user.is_superuser or request.user.rol == 'admin'):
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)
    
    url = request.GET.get('url', '').strip()
    check_only = request.GET.get('check_only', '0') == '1'

    if not url:
        return JsonResponse({'success': False, 'error': 'Debes ingresar una URL válida de Infotec.'}, status=400)
    
    url_norm = normalizar_url_infotec(url)
    if 'infotec.com.pe' not in url_norm:
        return JsonResponse({'success': False, 'error': 'El enlace ingresado no corresponde a infotec.com.pe.'}, status=400)

    # 1. Verificación previa por URL o ID Infotec antes de scrapear
    prod_existente = buscar_producto_duplicado(url_norm)
    if prod_existente:
        return JsonResponse({
            'success': False,
            'duplicado': True,
            'error': f'¡Este enlace ya fue importado anteriormente! Corresponde al producto: "{prod_existente.nombre}" (ID: #{prod_existente.id}).',
            'mensaje': f'Ya existe un producto registrado en la tienda con este mismo enlace.',
            'producto_existente': {
                'id': prod_existente.id,
                'nombre': prod_existente.nombre,
                'precio': str(prod_existente.precio),
                'modelo_codigo': prod_existente.modelo_codigo or '',
                'imagen_url': prod_existente.imagen_url or '',
                'url_ver': f'/producto/{prod_existente.id}/',
                'url_editar': f'/login/?tab=edit_product&producto_id={prod_existente.id}'
            }
        })

    if check_only:
        return JsonResponse({'success': True, 'duplicado': False, 'mensaje': 'Enlace disponible para importar.'})

    # 2. Extraer datos desde Infotec
    data = obtener_datos_infotec(url_norm)
    if not data.get('success'):
        return JsonResponse(data)

    # 3. Verificación posterior con nombre/modelo oficial extraído de Infotec
    nombre_extraido = data.get('nombre', '').strip()
    modelo_extraido = data.get('modelo_codigo', '').strip()
    prod_por_nombre = buscar_producto_duplicado(url_norm, nombre_extraido=nombre_extraido, modelo_extraido=modelo_extraido)
    if prod_por_nombre:
        # Enlazar la url_origen para futuras búsquedas directas e instantáneas
        if not prod_por_nombre.url_origen:
            prod_por_nombre.url_origen = url_norm
            prod_por_nombre.save(update_fields=['url_origen'])

        return JsonResponse({
            'success': False,
            'duplicado': True,
            'error': f'¡Este producto ya existe en tu catálogo! Corresponde a: "{prod_por_nombre.nombre}" (ID: #{prod_por_nombre.id}).',
            'mensaje': f'El producto extraído de este enlace ya se encuentra en tu base de datos.',
            'producto_existente': {
                'id': prod_por_nombre.id,
                'nombre': prod_por_nombre.nombre,
                'precio': str(prod_por_nombre.precio),
                'modelo_codigo': prod_por_nombre.modelo_codigo or '',
                'imagen_url': prod_por_nombre.imagen_url or '',
                'url_ver': f'/producto/{prod_por_nombre.id}/',
                'url_editar': f'/login/?tab=edit_product&producto_id={prod_por_nombre.id}'
            }
        })

    # Si todo es nuevo y válido
    data['url_origen'] = url_norm
    data['duplicado'] = False
    return JsonResponse(data)

def api_buscar_productos(request):
    """Endpoint AJAX con fetch para autocompletar buscador en tiempo real (muestra hasta 3 productos)."""
    q = request.GET.get('q', '').strip()
    if not q or len(q) < 2:
        return JsonResponse({'productos': [], 'total_coincidencias': 0, 'query': q})

    # Buscar por nombre o descripción en productos disponibles
    q_lower = q.lower()
    if q_lower in ['zona gamer', 'zona-gamer', 'zona_gamer', 'gamer', 'gaming', 'juegos', 'juego']:
        filtro_q = (
            Q(categoria__slug='zona-gamer') |
            Q(nombre__icontains='gamer') |
            Q(nombre__icontains='gaming') |
            Q(nombre__icontains='juego') |
            Q(nombre__icontains='juegos')
        )
    else:
        filtro_q = Q(nombre__icontains=q) | Q(descripcion__icontains=q) | Q(categoria__nombre__icontains=q)

    qs = Producto.objects.filter(
        disponible=True
    ).filter(
        filtro_q
    ).select_related('categoria').order_by('-creado')

    total_coincidencias = qs.count()
    primeros_3 = qs[:3]

    resultados = []
    for prod in primeros_3:
        # Obtener imagen principal
        img = prod.imagen_url.strip() if prod.imagen_url else ''
        if not img:
            galeria = prod.get_galeria_imagenes()
            img = galeria[0] if galeria else '/static/inicio/images/placeholder.png'

        resultados.append({
            'id': prod.id,
            'nombre': prod.nombre,
            'precio': f"{float(prod.precio):.2f}",
            'precio_anterior': f"{float(prod.precio_anterior):.2f}" if prod.precio_anterior else None,
            'porcentaje_descuento': prod.porcentaje_descuento,
            'categoria': prod.categoria.nombre if prod.categoria else 'General',
            'imagen': img,
            'url': f"/producto/{prod.id}/"
        })

    return JsonResponse({
        'productos': resultados,
        'total_coincidencias': total_coincidencias,
        'query': q
    })

def api_producto_detalle(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id, disponible=True)

    # Galería de imágenes por producto oficial Lenovo
    galerias = {
        101: [
            '/static/inicio/images/lenovo_v15/lenovo_v15_1.png',
            '/static/inicio/images/lenovo_v15/lenovo_v15_2.png',
            '/static/inicio/images/lenovo_v15/lenovo_v15_3.png',
            '/static/inicio/images/lenovo_v15/lenovo_v15_4.png',
            '/static/inicio/images/lenovo_v15/lenovo_v15_5.png',
        ],
        102: [
            '/static/inicio/images/lenovo_v15_r5/lenovo_v15_r5_1.png',
            '/static/inicio/images/lenovo_v15_r5/lenovo_v15_r5_2.png',
            '/static/inicio/images/lenovo_v15_r5/lenovo_v15_r5_3.png',
        ],
        103: [
            '/static/inicio/images/lenovo_v15_g5_i3/lenovo_v15_g5_i3_1.png',
            '/static/inicio/images/lenovo_v15_g5_i3/lenovo_v15_g5_i3_2.png',
            '/static/inicio/images/lenovo_v15_g5_i3/lenovo_v15_g5_i3_3.png',
        ],
        104: [
            '/static/inicio/images/lenovo_slim3_i5/lenovo_slim3_i5_1.png',
            '/static/inicio/images/lenovo_slim3_i5/lenovo_slim3_i5_2.png',
            '/static/inicio/images/lenovo_slim3_i5/lenovo_slim3_i5_3.png',
        ],
        106: [
            '/static/inicio/images/nuevas_laptops/106_hp_r7.jpg',
            'https://infotec.com.pe/111316-large_default/laptop-hp-15-fc0225dx-ryzen-7-7730u-16gb-512gb-ssd-156-fhd-touchscreen-windows-11-d96e6ua-aba.jpg',
            'https://infotec.com.pe/111315-large_default/laptop-hp-15-fc0225dx-ryzen-7-7730u-16gb-512gb-ssd-156-fhd-touchscreen-windows-11-d96e6ua-aba.jpg',
            'https://infotec.com.pe/111317-large_default/laptop-hp-15-fc0225dx-ryzen-7-7730u-16gb-512gb-ssd-156-fhd-touchscreen-windows-11-d96e6ua-aba.jpg',
        ],
        107: [
            '/static/inicio/images/nuevas_laptops/107_hp_core7.jpg',
            'https://infotec.com.pe/109610-large_default/laptop-hp-15-fd0127dx-intel-core-7-150u-16gb-ddr5-512gb-ssd-156-fhd-touchscreen-windows-11-b4hn8ua.jpg',
            'https://infotec.com.pe/109612-large_default/laptop-hp-15-fd0127dx-intel-core-7-150u-16gb-ddr5-512gb-ssd-156-fhd-touchscreen-windows-11-b4hn8ua.jpg',
        ],
        108: [
            '/static/inicio/images/nuevas_laptops/108_lenovo_yoga_r7.jpg',
            'https://infotec.com.pe/110697-large_default/laptop-lenovo-5-16ahp9-2en1-ryzen-7-8845hs-16gb-1tb-ssd-16-wuxga-touchscreen-windows-11-83ds0056us.jpg',
            'https://infotec.com.pe/110700-large_default/laptop-lenovo-5-16ahp9-2en1-ryzen-7-8845hs-16gb-1tb-ssd-16-wuxga-touchscreen-windows-11-83ds0056us.jpg',
            'https://infotec.com.pe/110698-large_default/laptop-lenovo-5-16ahp9-2en1-ryzen-7-8845hs-16gb-1tb-ssd-16-wuxga-touchscreen-windows-11-83ds0056us.jpg',
        ],
        109: [
            '/static/inicio/images/nuevas_laptops/109_hp_omnibook.jpg',
            'https://infotec.com.pe/109861-large_default/laptop-hp-omnibook-3-16-by0205-ryzen-5-40-16gb-256gb-ssd-16-wuxga-touchscreen-windows-11-d10e8ua-aba.jpg',
            'https://infotec.com.pe/109864-large_default/laptop-hp-omnibook-3-16-by0205-ryzen-5-40-16gb-256gb-ssd-16-wuxga-touchscreen-windows-11-d10e8ua-aba.jpg',
        ],
        110: [
            '/static/inicio/images/nuevas_laptops/110_lenovo_loq.jpg',
            'https://infotec.com.pe/111162-large_default/laptop-gamer-lenovo-loq-15arp10e-ryzen-7-7735hs-16gb-512gb-ssd-t-video-rtx-3050-6gb-156-fhd-freedos-83s0004hlm-.jpg',
            'https://infotec.com.pe/111163-large_default/laptop-gamer-lenovo-loq-15arp10e-ryzen-7-7735hs-16gb-512gb-ssd-t-video-rtx-3050-6gb-156-fhd-freedos-83s0004hlm-.jpg',
        ],
    }

    specs_map = {
        101: [
            ("Procesador", "AMD Ryzen 3 7320U (4 núcleos / 8 hilos, hasta 4.10GHz)"),
            ("Memoria RAM", "8GB LPDDR5 5500MHz ultrarrápida"),
            ("Almacenamiento", "512GB SSD M.2 PCIe 4.0 NVMe"),
            ("Pantalla", '15.6" Full HD (1920x1080) antirreflejo'),
            ("Gráficos", "AMD Radeon 610M Graphics"),
            ("Teclado", "Español con teclado numérico integrado"),
            ("Garantía", "12 Meses Oficial con respaldo técnico en Caraz"),
        ],
        102: [
            ("Procesador", "AMD Ryzen 5 7520U (4 núcleos / 8 hilos, hasta 4.30GHz)"),
            ("Memoria RAM", "8GB LPDDR5 5500MHz"),
            ("Almacenamiento", "256GB SSD M.2 PCIe NVMe"),
            ("Pantalla", '15.6" Full HD (1920x1080) antirreflejo'),
            ("Gráficos", "AMD Radeon 610M Graphics"),
            ("Conectividad", "Wi-Fi 6 + Bluetooth + RJ-45 Gigabit"),
            ("Garantía", "12 Meses Oficial en tienda Caraz"),
        ],
        103: [
            ("Procesador", "Intel Core i3-1315U 13va Gen (6 núcleos, hasta 4.50GHz)"),
            ("Memoria RAM", "8GB DDR5 5200MHz de alta frecuencia"),
            ("Almacenamiento", "512GB SSD M.2 PCIe Gen4 NVMe"),
            ("Pantalla", '15.6" Full HD (1920x1080) micro-edge'),
            ("Gráficos", "Intel UHD Graphics"),
            ("Teclado", "Español con pad numérico ergonómico"),
            ("Garantía", "12 Meses Oficial en tienda Caraz"),
        ],
        104: [
            ("Procesador", "Intel Core i5-13420H Serie H (8 núcleos / 12 hilos, hasta 4.60GHz)"),
            ("Memoria RAM", "16GB DDR5 4800MHz / 5200MHz"),
            ("Almacenamiento", "512GB SSD M.2 PCIe 4.0 NVMe"),
            ("Pantalla", '15.3" WUXGA (1920x1200) IPS 300 nits 16:10'),
            ("Gráficos", "Intel UHD Graphics 13va Gen"),
            ("Diseño", "Chasis Slim Ultradelgado Gris Ártico"),
            ("Garantía", "12 Meses Oficial en tienda Caraz"),
        ],
        106: [
            ("Procesador", "AMD Ryzen 7 7730U (8 núcleos / 16 hilos, hasta 4.50GHz)"),
            ("Memoria RAM", "16GB DDR4 multitarea fluida"),
            ("Almacenamiento", "512GB SSD M.2 PCIe NVMe de alta velocidad"),
            ("Pantalla", '15.6" Full HD (1920x1080) Touchscreen (Táctil)'),
            ("Gráficos", "AMD Radeon Graphics integrados"),
            ("Sistema Operativo", "Windows 11 Home 64-bit"),
            ("Garantía", "12 Meses Oficial con respaldo técnico en Caraz"),
        ],
        107: [
            ("Procesador", "Intel Core 7 150U de Nueva Generación (10 núcleos / 12 hilos, hasta 5.40GHz)"),
            ("Memoria RAM", "16GB DDR5 5200MHz de última generación"),
            ("Almacenamiento", "512GB SSD M.2 PCIe NVMe Gen4"),
            ("Pantalla", '15.6" Full HD IPS Touchscreen (Táctil) Micro-Edge'),
            ("Gráficos", "Intel Iris Xe Graphics"),
            ("Sistema Operativo", "Windows 11 Home 64-bit"),
            ("Garantía", "12 Meses Oficial en tienda Caraz"),
        ],
        108: [
            ("Procesador", "AMD Ryzen 7 8845HS con IA AMD Ryzen AI (8 núcleos / 16 hilos, hasta 5.10GHz)"),
            ("Memoria RAM", "16GB LPDDR5X 6400MHz ultrarrápida"),
            ("Almacenamiento", "1TB (1000GB) SSD M.2 PCIe Gen4 NVMe"),
            ("Pantalla", '16.0" WUXGA (1920x1200) IPS Touchscreen Convertible 360°'),
            ("Diseño", "2 en 1 Convertible 360° con chasis de aluminio prémium"),
            ("Sistema Operativo", "Windows 11 Home 64-bit"),
            ("Garantía", "12 Meses Oficial en tienda Caraz"),
        ],
        109: [
            ("Procesador", "AMD Ryzen 5 (Arquitectura Zen eficiente)"),
            ("Memoria RAM", "16GB RAM multitarea pro"),
            ("Almacenamiento", "256GB SSD M.2 PCIe NVMe ultra veloz"),
            ("Pantalla", '16.0" WUXGA (1920x1200) IPS Touchscreen Táctil 16:10'),
            ("Línea", "HP OmniBook 3 Chasis Ultraliviano Prémium"),
            ("Sistema Operativo", "Windows 11 Home 64-bit"),
            ("Garantía", "12 Meses Oficial con respaldo técnico en Caraz"),
        ],
        110: [
            ("Procesador", "AMD Ryzen 7 7735HS Alto Rendimiento (8 núcleos / 16 hilos hasta 4.75GHz)"),
            ("Tarjeta Gráfica", "NVIDIA GeForce RTX 3050 con 6GB GDDR6 Dedicados"),
            ("Memoria RAM", "16GB DDR5 4800MHz Gamer"),
            ("Almacenamiento", "512GB SSD M.2 PCIe Gen4 NVMe"),
            ("Pantalla", '15.6" Full HD (1920x1080) 144Hz IPS Antirreflejo Esports'),
            ("Refrigeración", "Sistema Térmico Avanzado Lenovo LOQ Dual Fan"),
            ("Garantía", "12 Meses Oficial en tienda Caraz"),
        ],
    }

    # Si tiene galería registrada en el modelo o en galerias hardcoded
    imagenes = galerias.get(producto.id, producto.get_galeria_imagenes())
    
    # Prioridad: Si el modelo tiene especificaciones configuradas directamente, usarlas; sino usar specs_map o fallback
    specs = producto.get_lista_especificaciones()
    if not specs or len(specs) <= 2:
        specs = specs_map.get(producto.id, specs)

    return JsonResponse({
        'id': producto.id,
        'nombre': producto.nombre,
        'descripcion': producto.descripcion,
        'precio': float(producto.precio),
        'precio_anterior': float(producto.precio_anterior),
        'porcentaje_descuento': producto.porcentaje_descuento,
        'stock': producto.stock,
        'imagenes': imagenes,
        'specs': specs,
        'detalle_url': f'/producto/{producto.id}/',
    })

import json
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction

@require_POST
def api_crear_pedido(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'success': False, 'error': 'Formato JSON inválido.'}, status=400)

    nombre = data.get('nombre', '').strip()
    telefono = data.get('telefono', '').strip()
    dni = data.get('dni', '').strip()
    direccion = data.get('direccion', '').strip()
    referencia = data.get('referencia', '').strip()
    metodo_pago = data.get('metodo_pago', 'yape').strip().lower()
    notas = data.get('notas', '').strip()
    items = data.get('items', [])

    # Validaciones obligatorias
    if not nombre:
        return JsonResponse({'success': False, 'error': 'El nombre completo es obligatorio.'}, status=400)
    if not telefono:
        return JsonResponse({'success': False, 'error': 'El número de teléfono es obligatorio.'}, status=400)
    if not direccion:
        return JsonResponse({'success': False, 'error': 'La dirección de entrega es obligatoria.'}, status=400)
    if not items or not isinstance(items, list):
        return JsonResponse({'success': False, 'error': 'El carrito no tiene productos válidos.'}, status=400)

    costo_envio = Decimal('5.00')

    # Transacción atómica: si algo falla en un producto o stock, se revierte toda la operación
    try:
        with transaction.atomic():
            subtotal_calculado = Decimal('0.00')
            items_a_crear = []

            for item in items:
                prod_id = item.get('id')
                cant = int(item.get('cantidad', 1))

                if cant <= 0:
                    return JsonResponse({'success': False, 'error': 'La cantidad de producto debe ser mayor a 0.'}, status=400)

                # Bloqueo select_for_update para evitar condiciones de carrera (dos compras al mismo tiempo)
                try:
                    producto = Producto.objects.select_for_update().get(id=prod_id, disponible=True)
                except Producto.DoesNotExist:
                    return JsonResponse({'success': False, 'error': f'El producto con ID {prod_id} no está disponible.'}, status=400)

                if producto.stock < cant:
                    return JsonResponse({
                        'success': False, 
                        'error': f'Stock insuficiente para "{producto.nombre}". Disponibles: {producto.stock}'
                    }, status=400)

                # Descontar stock
                producto.stock -= cant
                if producto.stock == 0:
                    producto.disponible = False
                producto.save()

                subtotal_item = producto.precio * cant
                subtotal_calculado += subtotal_item

                items_a_crear.append({
                    'producto': producto,
                    'nombre_producto': producto.nombre,
                    'precio_unitario': producto.precio,
                    'cantidad': cant
                })

            total_calculado = subtotal_calculado + costo_envio

            # Guardar Pedido
            from .models import Pedido, DetallePedido
            pedido = Pedido.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                nombre_completo=nombre,
                telefono=telefono,
                dni=dni,
                direccion=direccion,
                referencia=referencia,
                metodo_pago=metodo_pago,
                costo_envio=costo_envio,
                total=total_calculado,
                estado='PENDIENTE',
                notas=notas
            )

            # Guardar Detalles congelados
            for it in items_a_crear:
                DetallePedido.objects.create(
                    pedido=pedido,
                    producto=it['producto'],
                    nombre_producto=it['nombre_producto'],
                    precio_unitario=it['precio_unitario'],
                    cantidad=it['cantidad']
                )

        return JsonResponse({
            'success': True,
            'pedido_id': pedido.id,
            'total': str(pedido.total),
            'mensaje': f'¡Pedido #{pedido.id} registrado con éxito en Caraz!'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al procesar el pedido: {str(e)}'}, status=500)


def pedidos_view(request):
    """
    Vista de 'Mis Pedidos':
    - Si es Superusuario: puede ver todos los pedidos del sistema y cambiar sus estados.
    - Si es Cliente autenticado: ve únicamente los pedidos asociados a su cuenta o teléfono.
    - Si no está autenticado: redirige a iniciar sesión.
    """
    if not request.user.is_authenticated:
        messages.warning(request, 'Inicia sesión para ver el historial y estado de tus pedidos.')
        return redirect('/login/?next=/pedidos/')

    from .models import Pedido
    es_superuser = request.user.is_superuser or request.user.rol == 'admin'

    if es_superuser:
        pedidos_qs = Pedido.objects.all().prefetch_related('items').order_by('-creado')
    else:
        pedidos_qs = Pedido.objects.filter(
            Q(usuario=request.user) | (Q(telefono=request.user.telefono) & ~Q(telefono=''))
        ).prefetch_related('items').order_by('-creado')

    total_pedidos = pedidos_qs.count()
    pendientes_count = pedidos_qs.filter(estado='PENDIENTE').count()
    en_camino_count = pedidos_qs.filter(estado='EN_CAMINO').count()
    entregados_count = pedidos_qs.filter(estado='ENTREGADO').count()

    return render(request, 'pedidos.html', {
        'pedidos': pedidos_qs,
        'es_superuser': es_superuser,
        'total_pedidos': total_pedidos,
        'pendientes_count': pendientes_count,
        'en_camino_count': en_camino_count,
        'entregados_count': entregados_count,
    })


@require_POST
def actualizar_estado_pedido(request):
    """
    Actualiza el estado de entrega/pago de un pedido.
    RESTRICCIÓN ESTRICTA: Solo permitido para superusuarios.
    """
    if not request.user.is_authenticated or not request.user.is_superuser:
        messages.error(request, '⛔ Acción denegada: Solo el Superusuario tiene autorización para modificar pedidos.')
        return redirect('pedidos')

    from .models import Pedido
    pedido_id = request.POST.get('pedido_id')
    nuevo_estado = request.POST.get('nuevo_estado', '').strip()

    estados_validos = dict(Pedido.ESTADOS_CHOICES).keys()
    if nuevo_estado not in estados_validos:
        messages.error(request, 'Estado de pedido no válido.')
        return redirect('pedidos')

    pedido = get_object_or_404(Pedido, id=pedido_id)
    estado_anterior = pedido.get_estado_display()
    pedido.estado = nuevo_estado
    pedido.save()

    messages.success(request, f'✅ Pedido #{pedido.id} actualizado exitosamente: {estado_anterior} ➔ {pedido.get_estado_display()}')
    return redirect('pedidos')