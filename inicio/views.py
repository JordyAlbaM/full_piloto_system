from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Categoria, Producto

def inicio(request):
    query = request.GET.get('q', '').strip()
    categoria_slug = request.GET.get('categoria', '').strip()

    # Filtro exclusivo de laptops activas
    productos = Producto.objects.filter(disponible=True, categoria__slug='laptops-pc')

    if query:
        productos = productos.filter(
            Q(nombre__icontains=query) | Q(descripcion__icontains=query)
        )

    categorias = Categoria.objects.filter(slug='laptops-pc')

    return render(request, 'index.html', {
        'productos': productos,
        'categorias': categorias,
        'query': query,
        'categoria_seleccionada': categoria_slug,
    })

def detalle_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id, disponible=True)
    productos_relacionados = Producto.objects.filter(
        disponible=True
    ).exclude(id=producto.id)
    if producto.categoria:
        productos_relacionados = productos_relacionados.filter(categoria=producto.categoria)
    productos_relacionados = productos_relacionados[:4]
    
    return render(request, 'detalle.html', {
        'producto': producto,
        'productos_relacionados': productos_relacionados,
    })

def carrito(request):
    return render(request, 'carrito.html')

def login_view(request):
    return render(request, 'login.html')

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

    imagenes = galerias.get(producto.id, [producto.imagen_url] if producto.imagen_url else [])
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