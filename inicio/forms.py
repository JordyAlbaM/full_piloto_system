from django import forms
from django.contrib.auth import authenticate
from .models import Usuario

class RegistroClienteForm(forms.ModelForm):
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-input-field', 'placeholder': 'Crea una contraseña segura'})
    )
    password_confirm = forms.CharField(
        label='Confirmar Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-input-field', 'placeholder': 'Repite tu contraseña'})
    )

    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'telefono', 'direccion', 'referencia']
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'telefono': 'Teléfono / WhatsApp',
            'direccion': 'Dirección habitual en Caraz',
            'referencia': 'Referencia de entrega',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'Ej: Juan'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'Ej: Pérez'}),
            'email': forms.EmailInput(attrs={'class': 'form-input-field', 'placeholder': 'nombre@correo.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': '943 000 000'}),
            'direccion': forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'Jr. Sucre 715, Caraz'}),
            'referencia': forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'Ej: Frente a Pollería Mayli'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError('El correo electrónico es requerido.')
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta registrada con este correo electrónico.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and len(p1) < 6:
            self.add_error('password', 'La contraseña debe tener al menos 6 caracteres.')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', 'Las contraseñas no coinciden.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data['email'].strip().lower()
        user.email = email
        user.username = email
        user.set_password(self.cleaned_data['password'])
        user.rol = 'cliente'
        if commit:
            user.save()
        return user


class LoginClienteForm(forms.Form):
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'class': 'auth-input', 'placeholder': 'tuemail@ejemplo.com'})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'auth-input', 'placeholder': '••••••••'})
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            email = email.strip().lower()
            user = authenticate(username=email, password=password)
            if not user:
                raise forms.ValidationError('Correo o contraseña incorrectos.')
            if not user.is_active:
                raise forms.ValidationError('Esta cuenta ha sido desactivada.')
            self.user_cache = user
        return cleaned_data

    def get_user(self):
        return getattr(self, 'user_cache', None)


from .models import Producto, Categoria

class ProductoForm(forms.ModelForm):
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.all(),
        required=True,
        empty_label="-- Seleccionar Categoría --",
        widget=forms.Select(attrs={'class': 'form-input-field'})
    )

    class Meta:
        model = Producto
        fields = ['nombre', 'categoria', 'precio', 'stock', 'imagen_url', 'disponible', 'descripcion']
        labels = {
            'nombre': 'Nombre / Modelo de la Laptop o Producto',
            'categoria': 'Categoría',
            'precio': 'Precio de Venta (S/.)',
            'stock': 'Stock Disponible en Caraz',
            'imagen_url': 'URL de Imagen (Enlace Web o Ruta Local)',
            'disponible': '¿Producto Activo para la Venta?',
            'descripcion': 'Descripción y Especificaciones Técnicas',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-input-field',
                'placeholder': 'Ej: Lenovo IdeaPad Slim 3 Core i5 16GB 512GB SSD'
            }),
            'precio': forms.NumberInput(attrs={
                'class': 'form-input-field',
                'placeholder': 'Ej: 2450.00',
                'step': '0.01',
                'min': '1'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'form-input-field',
                'placeholder': 'Ej: 8',
                'min': '0'
            }),
            'imagen_url': forms.URLInput(attrs={
                'class': 'form-input-field',
                'placeholder': 'https://ejemplo.com/laptop.jpg o /static/inicio/images/...'
            }),
            'disponible': forms.CheckboxInput(attrs={
                'class': 'form-checkbox-custom'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-input-field',
                'placeholder': 'Especificaciones detalladas:\n• Procesador: Intel Core i5 13va Gen\n• Memoria RAM: 16GB DDR5\n• Almacenamiento: 512GB SSD NVMe\n• Pantalla: 15.6" Full HD IPS\n• Garantía: 12 Meses en Jr. Sucre 715, Caraz',
                'rows': 5
            }),
        }

    def clean_precio(self):
        precio = self.cleaned_data.get('precio')
        if precio is not None and precio <= 0:
            raise forms.ValidationError('El precio debe ser mayor a 0.')
        return precio

    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        if stock is not None and stock < 0:
            raise forms.ValidationError('El stock no puede ser negativo.')
        return stock
