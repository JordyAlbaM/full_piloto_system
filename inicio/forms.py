from django import forms
from django.contrib.auth import authenticate
from .models import Usuario

class RegistroClienteForm(forms.ModelForm):
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'auth-input', 'placeholder': 'Crea una contraseña segura'})
    )
    password_confirm = forms.CharField(
        label='Confirmar Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'auth-input', 'placeholder': 'Repite tu contraseña'})
    )

    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'telefono', 'dni', 'direccion', 'referencia']
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'telefono': 'Teléfono / WhatsApp',
            'dni': 'DNI',
            'direccion': 'Dirección habitual en Caraz',
            'referencia': 'Referencia de entrega',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'auth-input', 'placeholder': 'Ej: Juan'}),
            'last_name': forms.TextInput(attrs={'class': 'auth-input', 'placeholder': 'Ej: Pérez Mendoza'}),
            'email': forms.EmailInput(attrs={'class': 'auth-input', 'placeholder': 'tuemail@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'class': 'auth-input', 'placeholder': 'Ej: 961 081 784'}),
            'dni': forms.TextInput(attrs={'class': 'auth-input', 'placeholder': 'Ej: 71234567'}),
            'direccion': forms.TextInput(attrs={'class': 'auth-input', 'placeholder': 'Ej: Jr. San Martín #450'}),
            'referencia': forms.TextInput(attrs={'class': 'auth-input', 'placeholder': 'Ej: Frente a la plaza'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email').strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta registrada con este correo electrónico.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', 'Las contraseñas no coinciden.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
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
