import os
import socket # <--- Adicionado
from django.core.wsgi import get_wsgi_application

# --- PATCH PARA FORÇAR IPV4 (CORREÇÃO DO ERRO 101) ---
# O Gmail tenta usar IPv6, mas o servidor bloqueia. Isso obriga a usar IPv4.
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo
# -----------------------------------------------------

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sabina_decor.settings')

application = get_wsgi_application()