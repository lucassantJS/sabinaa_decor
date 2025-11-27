from datetime import datetime
import json
import threading
import time
import socket
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.contrib import messages
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
import logging

# Importações dos Models e Constantes
from .models import Agendamento, Orcamento, FotoGaleria, CategoriaFoto, CONSTANTES_PACOTES, CONSTANTES_SERVICOS
from .forms import AgendamentoForm, FotoGaleriaForm

# Configuração de logging - REDUZIDA para evitar rate limit
logger = logging.getLogger(__name__)

# Controle de rate limiting para e-mails
_last_email_time = 0
_email_count = 0

# --- Funções de Email Corrigidas ---
def testar_conexao_email():
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
        return False, f"Falha na conexão: {str(e)}"

def enviar_email_agendamento_servico(agendamento, tipo):
    """Envia e-mail de agendamento - VERSÃO CORRIGIDA DEFINITIVA"""
    global _last_email_time, _email_count
    
    # Rate limiting
    current_time = time.time()
    if current_time - _last_email_time < 1:
        return False, "Rate limit atingido"
    
    _last_email_time = current_time
    _email_count += 1
    
    try:
        if tipo == 'aceito':
            subject = '✅ Confirmação de Agendamento - Sabina Decorações'
            template_html = 'app/email_confirmacao_aceito.html'
        elif tipo == 'recusado':
            subject = '❌ Agendamento Recusado - Sabina Decorações'
            template_html = 'app/email_confirmacao_recusado.html'
        else:
            return False, "Tipo inválido"
        
        # Contexto para os templates
        context = {
            'nome': agendamento.nome,
            'data': agendamento.data.strftime('%d/%m/%Y'),
            'hora': agendamento.hora.strftime('%H:%M'),
            'telefone': agendamento.telefone,
            'mensagem': agendamento.mensagem or 'Não informada'
        }
        
        # ✅ CORREÇÃO: Renderizar HTML separadamente
        html_message = render_to_string(template_html, context)
        
        # ✅ CORREÇÃO: Criar mensagem de texto simples MANUALMENTE
        if tipo == 'aceito':
            plain_message = f"""
CONFIRMAÇÃO DE AGENDAMENTO - Sabina Decorações

Olá {agendamento.nome},

Seu agendamento foi confirmado com sucesso!

📅 Data: {agendamento.data.strftime('%d/%m/%Y')}
⏰ Hora: {agendamento.hora.strftime('%H:%M')}
📞 Telefone: {agendamento.telefone}

{('💬 Sua mensagem: ' + agendamento.mensagem) if agendamento.mensagem else ''}

Estamos ansiosos para atendê-lo!

Atenciosamente,
Sabina Decorações
"""
        else:
            plain_message = f"""
AGENDAMENTO RECUSADO - Sabina Decorações

Olá {agendamento.nome},

Infelizmente não podemos atender seu agendamento para a data solicitada.

📅 Data solicitada: {agendamento.data.strftime('%d/%m/%Y')}
⏰ Horário solicitado: {agendamento.hora.strftime('%H:%M')}

Entre em contato conosco para encontrar uma data alternativa.

📞 Telefone: (44) 99999-9999
📧 E-mail: lucashenri0231@gmail.com

Atenciosamente,
Sabina Decorações
"""
        
        # ✅ CORREÇÃO: Usar EmailMultiAlternatives para controle total
        from django.core.mail import EmailMultiAlternatives
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message.strip(),  # Texto simples
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[agendamento.email],
        )
        email.attach_alternative(html_message, "text/html")  # HTML
        email.send(fail_silently=False)
        
        logger.warning(f"E-mail {tipo} enviado para {agendamento.email}")
        return True, "Sucesso"
        
    except Exception as e:
        logger.warning(f"Erro e-mail: {str(e)}")
        return False, f"Erro: {str(e)}"
    
def testar_template_email(request):
    """Teste visual dos templates de e-mail"""
    from django.template.loader import render_to_string
    
    context = {
        'nome': 'João Silva',
        'data': '15/12/2024',
        'hora': '14:30',
        'telefone': '(44) 99999-9999',
        'mensagem': 'Gostaria de discutir decoração para festa de aniversário.'
    }
    
    template_type = request.GET.get('tipo', 'aceito')
    
    if template_type == 'aceito':
        html = render_to_string('app/email_confirmacao_aceito.html', context)
    else:
        html = render_to_string('app/email_confirmacao_recusado.html', context)
    
    return HttpResponse(html)    

def enviar_email_agendamento_background(agendamento_id, tipo):
    """Função background com proteção contra loops"""
    try:
        agendamento = Agendamento.objects.get(id=agendamento_id)
        success, message = enviar_email_agendamento_servico(agendamento, tipo)
        
        # REMOVA logs de sucesso - apenas erros com warning
        if not success and "Rate limit" not in message:
            logger.warning(f"Falha e-mail: {message}")
            
    except Agendamento.DoesNotExist:
        logger.warning(f"Agendamento {agendamento_id} não existe")
    except Exception as e:
        logger.warning(f"Erro inesperado: {str(e)}")

# --- Funções Auxiliares ---
def converter_preco_input(valor_str):
    """Converte string 'R$ 1.200,50' para float 1200.50"""
    if not valor_str:
        return 0.0
    try:
        limpo = valor_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(limpo)
    except ValueError:
        return 0.0

def task_enviar_email_orcamento(orcamento_id, preco_final_float):
    try:
        orcamento = Orcamento.objects.get(id=orcamento_id)
        preco_final_formatado_br = f"{preco_final_float:.2f}".replace('.', ',')

        pacote_data = CONSTANTES_PACOTES.get(orcamento.pacote_selecionado, {})
        pacote_obj = {'nome': pacote_data.get('nome', orcamento.pacote_selecionado), 'descricao': pacote_data.get('descricao', '')}
        
        servicos_lista = []
        servicos_detalhados = orcamento.get_servicos_detalhados()
        for svc in servicos_detalhados:
            servicos_lista.append({'nome': svc['key'], 'descricao': svc['nome']})

        dados_orcamento = {
            'nome': orcamento.nome,
            'telefone': orcamento.telefone,
            'email': orcamento.email,
            'tipo_evento': orcamento.get_tipo_evento_display(),
            'num_convidados': orcamento.num_convidados,
            'local_evento': 'Espaço interno' if orcamento.local_evento == 'interno' else 'Espaço externo',
            'ideias': orcamento.ideias,
            'preco_final': f"R$ {preco_final_formatado_br}", 
            'orcamento_estimado': f"R$ {orcamento.calcular_orcamento_estimado():.2f}".replace('.', ','),
            'pacote': pacote_obj,
            'servicos': servicos_lista
        }

        email_content = render_to_string('app/email_orcamento_final.html', dados_orcamento)
        plain_message = strip_tags(email_content)
   
        send_mail(
            subject=f"Preço Final Definido - Orçamento #{orcamento.id} - Sabina Decorações",
            message=plain_message,
            html_message=email_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[orcamento.email],
            fail_silently=False,
        )

        if hasattr(settings, 'EMAIL_DESTINO') and settings.EMAIL_DESTINO:
            send_mail(
                subject=f"Cópia: Preço Final Enviado - Orçamento #{orcamento.id}",
                message=f"Preço final de R$ {preco_final_formatado_br} enviado para {orcamento.nome}.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.EMAIL_DESTINO], 
                fail_silently=False,
            )
            
        # LOG SIMPLIFICADO
        logger.warning(f"E-mail orçamento #{orcamento.id} enviado")

    except Exception as e:
        logger.warning(f"Erro e-mail orçamento: {str(e)}")

# --- Views de Diagnóstico (Mantidas mas com logs reduzidos) ---
def diagnostico_email(request):
    """View para diagnóstico completo do problema de e-mail"""
    diagnostics = []
    
    # Teste de DNS
    try:
        socket.gethostbyname('smtp.gmail.com')
        diagnostics.append("✅ DNS do Gmail resolvido")
    except Exception as e:
        diagnostics.append(f"❌ Falha no DNS: {e}")
    
    # Teste de conectividade de rede
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex(('smtp.gmail.com', 587))
        sock.close()
        if result == 0:
            diagnostics.append("✅ Conexão com smtp.gmail.com:587")
        else:
            diagnostics.append(f"❌ Falha na conexão (código: {result})")
    except Exception as e:
        diagnostics.append(f"❌ Erro de socket: {e}")
    
    # Verificar configurações
    diagnostics.append(f"📧 EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'Não definido')}")
    diagnostics.append(f"🔑 EMAIL_PORT: {getattr(settings, 'EMAIL_PORT', 'Não definido')}")
    diagnostics.append(f"👤 EMAIL_HOST_USER: {getattr(settings, 'EMAIL_HOST_USER', 'Não definido')}")
    diagnostics.append(f"🔒 EMAIL_HOST_PASSWORD definido: {'Sim' if hasattr(settings, 'EMAIL_HOST_PASSWORD') and settings.EMAIL_HOST_PASSWORD else 'Não'}")
    
    return HttpResponse("<br>".join(diagnostics))

def testar_sendgrid_direto(request):
    """Teste DIRETO do SendGrid - sem templates, sem HTML"""
    try:
        # Teste MUITO simples - apenas texto
        send_mail(
            subject='🚀 TESTE DIRETO SENDGRID - Sabina Decorações',
            message='Se você está lendo isso, o SendGrid está funcionando PERFEITAMENTE!',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['lucassant@edu.unifil.br'],
            fail_silently=False,
        )
        return HttpResponse("✅ E-mail de teste DIRETO enviado! Verifique SUA CAIXA DE ENTRADA.")
    except Exception as e:
        return HttpResponse(f"❌ Falha no teste direto: {str(e)}")

def testar_email(request):
    """View temporária para testar configuração de e-mail"""
    try:
        success, message = testar_conexao_email()
        if success:
            return HttpResponse("✅ " + message)
        else:
            return HttpResponse("❌ " + message)
    except Exception as e:
        return HttpResponse(f"❌ Erro no teste: {str(e)}")

# --- Views de Autenticação ---
def login_personalizado(request):
    if request.user.is_authenticated:
        return redirect('inicio')
    next_url = request.GET.get('next') or 'inicio'
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(next_url)
    else:
        form = AuthenticationForm()
    return render(request, 'app/login.html', {'form': form, 'next_url': next_url})

def eh_administrador(usuario):
    return usuario.is_authenticated and usuario.is_staff

def logout_personalizado(request):
    logout(request)
    return redirect('inicio')

# --- Views Públicas ---
def inicio(request):
    return render(request, 'app/inicio.html')

def sobre(request):
    return render(request, 'app/sobre.html')

def galeria_fotos(request):
    try:
        fotos = FotoGaleria.objects.filter(ativo=True).select_related('categoria').order_by('-data_upload')
        fotos_com_imagem = [foto for foto in fotos if foto.imagem]
        categorias = CategoriaFoto.objects.all()
        
        context = {
            'fotos': fotos_com_imagem,
            'categorias': categorias,
        }
        return render(request, 'app/galeria_fotos.html', context)
        
    except Exception as e:
        # LOG SIMPLIFICADO
        logger.warning(f"Erro galeria: {e}")
        fotos_fallback = [
            {
                "id": 1,
                "titulo": "Festa Jardim Encantado (Exemplo)",
                "imagem": "app/images/image1.jpg",
                "descricao": "Decoração temática (Fallback).",
                "categoria": "Aniversários"
            },
        ]
        context = {
            'fotos': fotos_fallback,
            'categorias': [],
        }
        return render(request, 'app/galeria_fotos.html', context)

def simulador_orcamento(request):
    tipos_evento = [{'valor': k, 'nome': v} for k, v in Orcamento.TIPO_EVENTO_CHOICES]

    pacotes = []
    for key, data in CONSTANTES_PACOTES.items():
        pacote = data.copy()
        pacote['valor'] = key
        pacotes.append(pacote)

    servicos_adicionais = []
    for key, data in CONSTANTES_SERVICOS.items():
        servico = {'nome': key, 'descricao': data['nome']}
        servicos_adicionais.append(servico)

    if request.method == 'POST':
        dados = request.POST
        nome = dados.get('nome')
        telefone = dados.get('telefone')
        email = dados.get('email')
        tipo_evento_valor = dados.get('tipoEvento')
        num_convidados = dados.get('numeroConvidados')
        pacote_selecionado_valor = dados.get('pacoteSelecionado')
        servicos_escolhidos = dados.getlist('servicos')
        ideias = dados.get('ideias', '')
        local_evento = dados.get('localEvento', 'interno')
        
        required_fields = [nome, telefone, email, tipo_evento_valor, num_convidados, pacote_selecionado_valor]
        
        if not all(required_fields):
            messages.error(request, "Por favor, preencha todos os campos obrigatórios.")
            return render(request, 'app/simulador_orcamento.html', {
                'tipos_evento': tipos_evento, 'pacotes': pacotes, 'servicos_adicionais': servicos_adicionais, 'dados_formulario': dados
            })
        
        try:
            orcamento = Orcamento(
                nome=nome,
                telefone=telefone,
                email=email,
                tipo_evento=tipo_evento_valor,
                num_convidados=num_convidados,
                local_evento=local_evento,
                pacote_selecionado=pacote_selecionado_valor,
                servicos_adicionais=json.dumps(servicos_escolhidos),
                ideias=ideias
            )
            orcamento.full_clean()
            orcamento.save()
            
            messages.success(request, "Seu pedido de orçamento foi recebido com sucesso! Analisaremos suas informações e entraremos em contato em breve.")
            return redirect('simulador_orcamento')
            
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                for campo, erros in e.message_dict.items():
                    for erro in erros:
                        if campo == '__all__':
                            messages.error(request, erro)
                        else:
                            messages.error(request, f"{campo}: {erro}")
            else:
                for erro in e.messages:
                    messages.error(request, erro)
                    
        except Exception as e:
            messages.error(request, f"Ocorreu um erro ao salvar seu orçamento. Tente novamente. Erro: {str(e)}")
    
    return render(request, 'app/simulador_orcamento.html', {
        'tipos_evento': tipos_evento,
        'pacotes': pacotes,
        'servicos_adicionais': servicos_adicionais
    })

def criar_agendamento(request):
    if request.method == 'POST':
        formulario = AgendamentoForm(request.POST)
        if formulario.is_valid():
            try:
                formulario.save()
                messages.success(request, "Seu agendamento foi solicitado com sucesso!")
                return redirect('inicio')
            except ValidationError as e:
                 msg = e.message if hasattr(e, 'message') else str(e)
                 messages.error(request, msg)
            except Exception as e:
                messages.error(request, f"Erro no agendamento: {str(e)}")
        else:
            for field, errors in formulario.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        messages.error(request, f"{field}: {error}")
    else:
        formulario = AgendamentoForm()
        
    return render(request, 'app/cria_agendamento.html', {'form': formulario})

def api_verificar_disponibilidade(request):
    data_str = request.GET.get('data')
    if not data_str:
        return JsonResponse({'error': 'Data não fornecida'}, status=400)
    
    try:
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
        
        agendamentos = Agendamento.objects.filter(
            data=data_obj,
            status__in=['aceito', 'pendente']
        ).values_list('hora', flat=True)
        
        horarios_ocupados = [h.strftime('%H:%M') for h in agendamentos]
        
        return JsonResponse({'ocupados': horarios_ocupados})
        
    except ValueError:
        return JsonResponse({'error': 'Formato de data inválido'}, status=400)

# --- Views de Administração ---
@user_passes_test(eh_administrador, login_url='/admin/login/')
def lista_agendamentos(request):
    agendamentos = Agendamento.objects.all().order_by('-data', '-hora')
    return render(request, 'app/lista_agendamentos.html', {'agendamentos': agendamentos})

@user_passes_test(eh_administrador, login_url='/admin/login/')
def editar_agendamento(request, pk):
    agendamento = get_object_or_404(Agendamento, pk=pk)
    
    if request.method == 'POST':
        formulario = AgendamentoForm(request.POST, instance=agendamento)
        if formulario.is_valid():
            formulario.save()
            return redirect('lista_agendamentos')
        else:
            for field, errors in formulario.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        messages.error(request, f"{field}: {error}")
    else:
        formulario = AgendamentoForm(instance=agendamento)

    return render(request, 'app/edita_agendamento.html', {'form': formulario})

@user_passes_test(eh_administrador, login_url='/admin/login/')
def deletar_agendamento(request, pk):
    agendamento = get_object_or_404(Agendamento, pk=pk)
    if request.method == 'POST':
        agendamento.delete()
        return redirect('lista_agendamentos')
    return render(request, 'app/deleta_agendamento.html', {'agendamento': agendamento})

@user_passes_test(eh_administrador, login_url='/admin/login/')
def aceitar_agendamento(request, pk):
    agendamento = get_object_or_404(Agendamento, pk=pk)
    try:
        agendamento.status = 'aceito'
        agendamento.aceito_por = request.user
        agendamento.recusado_por = None
        
        agendamento.clean() 
        agendamento.save()
        
        # Use thread com daemon=True
        email_thread = threading.Thread(
            target=enviar_email_agendamento_background, 
            args=(agendamento.id, 'aceito'),
            daemon=True
        )
        email_thread.start()
        
        messages.success(request, "Agendamento aceito! E-mail de confirmação está sendo enviado.")
        
    except ValidationError as e:
        if hasattr(e, 'message'):
            msg = e.message
        elif hasattr(e, 'messages'):
            msg = " | ".join(e.messages)
        else:
            msg = str(e)
        messages.error(request, f"Não foi possível aceitar: {msg}")
    except Exception as e:
        messages.error(request, f"Erro inesperado: {str(e)}")
        
    return redirect('lista_agendamentos')

@user_passes_test(eh_administrador, login_url='/admin/login/')
def recusar_agendamento(request, pk):
    agendamento = get_object_or_404(Agendamento, pk=pk)
    try:
        agendamento.status = 'recusado'
        agendamento.recusado_por = request.user
        agendamento.aceito_por = None
        agendamento.save()

        email_thread = threading.Thread(
            target=enviar_email_agendamento_background, 
            args=(agendamento.id, 'recusado'),
            daemon=True
        )
        email_thread.start()

        messages.success(request, "Agendamento recusado. E-mail está sendo enviado.")
        
    except Exception as e:
        messages.error(request, f"Erro ao recusar agendamento: {str(e)}")
        
    return redirect('lista_agendamentos')

@user_passes_test(eh_administrador, login_url=settings.LOGIN_URL)
def gerenciar_galeria(request):
    fotos = FotoGaleria.objects.all().order_by('-data_upload')
    categorias = CategoriaFoto.objects.all()
    return render(request, 'app/gerenciar_galeria.html', {'fotos': fotos, 'categorias': categorias})

@user_passes_test(eh_administrador, login_url=settings.LOGIN_URL)
def adicionar_foto(request):
    if request.method == 'POST':
        form = FotoGaleriaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Foto adicionada com sucesso!")
            return redirect('gerenciar_galeria')
    else:
        form = FotoGaleriaForm()
    
    return render(request, 'app/adicionar_foto.html', {'form': form})

@user_passes_test(eh_administrador, login_url=settings.LOGIN_URL)
def excluir_foto(request, foto_id):
    foto = get_object_or_404(FotoGaleria, id=foto_id)
    if request.method == 'POST':
        foto.delete()
        messages.success(request, "Foto excluída com sucesso!")
        return redirect('gerenciar_galeria')
    return render(request, 'app/excluir_foto.html', {'foto': foto})

@user_passes_test(eh_administrador, login_url=settings.LOGIN_URL)
def lista_orcamentos(request):
    orcamentos = Orcamento.objects.all().order_by('-data_criacao')
    
    tipo_evento_filtro = request.GET.get('tipo_evento')
    if tipo_evento_filtro:
        orcamentos = orcamentos.filter(tipo_evento=tipo_evento_filtro)
    
    context = {
        'orcamentos': orcamentos,
        'total': orcamentos.count(),
        'tipos_evento': Orcamento.TIPO_EVENTO_CHOICES,
    }
    return render(request, 'app/lista_orcamentos.html', context)

@user_passes_test(eh_administrador, login_url=settings.LOGIN_URL)
def detalhes_orcamento(request, orcamento_id):
    orcamento = get_object_or_404(Orcamento, id=orcamento_id)
    orcamento_estimado = orcamento.calcular_orcamento_estimado()
    
    servicos_display = orcamento.get_servicos_detalhados()

    context = {
        'orcamento': orcamento,
        'orcamento_estimado': orcamento_estimado,
        'servicos_display': servicos_display
    }
    return render(request, 'app/detalhes_orcamento.html', context)

@user_passes_test(lambda u: u.is_superuser, login_url='/login/') 
def editar_preco_final(request, orcamento_id):
    orcamento = get_object_or_404(Orcamento, id=orcamento_id)
    
    pacotes_disponiveis = [{'nome': v['nome'], 'descricao': v['descricao'], 'valor': k} for k, v in CONSTANTES_PACOTES.items()]

    if request.method == 'POST':
        preco_final_str = request.POST.get('preco_final')
        enviar_email = request.POST.get('enviar_email') == 'on'
        
        if preco_final_str:
            preco_final_float = converter_preco_input(preco_final_str)
            
            if preco_final_float > 0:
                try:
                    orcamento.preco_final = preco_final_float
                    orcamento.save()
                    
                    if enviar_email:
                        email_thread = threading.Thread(
                            target=task_enviar_email_orcamento,
                            args=(orcamento.id, preco_final_float),
                            daemon=True
                        )
                        email_thread.start()
                        messages.success(request, f"Preço final salvo! O e-mail para {orcamento.email} está sendo enviado em segundo plano.")
                    else:
                        messages.success(request, "Preço final salvo com sucesso! (Opção de enviar e-mail desmarcada)")
                    
                    return redirect('detalhes_orcamento', orcamento_id=orcamento.id)
                except Exception as e:
                     messages.error(request, f"Erro ao salvar: {str(e)}")
            else:
                 messages.error(request, "Valor inválido. Certifique-se de digitar um número maior que zero.")
        else:
            messages.error(request, "Por favor, insira um valor válido para o preço final.")
    
    orcamento_estimado = orcamento.calcular_orcamento_estimado()
    
    context = {
        'orcamento': orcamento,
        'orcamento_estimado': orcamento_estimado,
        'pacotes_disponiveis': pacotes_disponiveis, 
    }
    return render(request, 'app/editar_preco_final.html', context)

@user_passes_test(eh_administrador, login_url=settings.LOGIN_URL)
def excluir_orcamento(request, orcamento_id):
    orcamento = get_object_or_404(Orcamento, id=orcamento_id)
    
    if request.method == 'POST':
        try:
            orcamento_nome = orcamento.nome
            orcamento.delete()
            messages.success(request, f"Orçamento de {orcamento_nome} excluído com sucesso!")
            return redirect('lista_orcamentos')
        except Exception as e:
            messages.error(request, f"Erro ao excluir orçamento: {str(e)}")
    
    return render(request, 'app/excluir_orcamento.html', {'orcamento': orcamento})