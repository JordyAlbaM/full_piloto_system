from django.urls import path
from . import views
from terms.views import pagina_cookies, pagina_politica_privacidad, terminos_condiciones, terminos_uso, ruc

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('producto/<int:producto_id>/', views.detalle_producto, name='detalle_producto'),
    path('carrito/', views.carrito, name='carrito'),
    path('api/producto/<int:producto_id>/', views.api_producto_detalle, name='api_producto_detalle'),
    path('api/buscar/', views.api_buscar_productos, name='api_buscar_productos'),
    path('api/crear-pedido/', views.api_crear_pedido, name='api_crear_pedido'),
    # Rutas de la rama feature/terms
    path('cookies/', pagina_cookies, name='pagina_cookies'), 
    path('politica-privacidad/', pagina_politica_privacidad, name='politica_privacidad'),
<<<<<<< HEAD
    path('terminos-condiciones/', terminos_condiciones,name='terminos_condiciones'),
    path('terminos-uso/', terminos_uso,name='terminos_uso'),
    path('ruc/', ruc, name='ruc'),
 ]





=======
    path('terminos-condiciones/', terminos_condiciones, name='terminos_condiciones'),
    path('terminos-uso/', terminos_uso, name='terminos_uso'),
    # Rutas de la rama main
    path('api/importar-infotec/', views.api_importar_infotec, name='api_importar_infotec'),
    path('pedidos/', views.pedidos_view, name='pedidos'),
    path('pedidos/actualizar-estado/', views.actualizar_estado_pedido, name='actualizar_estado_pedido'),
]
>>>>>>> 72498827bfac2aa9039bbe503c9713f4da52c860
