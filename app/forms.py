from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
import re
from .models import Agendamento, FotoGaleria

class AgendamentoForm(forms.ModelForm):
    class Meta:
        model = Agendamento
        fields = ['nome', 'email', 'telefone', 'data', 'hora', 'mensagem']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
            'hora': forms.TimeInput(attrs={'type': 'time'}),
        }
        error_messages = {
            'nome': {'required': "Este campo é obrigatório"},
            'email': {'required': "Este campo é obrigatório"},
            'telefone': {'required': "Este campo é obrigatório"},
            'data': {'required': "Este campo é obrigatório"},
            'hora': {'required': "Este campo é obrigatório"},
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ['nome', 'email', 'telefone', 'data', 'hora']:
            self.fields[field].required = True
            self.fields[field].widget.attrs['required'] = 'required'

    def clean_telefone(self):
        telefone = self.cleaned_data.get('telefone')
        telefone = re.sub(r'\D', '', telefone)
        
        if len(telefone) != 11:
            raise ValidationError("Padrão aceito: (00) 00000-0000.")
        
        return f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}"

    def clean_data(self):
        data = self.cleaned_data.get('data')
        if data < timezone.localdate():
            raise ValidationError("Não é possível agendar para uma data passada.")
        return data

    def clean(self):
        cleaned_data = super().clean()
        data = cleaned_data.get('data')
        hora = cleaned_data.get('hora')
        
        if not data or not hora:
            return cleaned_data
        
        data_hora = datetime.combine(data, hora)
        intervalo_inicio = data_hora - timedelta(minutes=30)
        intervalo_fim = data_hora + timedelta(minutes=30)
        
        conflitos = Agendamento.objects.filter(
            data=data,
            hora__gte=intervalo_inicio.time(),
            hora__lte=intervalo_fim.time(),
            status='aceito'
        )
        
        if conflitos.exists():
            raise ValidationError("Já existe uma reunião neste horário.")
        
        return cleaned_data

class FotoGaleriaForm(forms.ModelForm):
    class Meta:
        model = FotoGaleria
        fields = ['titulo', 'descricao', 'imagem', 'categoria']
        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título da foto'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Descrição da foto',
                'rows': 3
            }),
            'imagem': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'categoria': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'titulo': 'Título',
            'descricao': 'Descrição',
            'imagem': 'Imagem',
            'categoria': 'Categoria',
        }