from django.urls import path
from . import views
from terms.views import pagina_cookies, pagina_politica_privacidad, terminos_condiciones, terminos_uso



urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('producto/<int:producto_id>/', views.detalle_producto, name='detalle_producto'),
    path('carrito/', views.carrito, name='carrito'),
    path('api/producto/<int:producto_id>/', views.api_producto_detalle, name='api_producto_detalle'),
    path('api/crear-pedido/', views.api_crear_pedido, name='api_crear_pedido'),
    path('cookies/', pagina_cookies, name='pagina_cookies'), 
    path('politica-privacidad/', pagina_politica_privacidad, name='politica_privacidad'),
    path('terminos-condiciones/', terminos_condiciones,name='terminos_condiciones'),
    path('terminos-uso/', terminos_uso,name='terminos_uso'),
 ]





