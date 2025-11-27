# app/email_service.py
import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def testar_conexao():
        """Testa a conexão com o servidor de e-mail"""
        try:
            send_mail(
                subject='Teste de Conexão - Sabina Decorações',
                message='Teste de conexão bem-sucedido.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.DEFAULT_FROM_EMAIL],
                fail_silently=False,
            )
            return True, "Conexão bem-sucedida"
        except Exception as e:
            return False, f"Erro na conexão: {str(e)}"
    
    @staticmethod
    def enviar_email_agendamento(agendamento, tipo):
        """Envia e-mail de agendamento com tratamento robusto de erros"""
        try:
            if tipo == 'aceito':
                subject = 'Confirmação de Agendamento - Sabina Decorações'
                template = 'app/email_confirmacao_aceito.html'
            elif tipo == 'recusado':
                subject = 'Agendamento Recusado - Sabina Decorações'
                template = 'app/email_confirmacao_recusado.html'
            else:
                return False, "Tipo de e-mail inválido"
            
            context = {
                'nome': agendamento.nome,
                'data': agendamento.data,
                'hora': agendamento.hora.strftime('%H:%M'),
                'telefone': agendamento.telefone,
                'mensagem': agendamento.mensagem or 'Não informada'
            }
            
            html_message = render_to_string(template, context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[agendamento.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"✅ E-mail de {tipo} enviado para {agendamento.email}")
            return True, "E-mail enviado com sucesso"
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar e-mail: {str(e)}")
            # Tentar fallback simples
            return EmailService._enviar_fallback(agendamento, tipo, str(e))
    
    @staticmethod
    def _enviar_fallback(agendamento, tipo, erro_original):
        """Fallback simples com e-mail de texto puro"""
        try:
            if tipo == 'aceito':
                subject = 'Confirmação de Agendamento - Sabina Decorações'
                message = f"""Agendamento CONFIRMADO
                
Olá {agendamento.nome},

Seu agendamento foi confirmado:
Data: {agendamento.data}
Hora: {agendamento.hora.strftime('%H:%M')}

Atenciosamente,
Sabina Decorações"""
            else:
                subject = 'Agendamento Recusado - Sabina Decorações'
                message = f"""Agendamento RECUSADO
                
Olá {agendamento.nome},

Não podemos atender seu agendamento:
Data: {agendamento.data}
Hora: {agendamento.hora.strftime('%H:%M')}

Contate-nos para alternativas.

Sabina Decorações"""
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[agendamento.email],
                fail_silently=True,
            )
            
            logger.info(f"✅ E-mail fallback de {tipo} enviado")
            return True, "E-mail fallback enviado"
            
        except Exception as e:
            logger.error(f"❌ Falha total no envio: {str(e)}")
            return False, f"Falha total: {str(e)}"