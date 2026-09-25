from django.shortcuts import render


def pagina_cookies(request):
    return render(request, 'cookies.html')


def pagina_politica_privacidad(request):
    return render(request, 'politica_privacidad.html')


def terminos_condiciones(request):
    return render(request, 'terminos_condiciones.html')

def terminos_uso(request):
    return render(request, 'terminos_uso.html')




