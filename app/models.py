from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import models
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import json
from django.conf import settings

User = settings.AUTH_USER_MODEL

# --- CONSTANTES GLOBAIS (Single Source of Truth) ---
CONSTANTES_PACOTES = {
    'basico': {
        'nome': 'Básico',
        'descricao': 'Decoração simples com flores naturais e arranjos básicos.',
        'icone': 'bi-flower1',
        'preco': 1000
    },
    'premium': {
        'nome': 'Premium',
        'descricao': 'Decoração completa com temas personalizados e iluminação especial.',
        'icone': 'bi-stars',
        'preco': 2500
    },
    'luxo': {
        'nome': 'Luxo',
        'descricao': 'Decoração de luxo com flores importadas e design exclusivo.',
        'icone': 'bi-gem',
        'preco': 5000
    }
}

CONSTANTES_SERVICOS = {
    'fotografo': {'nome': 'Contratação de fotógrafo profissional (8 horas)', 'preco': 300},
    'buffet': {'nome': 'Serviço de buffet completo (comida e bebida)', 'preco': 300},
    'dj': {'nome': 'Animação com DJ e equipamento de som', 'preco': 300},
    'videomaker': {'nome': 'Cobertura em vídeo do evento', 'preco': 300},
    'convites': {'nome': 'Design e impressão de convites personalizados', 'preco': 300},
    'lembrancinhas': {'nome': 'Lembrancinhas personalizadas para os convidados', 'preco': 300},
}

# Validador de telefone (aceita formatos comuns brasileiros)
telefone_validator = RegexValidator(
    regex=r'^\(?\d{2}\)?\s?\d{4,5}-?\d{4}$',
    message="O número de telefone deve estar no formato (XX) XXXXX-XXXX ou similar."
)

class CategoriaFoto(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Categoria de Foto"
        verbose_name_plural = "Categorias de Fotos"

    def __str__(self):
        return self.nome

class FotoGaleria(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    imagem = models.ImageField(upload_to='galeria/')
    categoria = models.ForeignKey(CategoriaFoto, on_delete=models.SET_NULL, null=True, blank=True)
    data_upload = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Foto da Galeria"
        verbose_name_plural = "Fotos da Galeria"
        ordering = ['-data_upload']

    def __str__(self):
        return self.titulo

class Agendamento(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('aceito', 'Aceito'),
        ('recusado', 'Recusado'),
    ]
    
    nome = models.CharField(max_length=255)
    email = models.EmailField()
    telefone = models.CharField(max_length=20, validators=[telefone_validator])
    data = models.DateField()
    hora = models.TimeField()
    mensagem = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pendente')

    orcamento_associado = models.ForeignKey(
            'app.Orcamento', 
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            verbose_name="Orçamento Associado",
            related_name="agendamentos"
        ) 

    aceito_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Aceito por",
        related_name="agendamentos_aceitos"
    ) 

    recusado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Recusado por",
        related_name="agendamentos_recusados"
    )   

    class Meta:
        db_table = 'agendamento'
        verbose_name = "Agendamento de Visita"
        verbose_name_plural = "Agendamentos de Visitas"
        ordering = ['-data', '-hora']

    def clean(self):
        super().clean()
        
        if not self.data or not self.hora:
            return

        # 1. Validação de Dias da Semana (Bloqueia Domingo)
        # Python weekday(): 0=Segunda ... 6=Domingo
        if self.data.weekday() == 6:
            raise ValidationError("Não realizamos agendamentos aos domingos. Por favor, escolha uma data de segunda a sábado.")

        # 2. Validação de Horário Comercial (09:00 às 18:00)
        hora_inicio = 9
        hora_fim = 18
        
        # Bloqueia antes das 9h, depois das 18h, ou exatamente após 18:00 (ex: 18:01)
        if self.hora.hour < hora_inicio or (self.hora.hour >= hora_fim and self.hora.minute > 0) or self.hora.hour > hora_fim:
             raise ValidationError("O horário de agendamento deve ser entre 09:00 e 18:00.")

        try:
            # Cria datetime aware
            dt_input = datetime.combine(self.data, self.hora)
            if timezone.is_naive(dt_input):
                data_hora_agendamento = timezone.make_aware(dt_input)
            else:
                data_hora_agendamento = dt_input
            
            agora = timezone.now()

            # Validação de data passada
            if self.status in ['pendente', 'aceito'] and data_hora_agendamento < agora:
                raise ValidationError("Não é possível agendar para datas ou horas passadas.")

            # Validação de conflito de horário (Janela de 30 min antes e depois)
            if self.status == 'aceito':
                # Define a janela de tempo ocupada por este agendamento
                # Busca conflitos no banco
                # Lógica: Se existe algum agendamento que comece ANTES deste terminar E termine DEPOIS deste começar
                
                conflitos = Agendamento.objects.filter(
                    data=self.data,
                    status='aceito'
                ).exclude(pk=self.pk)

                for conflito in conflitos:
                    dt_conflito = datetime.combine(conflito.data, conflito.hora)
                    if timezone.is_naive(dt_conflito):
                        dt_conflito = timezone.make_aware(dt_conflito)
                    
                    # Diferença absoluta de tempo
                    diff = abs((data_hora_agendamento - dt_conflito).total_seconds())
                    
                    if diff < 1800: # 1800 segundos = 30 minutos
                        raise ValidationError(f"Conflito de horário: Já existe um agendamento às {conflito.hora}.")

        except (ValueError, TypeError):
            raise ValidationError("O formato da data ou da hora fornecida é inválido.")

    def save(self, *args, **kwargs):
        self.full_clean() # Força a validação antes de salvar
        super().save(*args, **kwargs)

    def _enviar_email_confirmacao(self):
        subject = 'Confirmação de Agendamento - Sabina Decorações'
        context = {
            'nome': self.nome,
            'data': self.data,
            'hora': self.hora,
            'telefone': self.telefone,
            'mensagem': self.mensagem
        }
        html_message = render_to_string('app/email_confirmacao_aceito.html', context)
        plain_message = strip_tags(html_message)
        send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [self.email], html_message=html_message)

    def _enviar_email_recusado(self):
        subject = 'Agendamento Recusado - Sabina Decorações'
        context = {
            'nome': self.nome,
            'data': self.data,
            'hora': self.hora,
            'telefone': self.telefone,
            'mensagem': self.mensagem
        }
        html_message = render_to_string('app/email_confirmacao_recusado.html', context)
        plain_message = strip_tags(html_message)
        send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [self.email], html_message=html_message)

    def __str__(self):
        return f"{self.nome} - {self.data} {self.hora} ({self.get_status_display()})"

class Orcamento(models.Model):
    TIPO_EVENTO_CHOICES = [
        ('casamento', 'Casamento'),
        ('aniversario', 'Aniversário'),
        ('corporativo', 'Evento Corporativo'),
        ('infantil', 'Festas Infantis'),
        ('outro', 'Outro'),
    ]
    
    PACOTE_CHOICES = [
        (k, v['nome']) for k, v in CONSTANTES_PACOTES.items()
    ]

    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20, validators=[telefone_validator])
    email = models.EmailField()
    tipo_evento = models.CharField(max_length=20, choices=TIPO_EVENTO_CHOICES)
    num_convidados = models.PositiveIntegerField() # Usar PositiveInteger previne números negativos
    local_evento = models.CharField(max_length=10, choices=[('interno', 'Interno'), ('externo', 'Externo')])
    pacote_selecionado = models.CharField(max_length=20, choices=PACOTE_CHOICES)
    servicos_adicionais = models.TextField(default='[]') # Armazena JSON
    ideias = models.TextField(blank=True)
    data_criacao = models.DateTimeField(default=timezone.now)
    preco_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Preço Final")

    def get_status_display(self):
        if self.preco_final:
            return "Preço Final Definido"
        return "Aguardando Preço Final"

    def get_servicos_list(self):
        """Retorna a lista de chaves dos serviços (ex: ['dj', 'buffet'])"""
        try:
            return json.loads(self.servicos_adicionais)
        except json.JSONDecodeError:
            return []

    def get_servicos_detalhados(self):
        """Retorna lista de dicionários com detalhes dos serviços para exibição"""
        keys = self.get_servicos_list()
        detalhes = []
        for key in keys:
            if key in CONSTANTES_SERVICOS:
                item = CONSTANTES_SERVICOS[key].copy()
                item['key'] = key # Adiciona a chave para referência
                detalhes.append(item)
        return detalhes

    def calcular_orcamento_estimado(self):
        servicos_list = self.get_servicos_list()
        
        # Pega preço base do pacote ou 1000 se não encontrar
        pacote_info = CONSTANTES_PACOTES.get(self.pacote_selecionado)
        preco_base = pacote_info['preco'] if pacote_info else 1000
        
        preco_convidados = self.num_convidados * 50
        
        # Calcula serviços extras baseado nas constantes
        valor_servicos_extra = 0
        for servico_key in servicos_list:
            if servico_key in CONSTANTES_SERVICOS:
                valor_servicos_extra += CONSTANTES_SERVICOS[servico_key]['preco']
            else:
                valor_servicos_extra += 300 # Valor fallback caso a chave mude no futuro
        
        return preco_base + preco_convidados + valor_servicos_extra

    def get_tipo_evento_display(self):
        choices_dict = dict(self.TIPO_EVENTO_CHOICES)
        return choices_dict.get(self.tipo_evento, self.tipo_evento)

    def get_pacote_selecionado_display(self):
        return CONSTANTES_PACOTES.get(self.pacote_selecionado, {}).get('nome', self.pacote_selecionado)

    def __str__(self):
        return f"Orçamento #{self.id} - {self.nome}"