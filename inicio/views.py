import os
import uuid
import urllib.request
import re
import json
import html
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.files.storage import default_storage
from .models import Categoria, Producto
from .forms import RegistroClienteForm, LoginClienteForm, ProductoForm


def obtener_datos_infotec(url):
    """Extrae automáticamente nombre, precio, descripción e imágenes de una URL de Infotec"""
    try:
        req = urllib.request.Request(
            url.strip(),
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        content = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
        
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
            
        return {
            'success': True,
            'nombre': nombre,
            'precio': precio,
            'descripcion': desc,
            'imagen_url': main_img,
            'imagenes_secundarias': "\n".join(gallery),
            'total_fotos': (1 if main_img else 0) + len(gallery)
        }
    except Exception as e:
        return {'success': False, 'error': f'No se pudo extraer la información del enlace: {str(e)}'}

def inicio(request):
    query = request.GET.get('q', '').strip()
    categoria_slug = request.GET.get('categoria', '').strip()

    # Si hay filtro de categoría, se aplica; si no, se muestran todos los productos disponibles
    productos = Producto.objects.filter(disponible=True).select_related('categoria')
    if categoria_slug:
        productos = productos.filter(categoria__slug=categoria_slug)

    if query:
        productos = productos.filter(
            Q(nombre__icontains=query) | Q(descripcion__icontains=query)
        )

    categorias = Categoria.objects.all()
    producto_destacado = productos.first() or Producto.objects.filter(disponible=True).select_related('categoria').first()

    return render(request, 'index.html', {
        'productos': productos,
        'categorias': categorias,
        'query': query,
        'categoria_seleccionada': categoria_slug,
        'producto_destacado': producto_destacado,
    })

def detalle_producto(request, producto_id):
    producto = get_object_or_404(Producto.objects.select_related('categoria'), id=producto_id, disponible=True)
    productos_relacionados = Producto.objects.filter(
        disponible=True
    ).exclude(id=producto.id).select_related('categoria')
    if producto.categoria:
        productos_relacionados = productos_relacionados.filter(categoria=producto.categoria)
    productos_relacionados = productos_relacionados[:4]
    
    # Galería dinámica para el producto
    galeria_fotos = producto.get_galeria_imagenes()
    
    return render(request, 'detalle.html', {
        'producto': producto,
        'productos_relacionados': productos_relacionados,
        'galeria_fotos': galeria_fotos,
    })

def carrito(request):
    return render(request, 'carrito.html')

def login_view(request):
    active_tab = request.GET.get('tab', 'login')
    edit_id = request.GET.get('edit')
    producto_a_editar = None
    if edit_id and request.user.is_authenticated and (request.user.is_superuser or request.user.rol == 'admin'):
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
            
            producto_form = ProductoForm(request.POST, request.FILES)
            if producto_form.is_valid():
                nuevo_prod = producto_form.save(commit=False)

                # Si el usuario subió una imagen principal desde su equipo
                if 'imagen_archivo' in request.FILES:
                    img_file = request.FILES['imagen_archivo']
                    file_ext = os.path.splitext(img_file.name)[1].lower() or '.jpg'
                    safe_filename = f"prod_{uuid.uuid4().hex[:8]}{file_ext}"
                    saved_path = default_storage.save(f"productos/{safe_filename}", img_file)
                    nuevo_prod.imagen_url = default_storage.url(saved_path)

                # Si el usuario subió fotos secundarias/galería desde su equipo
                if 'imagenes_secundarias_archivos' in request.FILES:
                    sec_files = request.FILES.getlist('imagenes_secundarias_archivos')
                    urls_nuevas = []
                    for f in sec_files:
                        f_ext = os.path.splitext(f.name)[1].lower() or '.jpg'
                        f_name = f"gallery_{uuid.uuid4().hex[:8]}{f_ext}"
                        s_path = default_storage.save(f"productos/galeria/{f_name}", f)
                        urls_nuevas.append(default_storage.url(s_path))
                    
                    if urls_nuevas:
                        existentes = nuevo_prod.imagenes_secundarias.strip()
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

                # Si sube nueva foto principal
                if 'imagen_archivo' in request.FILES:
                    img_file = request.FILES['imagen_archivo']
                    file_ext = os.path.splitext(img_file.name)[1].lower() or '.jpg'
                    safe_filename = f"prod_{uuid.uuid4().hex[:8]}{file_ext}"
                    saved_path = default_storage.save(f"productos/{safe_filename}", img_file)
                    prod_guardado.imagen_url = default_storage.url(saved_path)

                # Si sube nuevas fotos de galería
                if 'imagenes_secundarias_archivos' in request.FILES:
                    sec_files = request.FILES.getlist('imagenes_secundarias_archivos')
                    urls_nuevas = []
                    for f in sec_files:
                        f_ext = os.path.splitext(f.name)[1].lower() or '.jpg'
                        f_name = f"gallery_{uuid.uuid4().hex[:8]}{f_ext}"
                        s_path = default_storage.save(f"productos/galeria/{f_name}", f)
                        urls_nuevas.append(default_storage.url(s_path))
                    
                    if urls_nuevas:
                        existentes = prod_guardado.imagenes_secundarias.strip()
                        if existentes:
                            prod_guardado.imagenes_secundarias = existentes + "\n" + "\n".join(urls_nuevas)
                        else:
                            prod_guardado.imagenes_secundarias = "\n".join(urls_nuevas)

                prod_guardado.save()
                messages.success(request, f'✅ ¡Producto "{prod_guardado.nombre}" actualizado con éxito!')
                return redirect('/login/?tab=recent_products')
            else:
                producto_a_editar = prod_instance
                err_list = [f"{field}: {', '.join(errs)}" for field, errs in producto_form.errors.items()]
                messages.error(request, f"Error al actualizar el producto: {' | '.join(err_list)}")



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

    return render(request, 'login.html', {
        'login_form': login_form,
        'register_form': register_form,
        'producto_form': producto_form,
        'productos_recientes': productos_admin,
        'producto_a_editar': producto_a_editar,
        'active_tab': active_tab,
        'next': request.GET.get('next', '')
    })

def logout_view(request):
    if request.user.is_authenticated:
        auth_logout(request)
        messages.info(request, 'Has cerrado sesión con éxito.')
    return redirect('inicio')

def api_importar_infotec(request):
    """Endpoint AJAX para extraer datos de Infotec y autocompletar el formulario"""
    if not request.user.is_authenticated or not (request.user.is_superuser or request.user.rol == 'admin'):
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)
    
    url = request.GET.get('url', '').strip()
    if not url:
        return JsonResponse({'success': False, 'error': 'Debes ingresar una URL válida de Infotec.'}, status=400)
    
    data = obtener_datos_infotec(url)
    return JsonResponse(data)

def api_buscar_productos(request):
    """Endpoint AJAX con fetch para autocompletar buscador en tiempo real (muestra hasta 3 productos)."""
    q = request.GET.get('q', '').strip()
    if not q or len(q) < 2:
        return JsonResponse({'productos': [], 'total_coincidencias': 0, 'query': q})

    # Buscar por nombre o descripción en productos disponibles
    qs = Producto.objects.filter(
        disponible=True
    ).filter(
        Q(nombre__icontains=q) | Q(descripcion__icontains=q) | Q(categoria__nombre__icontains=q)
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
    specs = specs_map.get(producto.id, [
        ("Marca / Modelo", producto.nombre),
        ("Categoría", producto.categoria.nombre if producto.categoria else "Laptops & Cómputo"),
        ("Stock", f"{producto.stock} unidades en Caraz"),
        ("Garantía", "12 Meses en tienda Full Piloto System"),
    ])

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