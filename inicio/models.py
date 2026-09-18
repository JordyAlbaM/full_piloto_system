from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings

# Gestor personalizado para el Usuario con Email
class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El usuario debe tener un correo electrónico válido.')
        email = self.normalize_email(email)
        extra_fields.setdefault('username', email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('rol', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class Usuario(AbstractUser):
    ROLES_CHOICES = [
        ('cliente', 'Cliente'),
        ('repartidor', 'Repartidor Delivery'),
        ('admin', 'Administrador'),
    ]

    # Hacemos el email único y campo principal
    email = models.EmailField('Correo electrónico', unique=True)
    username = models.CharField(max_length=150, blank=True, null=True)

    # Datos adicionales para delivery y contacto
    telefono = models.CharField('Teléfono / WhatsApp', max_length=20, blank=True)
    dni = models.CharField('DNI', max_length=12, blank=True)
    direccion = models.CharField('Dirección de entrega habitual', max_length=255, blank=True)
    referencia = models.CharField('Referencia de entrega', max_length=255, blank=True)
    rol = models.CharField('Rol de usuario', max_length=20, choices=ROLES_CHOICES, default='cliente')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UsuarioManager()

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        nombre = f"{self.first_name} {self.last_name}".strip()
        return nombre if nombre else self.email


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = 'Categorías'

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='productos', null=True, blank=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=10)
    imagen_url = models.URLField(blank=True, help_text="URL de imagen externa o placeholder")
    disponible = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class Pedido(models.Model):
    ESTADOS_CHOICES = [
        ('PENDIENTE', 'Pendiente de Pago'),
        ('PAGADO', 'Pagado / Confirmado'),
        ('EN_CAMINO', 'En camino (Delivery Caraz)'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]

    METODOS_PAGO_CHOICES = [
        ('yape', 'Yape'),
        ('plin', 'Plin'),
        ('efectivo', 'Efectivo / Contraentrega'),
        ('transferencia', 'Transferencia Bancaria'),
    ]

    # Relación opcional con Usuario registrado
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos'
    )

    # Datos del cliente
    nombre_completo = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)
    dni = models.CharField(max_length=12, blank=True)
    direccion = models.CharField(max_length=255)
    referencia = models.CharField(max_length=255, blank=True)

    # Datos del pedido
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO_CHOICES, default='yape')
    costo_envio = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    estado = models.CharField(max_length=20, choices=ESTADOS_CHOICES, default='PENDIENTE')

    # Notas y auditoría
    notas = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-creado']

    def __str__(self):
        return f"Pedido #{self.id} - {self.nombre_completo}"


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    nombre_producto = models.CharField(max_length=200)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Detalle de Pedido'
        verbose_name_plural = 'Detalles de Pedido'

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f"{self.cantidad}x {self.nombre_producto} (Pedido #{self.pedido_id})"