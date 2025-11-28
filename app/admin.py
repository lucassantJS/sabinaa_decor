from django.contrib import admin
from .models import Agendamento

@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data', 'hora', 'email', 'telefone')
    list_filter = ('data',)
    search_fields = ('nome', 'email')

# agendamento/admin.py
from django.contrib import admin
from .models import CategoriaFoto, FotoGaleria, Agendamento, Orcamento

@admin.register(CategoriaFoto)
class CategoriaFotoAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']
    list_per_page = 20

@admin.register(FotoGaleria)
class FotoGaleriaAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'categoria', 'data_upload', 'ativo']
    list_filter = ['categoria', 'data_upload', 'ativo']
    search_fields = ['titulo', 'descricao']
    list_per_page = 20
    readonly_fields = ['data_upload', 'imagem_preview']
    
    def imagem_preview(self, obj):
        if obj.imagem:
            return f'<img src="{obj.imagem.url}" style="max-height: 200px;" />'
        return "Sem imagem"
    
    imagem_preview.allow_tags = True
    imagem_preview.short_description = "Preview da Imagem"