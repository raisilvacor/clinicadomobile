from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import json
import os
from functools import wraps
from db import (
    create_tables,
    get_site_content as db_get_site_content,
    save_site_content_section,
    get_admin_password,
    save_admin_password,
    get_all_repairs,
    get_repair as db_get_repair,
    save_repair,
    delete_repair as db_delete_repair,
    get_all_suppliers,
    get_supplier as db_get_supplier,
    save_supplier,
    delete_supplier as db_delete_supplier,
    get_all_products,
    get_product as db_get_product,
    save_product,
    delete_product as db_delete_product,
    get_all_brands,
    get_brand as db_get_brand,
    save_brand,
    delete_brand as db_delete_brand,
    get_all_budget_requests,
    save_budget_request,
    update_budget_request_status,
    delete_budget_request,
    get_budget_config,
    save_budget_config,
    transform_budget_config_to_raw,
    get_all_admin_users,
    get_admin_user,
    save_admin_user,
    delete_admin_user,
    get_all_technicians,
    get_technician,
    save_technician,
    delete_technician,
    calculate_technician_quality_score,
    get_all_technician_quality_scores,
    get_business_hours,
    save_business_hours,
    is_business_open as db_is_business_open,
)

app = Flask(__name__)
app.secret_key = 'sua-chave-secreta-mude-isso-em-producao'

# Inicializar banco de dados na inicialização do app
print("🚀 Inicializando aplicação...")
try:
    from db import init_db
    init_db()  # Inicializar pool primeiro
    create_tables()  # Depois criar tabelas
    print("✅ Banco de dados inicializado com sucesso!")
except Exception as e:
    print(f"⚠️  Erro ao inicializar banco de dados: {e}")
    import traceback
    traceback.print_exc()

def get_site_content():
    """Obtém o conteúdo do site do banco de dados"""
    return db_get_site_content()

def login_required(f):
    """Decorator para proteger rotas administrativas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    site_content = get_site_content()
    brands = get_all_brands()
    is_open = db_is_business_open()
    return render_template('index.html', content=site_content, brands=brands, is_open=is_open)

@app.route('/orcamento')
def orcamento_redirect():
    return redirect('/orcamento/')

@app.route('/orcamento/')
def orcamento_index():
    try:
        # Ler configuração e converter para raw
        raw_config = transform_budget_config_to_raw(get_budget_config())
        
        # Ler arquivo original
        index_path = os.path.join('orcamento', 'index.html')
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Injetar script
        # Colocar antes do primeiro script ou no head
        injection = f'<script>window.BUDGET_DATA = {json.dumps(raw_config)};</script>'
        if '<head>' in content:
            content = content.replace('<head>', f'<head>{injection}')
        else:
            # Fallback
            content = injection + content
            
        return content
    except Exception as e:
        print(f"Erro ao servir orcamento/index.html: {e}")
        return send_from_directory('orcamento', 'index.html')

@app.route('/orcamento/<path:filename>')
def orcamento_files(filename):
    return send_from_directory('orcamento', filename)

# ========== ROTAS ADMINISTRATIVAS ==========

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        admin_password = get_admin_password()
        
        if password == admin_password:
            session['logged_in'] = True
            session['admin_name'] = 'Raí Silva'  # Nome do administrador
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin/login.html', error='Senha incorreta!')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    from datetime import datetime, timedelta
    
    # Verificar se há parâmetros de busca na URL
    cpf = request.args.get('cpf', '').strip()
    if cpf:
        # Redirecionar para a rota de busca
        return redirect(url_for('admin_search', cpf=cpf))
    
    # Estatísticas de Ordens de Serviço
    repairs = get_all_repairs()
    total_os = len(repairs)
    os_abertas = 0
    os_finalizadas = 0
    
    for repair in repairs:
        status = (repair.get('status') or '').lower()
        if status in ['concluido', 'concluida', 'finalizado', 'finalizada']:
            os_finalizadas += 1
        elif status not in ['cancelado', 'cancelada']:
            os_abertas += 1
    
    # Contar solicitações de orçamento pendentes
    budget_requests = get_all_budget_requests()
    pending_budget_count = len([r for r in budget_requests if r.get('status') == 'pendente'])
    
    os_stats = {
        'total': total_os,
        'abertas': os_abertas,
        'finalizadas': os_finalizadas
    }
    
    return render_template('admin/dashboard.html',
                         pending_budget_count=pending_budget_count,
                         os_stats=os_stats)

@app.route('/admin/search', methods=['GET'])
@login_required
def admin_search():
    """Busca por CPF do cliente e retorna reparos, ORs e checklists relacionados"""
    cpf = request.args.get('cpf', '').strip()
    search_results = None
    formatted_cpf = None
    search_cpf = None
    
    if cpf:
        search_cpf = cpf
        # Remover formatação do CPF (pontos e traços)
        cpf_clean = cpf.replace('.', '').replace('-', '').replace(' ', '')
        
        if len(cpf_clean) == 11:
            # Formatar CPF para exibição
            formatted_cpf = f"{cpf_clean[:3]}.{cpf_clean[3:6]}.{cpf_clean[6:9]}-{cpf_clean[9:]}"
            
            repairs = get_all_repairs()
            
            # Buscar reparos pelo CPF
            matching_repairs = []
            for repair in repairs:
                repair_cpf = repair.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
                if repair_cpf == cpf_clean:
                    matching_repairs.append(repair)
            
            search_results = {
                'repairs': matching_repairs
            }
    
    return render_template('admin/dashboard.html', 
                         search_results=search_results, 
                         formatted_cpf=formatted_cpf,
                         search_cpf=search_cpf)

@app.route('/admin/hero', methods=['GET', 'POST'])
@login_required
def admin_hero():
    site_content = db_get_site_content()
    hero = site_content.get('hero', {})
    
    if request.method == 'POST':
        hero['title'] = request.form.get('title', '')
        hero['subtitle'] = request.form.get('subtitle', '')
        hero['button_text'] = request.form.get('button_text', '')
        hero['background_image'] = request.form.get('background_image', '')
        
        save_site_content_section('hero', hero)
        
        return redirect(url_for('admin_hero'))
    
    return render_template('admin/hero.html', hero=hero)

@app.route('/admin/services', methods=['GET', 'POST'])
@login_required
def admin_services():
    site_content = db_get_site_content()
    services = site_content.get('services', [])
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            services.append({
                'icon': request.form.get('icon', ''),
                'title': request.form.get('title', ''),
                'description': request.form.get('description', '')
            })
        elif action == 'update':
            index = int(request.form.get('index', 0))
            if 0 <= index < len(services):
                services[index] = {
                    'icon': request.form.get('icon', ''),
                    'title': request.form.get('title', ''),
                    'description': request.form.get('description', '')
                }
        elif action == 'delete':
            index = int(request.form.get('index', 0))
            if 0 <= index < len(services):
                services.pop(index)
        
        save_site_content_section('services', services)
        
        return redirect(url_for('admin_services'))
    
    return render_template('admin/services.html', services=services)

@app.route('/admin/about', methods=['GET', 'POST'])
@login_required
def admin_about():
    site_content = db_get_site_content()
    about = site_content.get('about', {})
    
    if request.method == 'POST':
        about['title'] = request.form.get('title', '')
        about['heading'] = request.form.get('heading', '')
        about['description1'] = request.form.get('description1', '')
        about['description2'] = request.form.get('description2', '')
        about['video'] = request.form.get('video', '')
        
        # Processar features
        features_text = request.form.get('features', '')
        about['features'] = [f.strip() for f in features_text.split('\n') if f.strip()]
        
        save_site_content_section('about', about)
        
        return redirect(url_for('admin_about'))
    
    return render_template('admin/about.html', about=about)

@app.route('/admin/devices', methods=['GET', 'POST'])
@login_required
def admin_devices():
    site_content = db_get_site_content()
    devices = site_content.get('devices', [])
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            devices.append({
                'name': request.form.get('name', ''),
                'image': request.form.get('image', ''),
                'description': request.form.get('description', '')
            })
        elif action == 'update':
            index = int(request.form.get('index', 0))
            if 0 <= index < len(devices):
                devices[index] = {
                    'name': request.form.get('name', ''),
                    'image': request.form.get('image', ''),
                    'description': request.form.get('description', '')
                }
        elif action == 'delete':
            index = int(request.form.get('index', 0))
            if 0 <= index < len(devices):
                devices.pop(index)
        
        save_site_content_section('devices', devices)
        
        return redirect(url_for('admin_devices'))
    
    return render_template('admin/devices.html', devices=devices)

@app.route('/admin/laboratory', methods=['GET', 'POST'])
@login_required
def admin_laboratory():
    site_content = db_get_site_content()
    laboratory = site_content.get('laboratory', {})
    
    if request.method == 'POST':
        laboratory['title'] = request.form.get('title', '')
        
        # Processar imagens
        images_text = request.form.get('images', '')
        laboratory['images'] = [img.strip() for img in images_text.split('\n') if img.strip()]
        
        save_site_content_section('laboratory', laboratory)
        
        return redirect(url_for('admin_laboratory'))
    
    return render_template('admin/laboratory.html', laboratory=laboratory)

@app.route('/api/contact-info')
def api_contact_info():
    site_content = db_get_site_content()
    contact = site_content.get('contact', {})
    return jsonify({
        'whatsapp': contact.get('whatsapp', ''),
        'phone': contact.get('phone', ''),
        'email': contact.get('email', '')
    })

@app.route('/admin/contact', methods=['GET', 'POST'])
@login_required
def admin_contact():
    site_content = db_get_site_content()
    contact = site_content.get('contact', {})
    business_hours = get_business_hours()
    
    if request.method == 'POST':
        contact['phone'] = request.form.get('phone', '')
        contact['email'] = request.form.get('email', '')
        contact['whatsapp'] = request.form.get('whatsapp', '')
        contact['address'] = request.form.get('address', '')
        contact['city'] = request.form.get('city', '')
        contact['hours_weekdays'] = request.form.get('hours_weekdays', '')
        contact['hours_saturday'] = request.form.get('hours_saturday', '')
        contact['hours_sunday'] = request.form.get('hours_sunday', '')
        
        # Remover campos antigos se existirem
        contact.pop('phone1', None)
        contact.pop('phone2', None)
        contact.pop('email1', None)
        contact.pop('email2', None)
        
        save_site_content_section('contact', contact)
        
        # Salvar horários detalhados
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in days:
            open_time = request.form.get(f'{day}_open', '09:00')
            close_time = request.form.get(f'{day}_close', '18:00')
            enabled = request.form.get(f'{day}_enabled') == 'on'
            
            # Garantir formato HH:MM
            if len(open_time) == 5 and ':' in open_time:
                pass  # Já está no formato correto
            elif len(open_time) == 4:  # Formato H:MM
                open_time = '0' + open_time
            else:
                open_time = '09:00'  # Default se inválido
                
            if len(close_time) == 5 and ':' in close_time:
                pass  # Já está no formato correto
            elif len(close_time) == 4:  # Formato H:MM
                close_time = '0' + close_time
            else:
                close_time = '18:00'  # Default se inválido
            
            business_hours[day] = {
                'open': open_time,
                'close': close_time,
                'enabled': enabled
            }
            print(f"💾 Salvando horário {day}: {open_time} - {close_time}, enabled={enabled}")
        
        save_business_hours(business_hours)
        print(f"✅ Horários salvos: {business_hours}")
        
        return redirect(url_for('admin_contact'))
    
    return render_template('admin/contact.html', contact=contact, business_hours=business_hours)

@app.route('/admin/password', methods=['GET', 'POST'])
@login_required
def admin_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        save_admin_password(new_password)
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/password.html')




# ========== CENTRAL DE STATUS DO REPARO ==========

@app.route('/admin/budget-config', methods=['GET', 'POST'])
@login_required
def admin_budget_config():
    """Gerenciar configuração de orçamentos (Marcas, Modelos, Preços)"""
    config = get_budget_config()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_brand':
            brand_name = request.form.get('brand_name')
            if brand_name:
                # Check if brand exists
                if not any(b['brand'] == brand_name for b in config):
                    config.append({'brand': brand_name, 'models': []})
                    save_budget_config(config)
                    
        elif action == 'delete_brand':
            brand_name = request.form.get('brand_name')
            config = [b for b in config if b['brand'] != brand_name]
            save_budget_config(config)
            
        elif action == 'add_model':
            brand_name = request.form.get('brand_name')
            model_name = request.form.get('model_name')
            if brand_name and model_name:
                for brand in config:
                    if brand['brand'] == brand_name:
                        # Check if model exists
                        if not any(m['name'] == model_name for m in brand['models']):
                            brand['models'].append({
                                'name': model_name,
                                'services': []
                            })
                            save_budget_config(config)
                        break
                        
        elif action == 'delete_model':
            brand_name = request.form.get('brand_name')
            model_name = request.form.get('model_name')
            for brand in config:
                if brand['brand'] == brand_name:
                    brand['models'] = [m for m in brand['models'] if m['name'] != model_name]
                    save_budget_config(config)
                    break
                    
        elif action == 'update_prices':
            brand_name = request.form.get('brand_name')
            model_name = request.form.get('model_name')
            
            services_map = [
                "Troca de Tela", "Troca de Vidro", "Troca de Bateria", 
                "Troca de Conector", "Troca de Tampa", "Troca de Lente", 
                "Reparo de Face ID"
            ]
            
            new_services = []
            for service in services_map:
                price = request.form.get(f'price_{service}')
                if price:
                    new_services.append({'service': service, 'price': price})
            
            # Add "Outro Defeito"
            new_services.append({
                "service": "Outro Defeito",
                "price": "Consulte",
                "action": "instagram"
            })
            
            for brand in config:
                if brand['brand'] == brand_name:
                    for model in brand['models']:
                        if model['name'] == model_name:
                            model['services'] = new_services
                            save_budget_config(config)
                            break
                    break
        
        return redirect(url_for('admin_budget_config'))
        
    return render_template('admin/budget_config.html', config=config)

@app.route('/admin/budget-requests', methods=['GET'])
@login_required
def admin_budget_requests():
    """Visualiza solicitações de orçamento"""
    from db import calculate_customer_risk_score
    
    try:
        requests = get_all_budget_requests()
        # Contar pendentes para notificação
        pending_count = len([r for r in requests if r.get('status') == 'pendente'])
        
        # Calcular score de risco para cada solicitação
        requests_with_score = []
        for req in requests:
            try:
                # Garantir que req é um dicionário
                if not isinstance(req, dict):
                    req = dict(req) if hasattr(req, '__dict__') else {}
                
                req_copy = req.copy()
                
                # Extrair CPF de diferentes formatos possíveis
                cpf = req_copy.get('customer_cpf', '')
                if not cpf and isinstance(req_copy.get('data'), dict):
                    cpf = req_copy.get('data', {}).get('customer_cpf', '')
                if not cpf:
                    # Tentar extrair de outros campos possíveis
                    cpf = req_copy.get('cpf', '')
                
                if cpf:
                    try:
                        risk_score = calculate_customer_risk_score(cpf)
                        req_copy['risk_score'] = risk_score
                    except Exception as e:
                        print(f"Erro ao calcular score de risco para CPF {cpf}: {e}")
                        req_copy['risk_score'] = {
                            'score': 0,
                            'level': 'low',
                            'label': '🟢 Baixo risco',
                            'details': {'message': 'Erro ao calcular score'}
                        }
                else:
                    req_copy['risk_score'] = {
                        'score': 0,
                        'level': 'low',
                        'label': '🟢 Baixo risco',
                        'details': {'message': 'CPF não informado'}
                    }
                requests_with_score.append(req_copy)
            except Exception as e:
                print(f"Erro ao processar solicitação: {e}")
                # Adicionar mesmo com erro, sem score
                req_copy = req.copy() if isinstance(req, dict) else dict(req)
                req_copy['risk_score'] = {
                    'score': 0,
                    'level': 'low',
                    'label': '🟢 Baixo risco',
                    'details': {'message': 'Erro ao processar'}
                }
                requests_with_score.append(req_copy)
        
        return render_template('admin/budget_requests.html', requests=requests_with_score, pending_count=pending_count)
    except Exception as e:
        print(f"Erro crítico em admin_budget_requests: {e}")
        import traceback
        traceback.print_exc()
        # Retornar página de erro ou lista vazia
        return render_template('admin/budget_requests.html', requests=[], pending_count=0)

@app.route('/admin/nfse', methods=['GET'])
@login_required
def admin_nfse():
    """Redireciona para o portal oficial de NFS-e do governo"""
    return redirect('https://www.nfse.gov.br/EmissorNacional/Login?ReturnUrl=%2fEmissorNacional')

@app.route('/admin/financeiro', methods=['GET'])
@login_required
def admin_financeiro():
    """Gestão financeira - relatórios e métricas"""
    from db import get_financial_summary
    from datetime import datetime, timedelta
    
    # Obter parâmetros de data
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    # Se não houver datas, usar o mês atual para contexto inicial
    if not start_date:
        now = datetime.now()
        start_date = now.replace(day=1).strftime('%Y-%m-%d')
    if not end_date:
        now = datetime.now()
        next_month = now.replace(day=28) + timedelta(days=4)
        end_date = (next_month - timedelta(days=next_month.day)).strftime('%Y-%m-%d')
    
    # Buscar resumo financeiro consolidado
    summary_data = get_financial_summary(start_date, end_date)
    
    return render_template('admin/financeiro.html', 
                         financial_data=summary_data, # Usando a nova estrutura consolidada
                         start_date=start_date,
                         end_date=end_date)

@app.route('/admin/financeiro/transaction/add', methods=['POST'])
@login_required
def admin_add_transaction():
    """Adiciona uma nova transação financeira manual"""
    from db import save_transaction
    import uuid
    from datetime import datetime
    
    try:
        transaction_id = str(uuid.uuid4())[:8]
        
        amount_str = request.form.get('amount', '0').replace('R$', '').replace('.', '').replace(',', '.')
        amount = float(amount_str)
        
        transaction_data = {
            'id': transaction_id,
            'type': request.form.get('type'), # 'income' ou 'expense'
            'category': request.form.get('category'),
            'description': request.form.get('description', ''),
            'amount': amount,
            'date': request.form.get('date') or datetime.now().strftime('%Y-%m-%d'),
            'created_at': datetime.now().isoformat()
        }
        
        save_transaction(transaction_id, transaction_data)
        
        return redirect(url_for('admin_financeiro'))
    except Exception as e:
        return f"Erro ao salvar transação: {e}", 500

@app.route('/admin/financeiro/transaction/<transaction_id>/delete', methods=['POST'])
@login_required
def admin_delete_transaction(transaction_id):
    """Remove uma transação financeira"""
    from db import delete_transaction
    try:
        delete_transaction(transaction_id)
        return redirect(url_for('admin_financeiro'))
    except Exception as e:
        return f"Erro ao excluir transação: {e}", 500


@app.route('/admin/risk-scores', methods=['GET'])
@login_required
def admin_risk_scores():
    """Visualiza scores de risco de todos os clientes"""
    from db import calculate_customer_risk_score, get_all_repairs
    
    # Buscar todos os reparos
    repairs = get_all_repairs()
    
    # Agrupar por CPF do cliente
    customers = {}
    for repair in repairs:
        cpf = repair.get('customer_cpf', '')
        if cpf:
            cpf_clean = cpf.replace('.', '').replace('-', '').replace(' ', '')
            if cpf_clean not in customers:
                customers[cpf_clean] = {
                    'cpf': cpf,
                    'name': repair.get('customer_name', 'N/A'),
                    'phone': repair.get('customer_phone', 'N/A'),
                    'email': repair.get('customer_email', ''),
                    'repairs': []
                }
            customers[cpf_clean]['repairs'].append(repair)
    
    # Calcular score de risco para cada cliente
    customers_with_score = []
    for cpf_clean, customer_data in customers.items():
        risk_score = calculate_customer_risk_score(cpf_clean)
        customer_data['risk_score'] = risk_score
        customer_data['total_repairs'] = len(customer_data['repairs'])
        customers_with_score.append(customer_data)
    
    # Ordenar por score (maior risco primeiro)
    customers_with_score.sort(key=lambda x: x['risk_score']['score'], reverse=True)
    
    # Filtrar por nível de risco se solicitado
    risk_filter = request.args.get('risk_level', '')
    if risk_filter:
        customers_with_score = [c for c in customers_with_score if c['risk_score']['level'] == risk_filter]
    
    return render_template('admin/risk_scores.html', 
                         customers=customers_with_score,
                         risk_filter=risk_filter)

# ========== ROTAS DE USUÁRIOS DO ADMIN ==========

@app.route('/admin/users', methods=['GET'])
@login_required
def admin_users():
    """Lista todos os usuários do admin"""
    users = get_all_admin_users()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/new', methods=['GET', 'POST'])
@login_required
def admin_new_user():
    """Cria um novo usuário do admin"""
    if request.method == 'POST':
        import uuid
        user_id = str(uuid.uuid4())[:8]
        user_data = {
            'username': request.form.get('username', '').strip(),
            'name': request.form.get('name', '').strip(),
            'email': request.form.get('email', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'password': request.form.get('password', '').strip(),
            'is_active': request.form.get('is_active') == 'on',
            'permissions': {
                'repairs': request.form.get('perm_repairs') == 'on',
                'checklist': request.form.get('perm_checklist') == 'on',
                'orders': request.form.get('perm_orders') == 'on',
                'suppliers': request.form.get('perm_suppliers') == 'on',
                'products': request.form.get('perm_products') == 'on',
                'budget_requests': request.form.get('perm_budget_requests') == 'on',
                'financeiro': request.form.get('perm_financeiro') == 'on',
                'risk_scores': request.form.get('perm_risk_scores') == 'on',
                'users': request.form.get('perm_users') == 'on',
                'technicians': request.form.get('perm_technicians') == 'on',
                'settings': request.form.get('perm_settings') == 'on'
            }
        }
        save_admin_user(user_id, user_data)
        return redirect(url_for('admin_users'))
    
    return render_template('admin/user_form.html', user=None)

@app.route('/admin/users/<user_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    """Edita um usuário do admin"""
    user = get_admin_user(user_id)
    if not user:
        return redirect(url_for('admin_users'))
    
    if request.method == 'POST':
        user_data = {
            'username': request.form.get('username', '').strip(),
            'name': request.form.get('name', '').strip(),
            'email': request.form.get('email', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'is_active': request.form.get('is_active') == 'on',
            'permissions': {
                'repairs': request.form.get('perm_repairs') == 'on',
                'checklist': request.form.get('perm_checklist') == 'on',
                'orders': request.form.get('perm_orders') == 'on',
                'suppliers': request.form.get('perm_suppliers') == 'on',
                'products': request.form.get('perm_products') == 'on',
                'budget_requests': request.form.get('perm_budget_requests') == 'on',
                'financeiro': request.form.get('perm_financeiro') == 'on',
                'risk_scores': request.form.get('perm_risk_scores') == 'on',
                'users': request.form.get('perm_users') == 'on',
                'technicians': request.form.get('perm_technicians') == 'on',
                'settings': request.form.get('perm_settings') == 'on'
            }
        }
        # Só atualizar senha se foi informada
        new_password = request.form.get('password', '').strip()
        if new_password:
            user_data['password'] = new_password
        
        save_admin_user(user_id, user_data)
        return redirect(url_for('admin_users'))
    
    return render_template('admin/user_form.html', user=user)

@app.route('/admin/users/<user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    """Exclui um usuário do admin"""
    delete_admin_user(user_id)
    return redirect(url_for('admin_users'))

# ========== ROTAS DE TÉCNICOS ==========

@app.route('/admin/technicians', methods=['GET'])
@login_required
def admin_technicians():
    """Lista todos os técnicos"""
    technicians = get_all_technicians()
    return render_template('admin/technicians.html', technicians=technicians)

@app.route('/admin/technicians/new', methods=['GET', 'POST'])
@login_required
def admin_new_technician():
    """Cria um novo técnico"""
    if request.method == 'POST':
        import uuid
        technician_id = str(uuid.uuid4())[:8]
        specialties = request.form.getlist('specialties')
        technician_data = {
            'name': request.form.get('name', '').strip(),
            'cpf': request.form.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', ''),
            'email': request.form.get('email', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'address': request.form.get('address', '').strip(),
            'specialties': specialties if specialties else [],
            'is_active': request.form.get('is_active') == 'on'
        }
        save_technician(technician_id, technician_data)
        return redirect(url_for('admin_technicians'))
    
    return render_template('admin/technician_form.html', technician=None)

@app.route('/admin/technicians/<technician_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_technician(technician_id):
    """Edita um técnico"""
    technician = get_technician(technician_id)
    if not technician:
        return redirect(url_for('admin_technicians'))
    
    if request.method == 'POST':
        specialties = request.form.getlist('specialties')
        technician_data = {
            'name': request.form.get('name', '').strip(),
            'cpf': request.form.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', ''),
            'email': request.form.get('email', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'address': request.form.get('address', '').strip(),
            'specialties': specialties if specialties else [],
            'is_active': request.form.get('is_active') == 'on'
        }
        save_technician(technician_id, technician_data)
        return redirect(url_for('admin_technicians'))
    
    return render_template('admin/technician_form.html', technician=technician)

@app.route('/admin/technicians/<technician_id>/delete', methods=['POST'])
@login_required
def admin_delete_technician(technician_id):
    """Exclui um técnico"""
    delete_technician(technician_id)
    return redirect(url_for('admin_technicians'))

# ========== ROTAS DE SCORE DE QUALIDADE DO TÉCNICO ==========

@app.route('/admin/technician-quality', methods=['GET'])
@login_required
def admin_technician_quality():
    """Dashboard de qualidade dos técnicos"""
    quality_scores = get_all_technician_quality_scores()
    
    # Filtrar por nível se solicitado
    quality_filter = request.args.get('filter', 'all')
    if quality_filter != 'all':
        quality_scores = [s for s in quality_scores if s['quality_score']['level'] == quality_filter]
    
    return render_template('admin/technician_quality.html', 
                         quality_scores=quality_scores,
                         quality_filter=quality_filter)

@app.route('/admin/budget-requests/<request_id>/delete', methods=['POST'])
@login_required
def admin_delete_budget_request(request_id):
    """Exclui uma solicitação de orçamento"""
    try:
        delete_budget_request(request_id)
        return jsonify({'success': True, 'message': 'Solicitação excluída com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/budget-requests/<request_id>/update', methods=['POST'])
@login_required
def admin_update_budget_request(request_id):
    """Atualiza o status e notas de uma solicitação de orçamento"""
    try:
        data = request.json
        status = data.get('status')
        admin_notes = data.get('admin_notes')
        
        if not status:
            return jsonify({'success': False, 'error': 'Status é obrigatório'}), 400
            
        update_budget_request_status(request_id, status, admin_notes)
        return jsonify({'success': True, 'message': 'Solicitação atualizada com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/repairs', methods=['GET'])
@login_required
def admin_repairs():
    repairs = get_all_repairs()
    # Ordenar por data mais recente
    repairs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return render_template('admin/repairs.html', repairs=repairs)

@app.route('/admin/repairs/new', methods=['GET', 'POST'])
@login_required
def admin_new_repair():
    from datetime import datetime
    import uuid
    
    if request.method == 'POST':
        repair_id = str(uuid.uuid4())[:8]
        
        # Dados do Wizard
        device_brand = request.form.get('device_brand', '')
        device_model = request.form.get('device_model', '')
        device_type = request.form.get('device_type', 'Celular')
        
        labor_value = float(request.form.get('labor_value') or 0)
        parts_value = float(request.form.get('parts_value') or 0)
        discount_value = float(request.form.get('discount_value') or 0)
        total_budget = (labor_value + parts_value) - discount_value
        
        repair = {
            'id': repair_id,
            'repair_type': 'novo',
            'device_name': f"{device_brand} {device_model}",
            'device_brand': device_brand,
            'device_model': device_model,
            'device_type': device_type,
            'device_imei': request.form.get('imei_serial', ''),
            'imei_serial': request.form.get('imei_serial', ''),
            'problem_description': request.form.get('problem_description', ''),
            'accessories': request.form.get('accessories', ''),
            'customer_name': request.form.get('customer_name', ''),
            'customer_phone': request.form.get('customer_phone', ''),
            'customer_cpf': request.form.get('customer_cpf', ''),
            'service_type': request.form.get('service_type', 'analise'),
            'delivery_forecast': request.form.get('delivery_forecast', ''),
            'status': 'aguardando', # Iniciar sempre como aguardando para o Kanban
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'budget': {
                'labor': labor_value,
                'parts': parts_value,
                'discount': discount_value,
                'total': total_budget,
                'status': 'pending'
            } if total_budget > 0 else None,
            'messages': [],
            'history': [{
                'timestamp': datetime.now().isoformat(),
                'action': 'Ordem de Serviço criada via Wizard',
                'status': 'aguardando'
            }]
        }
        
        # Salvar diretamente no banco de dados
        save_repair(repair_id, repair)
        
        # Redirecionar para a lista de reparos
        return redirect(url_for('admin_repairs'))
    
    technicians = get_all_technicians()
    return render_template('admin/new_os_wizard.html', technicians=technicians)
    return render_template('admin/new_os_wizard.html', technicians=technicians)

@app.route('/admin/repairs/<repair_id>/status', methods=['POST'])
@login_required
def admin_update_status(repair_id):
    from datetime import datetime
    import json
    
    data = request.get_json()
    new_status = data.get('status', '')
    
    repair = db_get_repair(repair_id)
    if not repair:
        return jsonify({'success': False, 'error': 'Reparo não encontrado'})
    
    old_status = repair.get('status', '')
    repair['status'] = new_status
    repair['updated_at'] = datetime.now().isoformat()
    repair['history'].append({
        'timestamp': datetime.now().isoformat(),
        'action': f'Status alterado: {old_status} → {new_status}',
        'status': new_status
    })
    save_repair(repair_id, repair)
    
    return jsonify({'success': True})

@app.route('/admin/repairs/<repair_id>/budget/approve', methods=['POST'])
@login_required
def admin_approve_budget(repair_id):
    from datetime import datetime
    import json
    
    repair = db_get_repair(repair_id)
    if not repair or not repair.get('budget'):
        return jsonify({'success': False})
    
    repair['budget']['status'] = 'approved'
    repair['status'] = 'aprovado'
    repair['updated_at'] = datetime.now().isoformat()
    repair['history'].append({
        'timestamp': datetime.now().isoformat(),
        'action': 'Orçamento aprovado pelo administrador',
        'status': 'aprovado'
    })
    repair['messages'].append({
        'type': 'budget_approved',
        'content': f'Orçamento de R$ {repair["budget"]["amount"]:.2f} foi aprovado. O reparo será iniciado em breve.',
        'sent_at': datetime.now().isoformat()
    })
    save_repair(repair_id, repair)
    return jsonify({'success': True})

@app.route('/admin/repairs/<repair_id>/budget/reject', methods=['POST'])
@login_required
def admin_reject_budget(repair_id):
    from datetime import datetime
    import json
    
    repair = db_get_repair(repair_id)
    if not repair or not repair.get('budget'):
        return jsonify({'success': False})
    
    repair['budget']['status'] = 'rejected'
    repair['status'] = 'aguardando'
    repair['updated_at'] = datetime.now().isoformat()
    repair['history'].append({
        'timestamp': datetime.now().isoformat(),
        'action': 'Orçamento rejeitado pelo administrador',
        'status': 'aguardando'
    })
    repair['messages'].append({
        'type': 'budget_rejected',
        'content': f'Orçamento de R$ {repair["budget"]["amount"]:.2f} foi rejeitado.',
        'sent_at': datetime.now().isoformat()
    })
    save_repair(repair_id, repair)
    return jsonify({'success': True})

@app.route('/admin/repairs/<repair_id>/message', methods=['POST'])
@login_required
def admin_send_message(repair_id):
    from datetime import datetime
    import json
    
    data = request.get_json()
    message_content = data.get('message', '')
    
    repair = db_get_repair(repair_id)
    if not repair:
        return jsonify({'success': False})
    
    if 'messages' not in repair:
        repair['messages'] = []
    
    repair['messages'].append({
        'type': 'admin',
        'content': message_content,
        'sent_at': datetime.now().isoformat()
    })
    repair['updated_at'] = datetime.now().isoformat()
    save_repair(repair_id, repair)
    
    return jsonify({'success': True})

@app.route('/admin/repairs/<repair_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_repair(repair_id):
    from datetime import datetime
    
    repair = db_get_repair(repair_id)
    if not repair:
        return redirect(url_for('admin_repairs'))
    
    if request.method == 'POST':
        repair['repair_type'] = request.form.get('repair_type', 'novo')  # 'novo' ou 'retorno'
        repair['device_name'] = request.form.get('device_name', '')
        repair['device_model'] = request.form.get('device_model', '')
        repair['device_imei'] = request.form.get('device_imei', '')
        repair['problem_description'] = request.form.get('problem_description', '')
        repair['customer_name'] = request.form.get('customer_name', '')
        repair['customer_phone'] = request.form.get('customer_phone', '')
        repair['customer_cpf'] = request.form.get('customer_cpf', '')
        repair['customer_address'] = request.form.get('customer_address', '')
        repair['customer_email'] = request.form.get('customer_email', '')
        repair['technician_id'] = request.form.get('technician_id', '')
        repair['technical_diagnosis'] = request.form.get('technical_diagnosis', '')
        repair['updated_at'] = datetime.now().isoformat()
        
        save_repair(repair_id, repair)
        return redirect(url_for('admin_repairs'))
    
    technicians = get_all_technicians()
    return render_template('admin/edit_repair.html', repair=repair, technicians=technicians)

@app.route('/admin/repairs/<repair_id>/generate_qr', methods=['POST'])
@login_required
def admin_generate_qr(repair_id):
    from datetime import datetime, timedelta
    import uuid
    repair = db_get_repair(repair_id)
    if not repair:
        return jsonify({'success': False, 'error': 'Reparo não encontrado'})
    token = uuid.uuid4().hex[:12]
    expires_at = datetime.now() + timedelta(minutes=3)
    if 'qr_tests' not in repair:
        repair['qr_tests'] = []
    repair['qr_tests'].append({
        'token': token,
        'created_at': datetime.now().isoformat(),
        'expires_at': expires_at.isoformat()
    })
    save_repair(repair_id, repair)
    url = url_for('quality_test', token=token, _external=True)
    return jsonify({'success': True, 'url': url, 'expires_in': 180, 'expires_at': expires_at.isoformat()})

@app.route('/tests/<token>')
def quality_test(token):
    from datetime import datetime
    repairs = get_all_repairs()
    found = None
    for r in repairs:
        for t in r.get('qr_tests', []):
            if t.get('token') == token:
                found = {'repair': r, 'token': t}
                break
        if found:
            break
    if not found:
        return f"<html><head><meta name='viewport' content='width=device-width,initial-scale=1' /></head><body style='font-family: system-ui; margin: 0; padding: 2rem;'><h2>QR Code inválido</h2><p>Gere um novo QR Code no painel.</p></body></html>"
    try:
        exp = datetime.fromisoformat(found['token']['expires_at'])
    except Exception:
        exp = None
    if exp and datetime.now() > exp:
        return f"<html><head><meta name='viewport' content='width=device-width,initial-scale=1' /></head><body style='font-family: system-ui; margin: 0; padding: 2rem;'><h2>QR Code expirado</h2><p>Peça ao técnico para gerar novamente.</p></body></html>"
    title = "Checklist de Qualidade"
    os_id = found['repair'].get('id')
    return f"<html><head><meta name='viewport' content='width=device-width,initial-scale=1' /></head><body style='font-family: system-ui; margin: 0; padding: 2rem; text-align:center;'><h2>{title}</h2><p>OS {os_id}</p><p>Inicie os testes no aparelho.</p></body></html>"



























@app.route('/admin/repairs/<repair_id>/status', methods=['POST'])
@login_required
def admin_update_repair_status(repair_id):
    repair = db_get_repair(repair_id)
    if not repair:
        return jsonify({'success': False, 'error': 'Reparo não encontrado'})
    
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status:
        old_status = repair.get('status', 'N/A')
        repair['status'] = new_status
        repair['updated_at'] = datetime.now().isoformat()
        
        repair['history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': f'Status alterado de {old_status} para {new_status}',
            'status': new_status
        })
        
        save_repair(repair_id, repair)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Status inválido'})

@app.route('/admin/repairs/<repair_id>/observation', methods=['POST'])
@login_required
def admin_add_repair_observation(repair_id):
    repair = db_get_repair(repair_id)
    if not repair:
        return jsonify({'success': False, 'error': 'Reparo não encontrado'})
    
    data = request.get_json()
    observation = data.get('observation')
    
    if observation:
        repair['history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': f'OBSERVAÇÃO: {observation}',
            'status': repair.get('status', 'em_reparo')
        })
        
        save_repair(repair_id, repair)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Observação vazia'})

@app.route('/admin/repairs/<repair_id>/complete', methods=['POST'])
@login_required
def admin_complete_repair(repair_id):
    from datetime import datetime, timedelta
    import json
    
    repair = db_get_repair(repair_id)
    if not repair:
        return jsonify({'success': False, 'error': 'Reparo não encontrado'})
    
    data = request.get_json() or {}
    notes = data.get('notes', '')
    checklist = data.get('checklist', {})
    
    repair['status'] = 'concluido'
    repair['completed_at'] = datetime.now().isoformat()
    repair['updated_at'] = datetime.now().isoformat()
    repair['technical_notes'] = notes
    repair['final_checklist'] = checklist
    
    # Gerar garantia (90 dias)
    warranty_until = datetime.now() + timedelta(days=90)
    repair['warranty'] = {
        'period': '90 dias',
        'valid_until': warranty_until.isoformat(),
        'coverage': 'Peças e mão de obra'
    }
    
    repair['history'].append({
        'timestamp': datetime.now().isoformat(),
        'action': f'Reparo concluído - Garantia de 90 dias ativada. Notas: {notes[:50]}...',
        'status': 'concluido'
    })
    
    # Adicionar mensagem automática de conclusão
    repair['messages'].append({
        'type': 'completed',
        'content': 'Seu reparo foi concluído com sucesso! Você possui 90 dias de garantia. Obrigado pela confiança!',
        'sent_at': datetime.now().isoformat()
    })
    
    save_repair(repair_id, repair)
    return jsonify({'success': True})

@app.route('/admin/suppliers', methods=['GET'])
@login_required
def admin_suppliers():
    """Página principal para gerenciar Fornecedores"""
    suppliers = get_all_suppliers()
    return render_template('admin/suppliers.html', suppliers=suppliers)

@app.route('/admin/suppliers/new', methods=['GET', 'POST'])
@login_required
def admin_new_supplier():
    """Criar novo fornecedor"""
    from datetime import datetime
    import uuid
    
    if request.method == 'POST':
        supplier_id = str(uuid.uuid4())[:8]
        
        supplier = {
            'id': supplier_id,
            'name': request.form.get('name', ''),
            'cnpj': request.form.get('cnpj', ''),
            'phone': request.form.get('phone', ''),
            'email': request.form.get('email', ''),
            'address': request.form.get('address', ''),
            'description': request.form.get('description', ''),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        save_supplier(supplier_id, supplier)
        return redirect(url_for('admin_suppliers'))
    
    return render_template('admin/new_supplier.html')

@app.route('/admin/suppliers/<supplier_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_supplier(supplier_id):
    """Editar fornecedor"""
    from datetime import datetime
    
    supplier = db_get_supplier(supplier_id)
    if not supplier:
        return redirect(url_for('admin_suppliers'))
    
    if request.method == 'POST':
        supplier['name'] = request.form.get('name', '')
        supplier['cnpj'] = request.form.get('cnpj', '')
        supplier['phone'] = request.form.get('phone', '')
        supplier['email'] = request.form.get('email', '')
        supplier['address'] = request.form.get('address', '')
        supplier['description'] = request.form.get('description', '')
        supplier['updated_at'] = datetime.now().isoformat()
        
        save_supplier(supplier_id, supplier)
        return redirect(url_for('admin_suppliers'))
    
    return render_template('admin/edit_supplier.html', supplier=supplier)

@app.route('/admin/suppliers/<supplier_id>/delete', methods=['POST'])
@login_required
def admin_delete_supplier(supplier_id):
    """Deletar fornecedor"""
    import json
    
    supplier = db_get_supplier(supplier_id)
    if not supplier:
        return jsonify({'success': False, 'error': 'Fornecedor não encontrado'})
    
    db_delete_supplier(supplier_id)
    return jsonify({'success': True})

@app.route('/admin/suppliers/<supplier_id>', methods=['GET'])
@login_required
def admin_view_supplier(supplier_id):
    """Visualizar detalhes do fornecedor"""
    supplier = db_get_supplier(supplier_id)
    if not supplier:
        return redirect(url_for('admin_suppliers'))
    
    return render_template('admin/view_supplier.html', supplier=supplier)

# ========== ROTAS DE PRODUTOS (LOJA) ==========

@app.route('/admin/products', methods=['GET'])
@login_required
def admin_products():
    """Página principal para gerenciar Produtos da Loja"""
    products = get_all_products()
    return render_template('admin/products.html', products=products)

@app.route('/admin/products/new', methods=['GET', 'POST'])
@login_required
def admin_new_product():
    """Criar novo produto"""
    if request.method == 'POST':
        import uuid
        from datetime import datetime
        import base64
        
        product_id = str(uuid.uuid4())[:8]
        product_data = {
            'id': product_id,
            'title': request.form.get('title', ''),
            'description': request.form.get('description', ''),
            'price': request.form.get('price', '0'),
            'condition': request.form.get('condition', 'novo'),  # novo ou usado
            'sold': False,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'photos': [],
            '_photo_data': {}
        }
        
        # Salvar fotos
        photos_dir = os.path.join('static', 'product_photos')
        if not os.path.exists(photos_dir):
            os.makedirs(photos_dir)
        
        if 'photos' in request.files:
            files = request.files.getlist('photos')
            for file in files:
                if file and file.filename:
                    filename = f"product_{product_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
                    filepath = os.path.join(photos_dir, filename)
                    file.save(filepath)
                    product_data['photos'].append(f"/static/product_photos/{filename}")
                    # Salvar também como base64 no banco
                    file.seek(0)
                    file_data = file.read()
                    product_data['_photo_data'][filename] = base64.b64encode(file_data).decode('utf-8')
        
        save_product(product_id, product_data)
        return redirect(url_for('admin_products'))
    
    return render_template('admin/new_product.html')

@app.route('/admin/products/<product_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_product(product_id):
    """Editar produto existente"""
    product = db_get_product(product_id)
    if not product:
        return redirect(url_for('admin_products'))
    
    if request.method == 'POST':
        from datetime import datetime
        import base64
        
        product['title'] = request.form.get('title', '')
        product['description'] = request.form.get('description', '')
        product['price'] = request.form.get('price', '0')
        product['condition'] = request.form.get('condition', 'novo')
        product['updated_at'] = datetime.now().isoformat()
        
        # Adicionar novas fotos
        if 'photos' in request.files:
            photos_dir = os.path.join('static', 'product_photos')
            if not os.path.exists(photos_dir):
                os.makedirs(photos_dir)
            
            if '_photo_data' not in product:
                product['_photo_data'] = {}
            
            files = request.files.getlist('photos')
            for file in files:
                if file and file.filename:
                    filename = f"product_{product_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
                    filepath = os.path.join(photos_dir, filename)
                    file.save(filepath)
                    product['photos'].append(f"/static/product_photos/{filename}")
                    # Salvar também como base64 no banco
                    file.seek(0)
                    file_data = file.read()
                    product['_photo_data'][filename] = base64.b64encode(file_data).decode('utf-8')
        
        save_product(product_id, product)
        return redirect(url_for('admin_products'))
    
    return render_template('admin/edit_product.html', product=product)

@app.route('/admin/products/<product_id>', methods=['GET'])
@login_required
def admin_view_product(product_id):
    """Visualizar detalhes de um produto"""
    product = db_get_product(product_id)
    if not product:
        return redirect(url_for('admin_products'))
    
    return render_template('admin/view_product.html', product=product)

@app.route('/admin/products/<product_id>/delete', methods=['POST'])
@login_required
def admin_delete_product(product_id):
    """Deletar produto"""
    if request.method == 'POST':
        try:
            db_delete_product(product_id)
            return jsonify({'success': True})
        except Exception as e:
            print(f"Erro ao deletar produto {product_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': 'Método não permitido'}), 405

@app.route('/admin/products/<product_id>/sold', methods=['POST'])
@login_required
def admin_mark_product_sold(product_id):
    """Marcar produto como vendido"""
    if request.method == 'POST':
        from datetime import datetime
        product = db_get_product(product_id)
        if product:
            product['sold'] = True
            product['sold_at'] = datetime.now().isoformat()
            product['updated_at'] = datetime.now().isoformat()
            save_product(product_id, product)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Produto não encontrado'}), 404
    return jsonify({'success': False, 'error': 'Método não permitido'}), 405

# ========== ROTAS DE BRANDS ==========

@app.route('/admin/brands')
@login_required
def admin_brands():
    """Listar todas as marcas"""
    brands = get_all_brands()
    return render_template('admin/brands.html', brands=brands)

@app.route('/admin/brands/new', methods=['GET', 'POST'])
@login_required
def admin_new_brand():
    """Criar nova marca"""
    if request.method == 'POST':
        from datetime import datetime
        import uuid
        import base64
        from PIL import Image
        from io import BytesIO
        
        brand_id = str(uuid.uuid4())[:8]
        brand_data = {
            'id': brand_id,
            'name': request.form.get('name', ''),
            'image': '',
            '_image_data': None,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Salvar imagem como base64 com otimização
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                try:
                    # Abrir e otimizar imagem
                    img = Image.open(file)
                    
                    # Converter para RGB se necessário (remove transparência para JPEG)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Redimensionar se muito grande (max 400px de largura ou altura)
                    max_size = 400
                    if img.width > max_size or img.height > max_size:
                        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                    
                    # Comprimir e salvar como JPEG (menor que PNG)
                    output = BytesIO()
                    img.save(output, format='JPEG', quality=85, optimize=True)
                    output.seek(0)
                    
                    # Converter para base64
                    file_data = output.getvalue()
                    brand_data['_image_data'] = base64.b64encode(file_data).decode('utf-8')
                    brand_data['image'] = f"/static/brand_images/{brand_id}.jpg"
                except Exception as e:
                    print(f"Erro ao processar imagem: {e}")
                    # Fallback: salvar sem otimização
                    file.seek(0)
                    file_data = file.read()
                    brand_data['_image_data'] = base64.b64encode(file_data).decode('utf-8')
                    brand_data['image'] = f"/static/brand_images/{brand_id}_{file.filename}"
        
        save_brand(brand_id, brand_data)
        return redirect(url_for('admin_brands'))
    
    return render_template('admin/new_brand.html')

@app.route('/admin/brands/<brand_id>/delete', methods=['POST'])
@login_required
def admin_delete_brand(brand_id):
    """Deletar marca"""
    if request.method == 'POST':
        try:
            db_delete_brand(brand_id)
            return jsonify({'success': True})
        except Exception as e:
            print(f"Erro ao deletar marca {brand_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': 'Método não permitido'}), 405

@app.route('/static/brand_images/<path:filename>')
def serve_brand_image(filename):
    """Serve imagens de marcas do banco de dados com cache otimizado"""
    import base64
    from flask import Response
    from datetime import datetime, timedelta
    
    brands = get_all_brands()
    for brand in brands:
        image_path = brand.get('image', '')
        if isinstance(image_path, str) and filename in image_path:
            image_data = brand.get('_image_data')
            if image_data:
                try:
                    img_data = base64.b64decode(image_data)
                    mimetype = 'image/jpeg'  # Sempre JPEG após otimização
                    if filename.lower().endswith('.png'):
                        mimetype = 'image/png'
                    
                    # Headers de cache para performance
                    expires = datetime.now() + timedelta(days=365)  # Cache por 1 ano
                    response = Response(img_data, mimetype=mimetype)
                    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
                    response.headers['Expires'] = expires.strftime('%a, %d %b %Y %H:%M:%S GMT')
                    response.headers['ETag'] = f'"{brand.get("id", "")}"'
                    return response
                except Exception as e:
                    print(f"Erro ao decodificar imagem de marca {filename}: {e}")
                    continue
    
    return "Imagem de marca não encontrada", 404

# ========== ROTAS PÚBLICAS DA LOJA ==========

@app.route('/loja', methods=['GET'])
def public_shop():
    """Página pública da loja"""
    products = get_all_products()
    # Filtrar apenas produtos não vendidos
    available_products = [p for p in products if not p.get('sold', False)]
    return render_template('shop.html', products=available_products)

@app.route('/loja/<product_id>', methods=['GET'])
def public_product(product_id):
    """Página pública de detalhes do produto"""
    product = db_get_product(product_id)
    if not product:
        return redirect(url_for('public_shop'))
    
    # Buscar WhatsApp do admin
    from db import get_site_content as db_get_site_content
    site_content = db_get_site_content()
    contact = site_content.get('contact', {})
    whatsapp = contact.get('whatsapp', '')
    
    return render_template('product.html', product=product, whatsapp=whatsapp)















@app.route('/admin/repairs/<repair_id>/delete', methods=['POST'])
@login_required
def admin_delete_repair(repair_id):
    import json
    import os
    
    repair_to_delete = db_get_repair(repair_id)
    if not repair_to_delete:
        return jsonify({'success': False, 'error': 'Reparo não encontrado'})
    
    # Remover assinatura se existir
    if repair_to_delete.get('signature') and repair_to_delete['signature'].get('image'):
        signature_path = repair_to_delete['signature']['image'].replace('/static/', '')
        if os.path.exists(signature_path):
            try:
                os.remove(signature_path)
            except:
                pass
    
    # Remover do banco de dados
    db_delete_repair(repair_id)
    
    return jsonify({'success': True})

@app.route('/admin/repairs/<repair_id>/pdf', methods=['GET'])
@login_required
def admin_repair_pdf(repair_id):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib.units import cm
    from io import BytesIO
    import os
    from datetime import datetime
    
    repair = db_get_repair(repair_id)
    if not repair:
        return "Reparo não encontrado", 404
    
    # Criar PDF em memória
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Cabeçalho com logo e informações da empresa (totalmente centralizado)
    logo_path = os.path.join('static', 'images', 'logopdf.png')
    
    # Logo (se existir) - mantendo proporção original
    logo_img = None
    if os.path.exists(logo_path):
        try:
            from PIL import Image as PILImage
            # Obter dimensões reais da imagem para manter proporção
            pil_img = PILImage.open(logo_path)
            img_width, img_height = pil_img.size
            aspect_ratio = img_width / img_height
            
            # Definir altura máxima e calcular largura proporcional
            max_height = 2.5*cm
            logo_width = max_height * aspect_ratio
            # Limitar largura máxima
            if logo_width > 4.5*cm:
                logo_width = 4.5*cm
                max_height = logo_width / aspect_ratio
            
            logo_img = Image(logo_path, width=logo_width, height=max_height)
        except Exception as e:
            print(f"Erro ao carregar logo: {e}")
            logo_img = None
    
    # Informações da empresa (centralizadas)
    company_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontSize=12,
        alignment=1,  # Center
        spaceAfter=6
    )
    
    company_info = Paragraph(
        f"<b>Clínica CELL</b><br/>"
        f"CNPJ: 62.891.287/0001-44<br/>"
        f"www.clinicadomobile.com.br",
        company_style
    )
    
    # Criar tabela centralizada na página
    page_width = A4[0] - 4*cm  # Largura disponível (A4 - margens)
    
    if logo_img:
        # Tabela com logo e texto lado a lado, centralizada
        header_data = [[logo_img, company_info]]
        header_table = Table(header_data, colWidths=[5*cm, 11*cm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        # Wrapper para centralizar na página
        wrapper_data = [[header_table]]
        wrapper_table = Table(wrapper_data, colWidths=[page_width])
        wrapper_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(wrapper_table)
    else:
        # Apenas texto centralizado se não houver logo
        story.append(company_info)
    
    story.append(Spacer(1, 0.8*cm))
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#FF8C00'),
        spaceAfter=30,
        alignment=1  # Center
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#FF8C00'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Estilos para informações profissionais
    info_label_style = ParagraphStyle(
        'InfoLabel',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        spaceAfter=4,
        fontName='Helvetica'
    )
    
    info_value_style = ParagraphStyle(
        'InfoValue',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        spaceAfter=14,
        fontName='Helvetica-Bold',
        leading=14
    )
    
    # Título
    story.append(Paragraph("ORDEM DE SERVIÇO - OS", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Informações do Reparo - Design Elegante
    story.append(Paragraph("INFORMAÇÕES DO REPARO", heading_style))
    
    repair_id = repair.get('id', 'N/A')
    story.append(Paragraph(f"<b>ID do Reparo:</b> <font color='#FF8C00'>{repair_id}</font>", info_value_style))
    
    status = repair.get('status', 'N/A').replace('_', ' ').title()
    status_color = '#28a745' if status.lower() == 'concluido' else '#FF8C00'
    story.append(Paragraph(f"<b>Status:</b> <font color='{status_color}'>{status}</font>", info_value_style))
    
    created_date = repair.get('created_at', 'N/A')[:10] if repair.get('created_at') else 'N/A'
    story.append(Paragraph(f"<b>Data de Entrada:</b> {created_date}", info_value_style))
    
    updated_date = repair.get('updated_at', 'N/A')[:10] if repair.get('updated_at') else 'N/A'
    story.append(Paragraph(f"<b>Última Atualização:</b> {updated_date}", info_value_style))
    
    if repair.get('completed_at'):
        completed_date = repair.get('completed_at', 'N/A')[:10]
        story.append(Paragraph(f"<b>Data de Conclusão:</b> <font color='#28a745'>{completed_date}</font>", info_value_style))
    
    story.append(Spacer(1, 0.4*cm))
    
    # Informações do Dispositivo - Design Elegante
    story.append(Paragraph("DISPOSITIVO", heading_style))
    
    device_name = repair.get('device_name', 'N/A')
    story.append(Paragraph(f"<b>Nome do Dispositivo:</b> {device_name}", info_value_style))
    
    device_model = repair.get('device_model', 'N/A')
    story.append(Paragraph(f"<b>Modelo:</b> {device_model}", info_value_style))
    
    device_imei = repair.get('device_imei', 'N/A')
    story.append(Paragraph(f"<b>IMEI:</b> <font face='Courier' size='10'>{device_imei}</font>", info_value_style))
    
    if repair.get('problem_description'):
        problem_desc = repair.get('problem_description', 'N/A')
        story.append(Paragraph(f"<b>Descrição do Problema:</b> {problem_desc}", info_value_style))
    
    story.append(Spacer(1, 0.4*cm))
    
    # Informações do Cliente - Design Elegante
    story.append(Paragraph("CLIENTE", heading_style))
    
    customer_name = repair.get('customer_name', 'N/A')
    story.append(Paragraph(f"<b>Nome:</b> {customer_name}", info_value_style))
    
    customer_phone = repair.get('customer_phone', 'N/A')
    story.append(Paragraph(f"<b>Telefone:</b> {customer_phone}", info_value_style))
    
    if repair.get('customer_cpf'):
        # Formatar CPF: XXX.XXX.XXX-XX
        cpf = repair.get('customer_cpf', '')
        if len(cpf) == 11:
            formatted_cpf = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        else:
            formatted_cpf = cpf
        story.append(Paragraph(f"<b>CPF:</b> <font face='Courier' size='11'>{formatted_cpf}</font>", info_value_style))
    
    if repair.get('customer_address'):
        customer_address = repair.get('customer_address', 'N/A')
        story.append(Paragraph(f"<b>Endereço:</b> {customer_address}", info_value_style))
    
    if repair.get('customer_email'):
        customer_email = repair.get('customer_email', 'N/A')
        story.append(Paragraph(f"<b>E-mail:</b> <font color='#0066CC'>{customer_email}</font>", info_value_style))
    
    story.append(Spacer(1, 0.4*cm))
    
    # Orçamento - Design Elegante
    if repair.get('budget'):
        story.append(Paragraph("ORÇAMENTO", heading_style))
        
        budget_amount = f"R$ {repair['budget'].get('amount', 0):.2f}"
        story.append(Paragraph(f"<b>Valor:</b> <font size='13' color='#28a745'><b>{budget_amount}</b></font>", info_value_style))
        
        budget_status = repair['budget'].get('status', 'N/A').replace('pending', 'Pendente').replace('approved', 'Aprovado').replace('rejected', 'Rejeitado')
        status_color = '#28a745' if budget_status == 'Aprovado' else '#dc3545' if budget_status == 'Rejeitado' else '#FF8C00'
        story.append(Paragraph(f"<b>Status:</b> <font color='{status_color}'>{budget_status}</font>", info_value_style))
        
        if repair['budget'].get('description'):
            budget_desc = repair['budget'].get('description', 'N/A')
            story.append(Paragraph(f"<b>Descrição:</b> {budget_desc}", info_value_style))
        
        story.append(Spacer(1, 0.4*cm))
        
        # Cláusulas do Contrato
        clause_style = ParagraphStyle(
            'ClauseStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.black,
            spaceAfter=6,
            leading=10,
            alignment=0  # Left alignment
        )
        
        clause_title_style = ParagraphStyle(
            'ClauseTitle',
            parent=styles['Heading3'],
            fontSize=9,
            textColor=colors.HexColor('#FF8C00'),
            spaceAfter=4,
            spaceBefore=8,
            fontName='Helvetica-Bold'
        )
        
        story.append(Paragraph("CLÁUSULAS CONTRATUAIS", heading_style))
        story.append(Spacer(1, 0.2*cm))
        
        story.append(Paragraph("1. DO SINAL E CONDIÇÕES DE PAGAMENTO", clause_title_style))
        story.append(Paragraph("1.1. O cliente declara estar ciente e concorda que 50% (cinquenta por cento) do valor total do serviço deverá ser pago antecipadamente, no ato da abertura da presente Ordem de Serviço.", clause_style))
        story.append(Paragraph("1.2. O valor pago a título de sinal não é reembolsável em caso de desistência do serviço por parte do cliente após o início dos trabalhos.", clause_style))
        story.append(Paragraph("1.3. O saldo remanescente deverá ser quitado integralmente no ato da retirada do aparelho.", clause_style))
        story.append(Spacer(1, 0.2*cm))
        
        story.append(Paragraph("2. DO ESTADO DO APARELHO", clause_title_style))
        story.append(Paragraph("2.1. O cliente declara que entregou o aparelho para análise e/ou reparo ciente de seu estado físico e funcional, incluindo possíveis danos pré-existentes como: Trincas, riscos, amassados; Manchas na tela; Oxidação, umidade ou contato com líquidos; Falhas intermitentes ou ocultas.", clause_style))
        story.append(Paragraph("2.2. A assistência não se responsabiliza por falhas preexistentes que venham a se manifestar durante ou após o reparo.", clause_style))
        story.append(Paragraph("2.3. Em aparelhos que já apresentem sinais de oxidação, queda ou tentativas anteriores de conserto, não há garantia de recuperação total do funcionamento, mesmo após o serviço executado.", clause_style))
        story.append(Spacer(1, 0.2*cm))
        
        story.append(Paragraph("3. DA GARANTIA DO SERVIÇO", clause_title_style))
        story.append(Paragraph("3.1. A garantia refere-se exclusivamente ao serviço executado ou à peça substituída, pelo prazo de 90 dias.", clause_style))
        story.append(Paragraph("3.2. A garantia não cobre: Danos causados por mau uso; Quedas, impactos, líquidos ou sobrecarga elétrica; Atualizações de sistema, vírus ou softwares de terceiros; Defeitos não relacionados diretamente ao serviço realizado.", clause_style))
        story.append(Paragraph("3.3. Qualquer violação de lacres, abertura do aparelho por terceiros ou nova queda anula automaticamente a garantia.", clause_style))
        story.append(Spacer(1, 0.2*cm))
        
        story.append(Paragraph("4. DA RESPONSABILIDADE SOBRE DADOS", clause_title_style))
        story.append(Paragraph("4.1. A assistência não se responsabiliza por perda de dados, como fotos, contatos, aplicativos ou arquivos.", clause_style))
        story.append(Paragraph("4.2. É de inteira responsabilidade do cliente realizar backup prévio antes da entrega do aparelho.", clause_style))
        story.append(Spacer(1, 0.2*cm))
        
        story.append(Paragraph("5. DO NÃO FUNCIONAMENTO APÓS O REPARO", clause_title_style))
        story.append(Paragraph("5.1. O cliente reconhece que, em alguns casos, o aparelho pode não apresentar recuperação total, devido ao grau de dano, oxidação, desgaste de componentes ou defeitos ocultos.", clause_style))
        story.append(Paragraph("5.2. Nesses casos, o valor referente à análise técnica não será devolvido, bem como o sinal pago.", clause_style))
        story.append(Spacer(1, 0.2*cm))
        
        story.append(Paragraph("6. DO ABANDONO DO APARELHO (CLÁUSULA CRÍTICA)", clause_title_style))
        story.append(Paragraph("6.1. Após a conclusão do serviço ou comunicação de impossibilidade de reparo, o cliente terá o prazo máximo de 90 (noventa) dias corridos para retirar o aparelho.", clause_style))
        story.append(Paragraph("6.2. Após esse prazo, será cobrada taxa de armazenamento no valor de R$ 5,00 (cinco reais) por dia.", clause_style))
        story.append(Paragraph("6.3. Caso o aparelho permaneça abandonado por período superior a 180 dias, a assistência poderá: Destinar o aparelho para descarte; Utilizá-lo para compensação de custos; Ou dar outra destinação legalmente permitida, sem direito a qualquer indenização ao cliente.", clause_style))
        story.append(Spacer(1, 0.2*cm))
        
        story.append(Paragraph("7. DA CIÊNCIA E ACEITE", clause_title_style))
        story.append(Paragraph("7.1. Ao assinar a presente Ordem de Serviço, o cliente declara que leu, compreendeu e concorda integralmente com todas as cláusulas aqui descritas, não cabendo alegação futura de desconhecimento.", clause_style))
        story.append(Spacer(1, 0.4*cm))
    
    # Garantia - Design Elegante
    if repair.get('warranty'):
        story.append(Paragraph("GARANTIA", heading_style))
        
        warranty_period = repair['warranty'].get('period', 'N/A')
        story.append(Paragraph(f"<b>Período:</b> <font color='#28a745'><b>{warranty_period}</b></font>", info_value_style))
        
        warranty_valid = repair['warranty'].get('valid_until', 'N/A')[:10] if repair['warranty'].get('valid_until') else 'N/A'
        story.append(Paragraph(f"<b>Válida até:</b> <font color='#28a745'>{warranty_valid}</font>", info_value_style))
        
        warranty_coverage = repair['warranty'].get('coverage', 'N/A')
        story.append(Paragraph(f"<b>Cobertura:</b> {warranty_coverage}", info_value_style))
        
        story.append(Spacer(1, 0.4*cm))
    
    # Histórico
    if repair.get('history'):
        story.append(Paragraph("HISTÓRICO", heading_style))
        history_data = [['Data/Hora', 'Ação', 'Status']]
        for item in repair.get('history', []):
            history_data.append([
                item.get('timestamp', 'N/A')[:16] if item.get('timestamp') else 'N/A',
                item.get('action', 'N/A'),
                item.get('status', 'N/A').replace('_', ' ').title()
            ])
        
        history_table = Table(history_data, colWidths=[5*cm, 8*cm, 3*cm])
        history_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF8C00')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ]))
        story.append(history_table)
        story.append(Spacer(1, 0.5*cm))
    
    # Mensagens
    if repair.get('messages'):
        story.append(Paragraph("MENSAGENS", heading_style))
        for msg in repair.get('messages', []):
            msg_text = f"<b>{msg.get('type', 'N/A').title()}</b> - {msg.get('sent_at', 'N/A')[:16] if msg.get('sent_at') else 'N/A'}<br/>{msg.get('content', 'N/A')}"
            story.append(Paragraph(msg_text, styles['Normal']))
            story.append(Spacer(1, 0.3*cm))
    
    

    # Assinaturas Físicas
    story.append(Spacer(1, 0.5*cm))
    
    signature_line_style = ParagraphStyle(
        'SignatureLine',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=4,
        leading=11,
        alignment=1  # Centralizado
    )
    
    # Linha de assinatura do cliente (física)
    customer_line = Table([['']], colWidths=[7*cm])
    customer_line.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    # Linha de assinatura do técnico (física)
    tech_line = Table([['']], colWidths=[7*cm])
    tech_line.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    # Tabela para colocar as assinaturas lado a lado
    sigs_data = [
        [Paragraph("ASSINATURA DO CLIENTE", signature_line_style), Paragraph("ASSINATURA DO TÉCNICO", signature_line_style)],
        [customer_line, tech_line],
        [Paragraph(f"<b>{repair.get('customer_name', 'Cliente')}</b>", signature_line_style), Paragraph("<b>Técnico Responsável</b>", signature_line_style)]
    ]
    
    sigs_table = Table(sigs_data, colWidths=[9*cm, 9*cm])
    sigs_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(sigs_table)
    
    # Rodapé
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(f"<i>Documento gerado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</i>", styles['Normal']))
    
    # Construir PDF
    doc.build(story)
    buffer.seek(0)
    
    from flask import Response
    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename=reparo_{repair_id}_{datetime.now().strftime("%Y%m%d")}.pdf'
        }
    )

@app.route('/static/product_photos/<path:filename>')
def serve_product_photo(filename):
    """Serve fotos de produtos do banco de dados"""
    import base64
    from flask import Response
    
    # Buscar em todos os produtos
    products = get_all_products()
    
    for product in products:
        photos = product.get('photos', [])
        for photo_path in photos:
            if isinstance(photo_path, str) and filename in photo_path:
                # Verificar se há dados base64 salvos
                photo_data = product.get('_photo_data', {})
                if photo_data:
                    for stored_filename, stored_data in photo_data.items():
                        if filename in stored_filename or stored_filename in filename:
                            try:
                                img_data = base64.b64decode(stored_data)
                                # Detectar tipo MIME
                                mimetype = 'image/png'
                                if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                                    mimetype = 'image/jpeg'
                                elif filename.lower().endswith('.png'):
                                    mimetype = 'image/png'
                                return Response(img_data, mimetype=mimetype)
                            except Exception as e:
                                print(f"Erro ao decodificar imagem {filename}: {e}")
    
    # Se não encontrou no banco, tentar do disco (fallback)
    photo_path = os.path.join('static', 'product_photos', filename)
    if os.path.exists(photo_path):
        try:
            with open(photo_path, 'rb') as f:
                img_data = f.read()
                mimetype = 'image/png'
                if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                    mimetype = 'image/jpeg'
                return Response(img_data, mimetype=mimetype)
        except Exception as e:
            print(f"Erro ao ler arquivo {photo_path}: {e}")
    
    return "Imagem não encontrada", 404

# Rota para servir vídeos com streaming adequado (evita timeout)
@app.route('/static/videos/<path:filename>')
def serve_video(filename):
    """Serve vídeos com range requests para streaming adequado e eficiente"""
    from flask import Response, request
    import os
    
    video_path = os.path.join('static', 'videos', filename)
    if not os.path.exists(video_path):
        return "Vídeo não encontrado", 404
    
    file_size = os.path.getsize(video_path)
    
    # Suportar range requests para streaming
    range_header = request.headers.get('Range', None)
    
    if not range_header:
        # Se não há range request, retornar apenas headers para o navegador fazer range request
        return Response(
            status=200,
            mimetype='video/mp4',
            headers={
                'Accept-Ranges': 'bytes',
                'Content-Length': str(file_size),
                'Content-Type': 'video/mp4'
            }
        )
    
    # Processar range request
    try:
        byte_start = 0
        byte_end = file_size - 1
        
        # Parse do range header (ex: "bytes=0-1023")
        range_match = range_header.replace('bytes=', '').split('-')
        if range_match[0]:
            byte_start = int(range_match[0])
        if len(range_match) > 1 and range_match[1]:
            byte_end = int(range_match[1])
        else:
            # Se não especificou fim, servir até o final
            byte_end = file_size - 1
        
        # Limitar chunk size para evitar carregar muito na memória
        max_chunk_size = 10 * 1024 * 1024  # 10MB por chunk
        content_length = min(byte_end - byte_start + 1, max_chunk_size)
        byte_end = byte_start + content_length - 1
        
        # Usar generator para streaming eficiente
        def generate():
            with open(video_path, 'rb') as f:
                f.seek(byte_start)
                remaining = content_length
                chunk_size = 1024 * 1024  # 1MB chunks
                while remaining > 0:
                    read_size = min(chunk_size, remaining)
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        
        return Response(
            generate(),
            status=206,  # Partial Content
            mimetype='video/mp4',
            headers={
                'Content-Range': f'bytes {byte_start}-{byte_end}/{file_size}',
                'Accept-Ranges': 'bytes',
                'Content-Length': str(content_length),
                'Content-Type': 'video/mp4'
            }
        )
    except Exception as e:
        print(f"Erro ao processar range request para {filename}: {e}")
        import traceback
        traceback.print_exc()
        return "Erro ao processar vídeo", 500

# Rota para sitemap.xml (SEO)
@app.route('/sitemap.xml')
def sitemap():
    """Gera sitemap.xml para SEO"""
    from flask import Response
    import xml.etree.ElementTree as ET
    
    url_root = request.url_root.rstrip('/')
    
    urlset = ET.Element('urlset')
    urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    
    # Página principal
    url = ET.SubElement(urlset, 'url')
    ET.SubElement(url, 'loc').text = url_root
    ET.SubElement(url, 'changefreq').text = 'daily'
    ET.SubElement(url, 'priority').text = '1.0'
    
    # Loja
    url = ET.SubElement(urlset, 'url')
    ET.SubElement(url, 'loc').text = f'{url_root}/loja'
    ET.SubElement(url, 'changefreq').text = 'daily'
    ET.SubElement(url, 'priority').text = '0.8'
    
    # Produtos
    products = get_all_products()
    for product in products:
        if not product.get('sold', False):
            url = ET.SubElement(urlset, 'url')
            ET.SubElement(url, 'loc').text = f'{url_root}/loja/{product.get("id")}'
            ET.SubElement(url, 'changefreq').text = 'weekly'
            ET.SubElement(url, 'priority').text = '0.7'
    
    xml_str = ET.tostring(urlset, encoding='utf-8', method='xml').decode('utf-8')
    return Response(xml_str, mimetype='application/xml')

# Rota para robots.txt (SEO)
@app.route('/robots.txt')
def robots():
    """Gera robots.txt para SEO"""
    from flask import Response
    url_root = request.url_root.rstrip('/')
    robots_content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /status/
Disallow: /repairs

Sitemap: {url_root}/sitemap.xml
"""
    return Response(robots_content, mimetype='text/plain')

# API: Status do negócio (aberto/fechado)
@app.route('/api/business-status', methods=['GET'])
def api_business_status():
    """Retorna o status atual do negócio (aberto ou fechado)"""
    try:
        is_open = db_is_business_open()
        business_hours = get_business_hours()
        from datetime import datetime, timedelta
        
        # Usar timezone do Brasil (UTC-3)
        now_utc = datetime.utcnow()
        now = now_utc - timedelta(hours=3)
        current_day = now.weekday()
        days_map = {0: 'monday', 1: 'tuesday', 2: 'wednesday', 3: 'thursday', 4: 'friday', 5: 'saturday', 6: 'sunday'}
        day_name = days_map[current_day]
        day_config = business_hours.get(day_name, {})
        
        return jsonify({
            'success': True,
            'is_open': is_open,
            'debug': {
                'current_time_utc': datetime.utcnow().strftime('%H:%M'),
                'current_time_brasil': now.strftime('%H:%M'),
                'current_day': day_name,
                'day_config': day_config,
                'business_hours': business_hours
            }
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
