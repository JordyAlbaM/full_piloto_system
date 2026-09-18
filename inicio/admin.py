from django.contrib import admin
from .models import Categoria, Producto

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio', 'stock', 'disponible')
    list_filter = ('categoria', 'disponible')
    search_fields = ('nombre', 'descripcion')
    list_editable = ('precio', 'stock', 'disponible')


from .models import Pedido, DetallePedido

class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    readonly_fields = ('producto', 'nombre_producto', 'precio_unitario', 'cantidad', 'subtotal')
    can_delete = False

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre_completo', 'telefono', 'metodo_pago', 'total', 'estado', 'usuario', 'creado')
    list_filter = ('estado', 'metodo_pago', 'creado')
    search_fields = ('id', 'nombre_completo', 'telefono', 'dni', 'direccion')
    list_editable = ('estado',)
    inlines = [DetallePedidoInline]
    readonly_fields = ('total', 'costo_envio', 'creado', 'actualizado')


from django.contrib.auth.admin import UserAdmin
from .models import Usuario

@admin.register(Usuario)
class CustomUsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ('email', 'first_name', 'last_name', 'telefono', 'rol', 'is_staff', 'is_active')
    list_filter = ('rol', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name', 'telefono', 'dni')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Información Personal', {'fields': ('first_name', 'last_name', 'dni', 'telefono')}),
        ('Dirección de Entrega', {'fields': ('direccion', 'referencia')}),
        ('Permisos y Rol', {'fields': ('rol', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas Importantes', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password', 'rol', 'telefono', 'direccion'),
        }),
    )



