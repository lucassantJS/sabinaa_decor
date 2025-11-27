from django.urls import path
from . import views

urlpatterns = [
    path('', views.inicio, name='home'),

    # Autenticação
    path('login/', views.login_personalizado, name='login'),
    path('logout/', views.logout_personalizado, name='custom_logout'),

    # Páginas públicas
    path('inicio/', views.inicio, name='inicio'),
    path('sobre/', views.sobre, name='sobre'),
    path('galeria/', views.galeria_fotos, name='galeria_fotos'),
    path('simulador/', views.simulador_orcamento, name='simulador_orcamento'),
    
    # Agendamentos
    path('criar/', views.criar_agendamento, name='cria_agendamento'),
    path('agendamentos/', views.lista_agendamentos, name='lista_agendamentos'),
    path('editar/<int:pk>/', views.editar_agendamento, name='edita_agendamento'),
    path('deletar/<int:pk>/', views.deletar_agendamento, name='deleta_agendamento'),
    path('aceitar/<int:pk>/', views.aceitar_agendamento, name='aceitar_agendamento'),
    path('recusar/<int:pk>/', views.recusar_agendamento, name='recusar_agendamento'),
    
    # Orçamentos
    path('orcamentos/', views.lista_orcamentos, name='lista_orcamentos'),
    path('orcamentos/<int:orcamento_id>/', views.detalhes_orcamento, name='detalhes_orcamento'),
    path('orcamentos/<int:orcamento_id>/editar-preco/', views.editar_preco_final, name='editar_preco_final'),
    path('orcamentos/<int:orcamento_id>/excluir/', views.excluir_orcamento, name='excluir_orcamento'),
    
    # Galeria (admin)
    path('galeria/adicionar/', views.adicionar_foto, name='adicionar_foto'),
    path('galeria/excluir/<int:foto_id>/', views.excluir_foto, name='excluir_foto'),
    path('galeria/gerenciar/', views.gerenciar_galeria, name='gerenciar_galeria'),
    
    # Autenticação
    path('logout/', views.logout_personalizado, name='custom_logout'),
]