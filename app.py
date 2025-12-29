from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import json
import os
from functools import wraps
from db import (
    create_tables,
    load_config,
    save_config,
    get_site_content as db_get_site_content,
    save_site_content_section,
    get_admin_password,
    save_admin_password,
    get_all_repairs,
    get_repair as db_get_repair,
    save_repair,
    delete_repair as db_delete_repair,
    get_all_checklists,
    get_checklist as db_get_checklist,
    get_checklists_by_repair,
    save_checklist,
    delete_checklist as db_delete_checklist,
    get_all_orders,
    get_order as db_get_order,
    get_order_by_repair,
    save_order,
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
    get_customer_password_hash,
    save_customer_password,
    get_repairs_by_cpf,
    get_all_budget_requests,
    save_budget_request,
    delete_budget_request,
    save_push_token,
    get_push_tokens_by_cpf,
    save_pending_notification,
    get_pending_notifications,
    mark_notification_sent,
    get_all_admin_users,
    get_admin_user,
    save_admin_user,
    delete_admin_user,
    get_all_technicians,
    get_technician,
    save_technician,
    delete_technician
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
    return render_template('index.html', content=site_content, brands=brands)

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
    
    # Calcular alertas de aparelhos abandonados para mostrar no dashboard
    repairs = get_all_repairs()
    abandoned_count = 0
    critical_count = 0
    
    now = datetime.now()
    for repair in repairs:
        if repair.get('status') != 'concluido' or repair.get('order_id'):
            continue
        
        completed_at = repair.get('completed_at') or repair.get('created_at')
        if completed_at:
            try:
                completed_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                if completed_date.tzinfo is None:
                    completed_date = completed_date.replace(tzinfo=None)
                days_since = (now - completed_date.replace(tzinfo=None)).days
                if days_since >= 55:
                    abandoned_count += 1
                    if days_since >= 60:
                        critical_count += 1
            except:
                pass
    
    # Contar solicitações de orçamento pendentes
    budget_requests = get_all_budget_requests()
    pending_budget_count = len([r for r in budget_requests if r.get('status') == 'pendente'])
    
    return render_template('admin/dashboard.html', 
                         abandoned_count=abandoned_count, 
                         critical_count=critical_count,
                         pending_budget_count=pending_budget_count)

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
            orders = get_all_orders()
            checklists = get_all_checklists()
            
            # Buscar reparos pelo CPF
            matching_repairs = []
            for repair in repairs:
                repair_cpf = repair.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
                if repair_cpf == cpf_clean:
                    matching_repairs.append(repair)
            
            # Buscar ORs relacionadas aos reparos encontrados
            matching_orders = []
            repair_ids = [r.get('id') for r in matching_repairs]
            for order in orders:
                if order.get('repair_id') in repair_ids:
                    matching_orders.append(order)
            
            # Buscar checklists relacionados aos reparos encontrados
            matching_checklists = []
            for checklist in checklists:
                checklist_repair_id = checklist.get('repair_id')
                if checklist_repair_id in repair_ids:
                    matching_checklists.append(checklist)
                # Também verificar se está na lista de checklists do reparo
                for repair in matching_repairs:
                    repair_checklist_ids = repair.get('checklists', [])
                    if checklist.get('id') in repair_checklist_ids:
                        if checklist not in matching_checklists:
                            matching_checklists.append(checklist)
            
            search_results = {
                'repairs': matching_repairs,
                'orders': matching_orders,
                'checklists': matching_checklists
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

@app.route('/admin/contact', methods=['GET', 'POST'])
@login_required
def admin_contact():
    site_content = db_get_site_content()
    contact = site_content.get('contact', {})
    
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
        
        return redirect(url_for('admin_contact'))
    
    return render_template('admin/contact.html', contact=contact)

@app.route('/admin/password', methods=['GET', 'POST'])
@login_required
def admin_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        save_admin_password(new_password)
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/password.html')

@app.route('/admin/checklist', methods=['GET', 'POST'])
@login_required
def admin_checklist():
    import base64
    import os
    import uuid
    from datetime import datetime
    
    if request.method == 'POST':
        checklist_type = request.form.get('checklist_type', 'inicial')  # inicial ou conclusao
        repair_id = request.form.get('repair_id', '').strip()
        
        # Validar se o reparo foi informado (obrigatório)
        if not repair_id:
            return "É obrigatório associar o checklist a um reparo para poder emitir a Ordem de Retirada (OR).", 400
        
        # Criar pasta para fotos se não existir
        photos_dir = os.path.join('static', 'checklist_photos')
        if not os.path.exists(photos_dir):
            os.makedirs(photos_dir)
        
        checklist_id = str(uuid.uuid4())[:8]
        checklist_data = {
            'id': checklist_id,
            'type': checklist_type,
            'repair_id': repair_id,
            'timestamp': datetime.now().isoformat(),
            'photos': {},
            'tests': {},
            'signature': None
        }
        
        # Salvar fotos
        photo_fields = ['imei_photo', 'placa_photo', 'conectores_photo']
        if '_photo_data' not in checklist_data:
            checklist_data['_photo_data'] = {}
        for field in photo_fields:
            if field in request.files:
                file = request.files[field]
                if file and file.filename:
                    filename = f"{field}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
                    filepath = os.path.join(photos_dir, filename)
                    file.save(filepath)
                    checklist_data['photos'][field] = f"/static/checklist_photos/{filename}"
                    # Salvar também como base64 no banco (para persistência no Render)
                    # Usar o campo como chave para garantir que cada foto seja única
                    file.seek(0)  # Resetar posição do arquivo
                    file_data = file.read()
                    # Salvar usando o campo como chave para garantir unicidade
                    checklist_data['_photo_data'][field] = base64.b64encode(file_data).decode('utf-8')
                    # Também salvar pelo filename para compatibilidade
                    checklist_data['_photo_data'][filename] = base64.b64encode(file_data).decode('utf-8')
        
        # Salvar testes - para conclusão, só test_after
        if checklist_type == 'conclusao':
            test_fields = [
                'test_after_screen', 'test_after_touch', 'test_after_camera',
                'test_after_battery', 'test_after_audio', 'test_after_buttons'
            ]
        else:
            test_fields = [
                'test_before_screen', 'test_before_touch', 'test_before_camera',
                'test_before_battery', 'test_before_audio', 'test_before_buttons',
                'test_after_screen', 'test_after_touch', 'test_after_camera',
                'test_after_battery', 'test_after_audio', 'test_after_buttons'
            ]
        
        for field in test_fields:
            checklist_data['tests'][field] = field in request.form
        
        # Assinatura será feita pelo cliente no link de acompanhamento, não no admin
        
        # Salvar checklist diretamente no banco de dados
        save_checklist(checklist_id, checklist_data)
        
        # Associar checklist ao reparo
        repair = db_get_repair(repair_id)
        if repair:
            if 'checklists' not in repair:
                repair['checklists'] = []
            if checklist_id not in repair['checklists']:
                repair['checklists'].append(checklist_id)
            
            # Se for checklist de conclusão, marcar como conclusão
            if checklist_type == 'conclusao':
                repair['conclusion_checklist_id'] = checklist_id
            # Se for checklist inicial, marcar como inicial
            elif checklist_type == 'inicial':
                repair['initial_checklist_id'] = checklist_id
            
            save_repair(repair_id, repair)
        
        if repair_id:
            return redirect(url_for('admin_repairs'))
        else:
            return redirect(url_for('admin_checklist'))
    
    # GET - mostrar checklist
    checklists = get_all_checklists()
    repairs = get_all_repairs()
    
    return render_template('admin/checklist.html', checklists=checklists, repairs=repairs)

@app.route('/admin/checklist/<checklist_id>/delete', methods=['POST'])
@login_required
def admin_delete_checklist(checklist_id):
    import json
    import os
    
    checklist_to_delete = db_get_checklist(checklist_id)
    
    if not checklist_to_delete:
        return jsonify({'success': False, 'error': 'Checklist não encontrado'})
    
    # Remover fotos do checklist
    if checklist_to_delete.get('photos'):
        photos = checklist_to_delete.get('photos', {})
        for photo_field, photo_path in photos.items():
            if photo_path:
                photo_file = photo_path.replace('/static/', '')
                if not photo_file.startswith('static/'):
                    photo_file = 'static/' + photo_file.lstrip('/')
                if os.path.exists(photo_file):
                    try:
                        os.remove(photo_file)
                    except:
                        pass
    
    # Remover assinatura do checklist
    if checklist_to_delete.get('signature'):
        signature_path = checklist_to_delete['signature']
        if signature_path.startswith('/static/'):
            signature_path = signature_path[1:]
        elif not signature_path.startswith('static/'):
            signature_path = 'static/' + signature_path.lstrip('/')
        if os.path.exists(signature_path):
            try:
                os.remove(signature_path)
            except:
                pass
    
    # Remover referência do checklist no reparo
    repair_id = checklist_to_delete.get('repair_id')
    if repair_id:
        repair = db_get_repair(repair_id)
        if repair:
            # Remover ID do checklist da lista do reparo
            if 'checklists' in repair:
                if checklist_id in repair['checklists']:
                    repair['checklists'].remove(checklist_id)
            
            # Remover referências específicas
            if repair.get('conclusion_checklist_id') == checklist_id:
                repair.pop('conclusion_checklist_id', None)
            if repair.get('initial_checklist_id') == checklist_id:
                repair.pop('initial_checklist_id', None)
            
            save_repair(repair_id, repair)
    
    # Remover checklist do banco
    db_delete_checklist(checklist_id)
    
    return jsonify({'success': True})

# ========== CENTRAL DE STATUS DO REPARO ==========

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
    from db import get_financial_data
    from datetime import datetime, timedelta
    
    # Obter parâmetros de data
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    # Se não houver datas, usar últimos 30 dias
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Buscar dados financeiros
    financial_data = get_financial_data(start_date, end_date)
    
    return render_template('admin/financeiro.html', 
                         financial_data=financial_data,
                         start_date=start_date,
                         end_date=end_date)

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

@app.route('/admin/budget-requests/<request_id>/delete', methods=['POST'])
@login_required
def admin_delete_budget_request(request_id):
    """Exclui uma solicitação de orçamento"""
    try:
        delete_budget_request(request_id)
        return jsonify({'success': True, 'message': 'Solicitação excluída com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/repairs', methods=['GET'])
@login_required
def admin_repairs():
    repairs = get_all_repairs()
    # Ordenar por data mais recente
    repairs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Adicionar score de risco para cada reparo
    from db import calculate_customer_risk_score
    repairs_with_score = []
    for repair in repairs:
        repair_copy = repair.copy()
        cpf = repair.get('customer_cpf', '')
        if cpf:
            risk_score = calculate_customer_risk_score(cpf)
            repair_copy['risk_score'] = risk_score
        repairs_with_score.append(repair_copy)
    
    return render_template('admin/repairs.html', repairs=repairs_with_score)

@app.route('/admin/repairs/new', methods=['GET', 'POST'])
@login_required
def admin_new_repair():
    from datetime import datetime
    import uuid
    
    if request.method == 'POST':
        repair_id = str(uuid.uuid4())[:8]
        
        repair_type = request.form.get('repair_type', 'novo')  # 'novo' ou 'retorno'
        
        repair = {
            'id': repair_id,
            'repair_type': repair_type,  # 'novo' ou 'retorno'
            'device_name': request.form.get('device_name', ''),
            'device_model': request.form.get('device_model', ''),
            'device_imei': request.form.get('device_imei', ''),
            'problem_description': request.form.get('problem_description', ''),
            'customer_name': request.form.get('customer_name', ''),
            'customer_phone': request.form.get('customer_phone', ''),
            'customer_cpf': request.form.get('customer_cpf', ''),
            'customer_address': request.form.get('customer_address', ''),
            'customer_email': request.form.get('customer_email', ''),
            'status': 'aguardando',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'budget': None,
            'messages': [],
            'history': [{
                'timestamp': datetime.now().isoformat(),
                'action': f'Reparo {"novo" if repair_type == "novo" else "de retorno"} criado',
                'status': 'aguardando'
            }]
        }
        
        # Adicionar orçamento se fornecido
        budget_amount = request.form.get('budget_amount', '')
        if budget_amount:
            repair['budget'] = {
                'amount': float(budget_amount),
                'description': request.form.get('budget_description', ''),
                'status': 'pending'
            }
            repair['status'] = 'orcamento'
            repair['history'].append({
                'timestamp': datetime.now().isoformat(),
                'action': f'Orçamento criado: R$ {budget_amount}',
                'status': 'orcamento'
            })
        
        # Salvar diretamente no banco de dados
        save_repair(repair_id, repair)
        
        return redirect(url_for('admin_repairs'))
    
    return render_template('admin/new_repair.html')

@app.route('/admin/repairs/<repair_id>/status', methods=['POST'])
@login_required
def admin_update_status(repair_id):
    from datetime import datetime
    import json
    from db import get_push_tokens_by_cpf
    
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
    
    # Salvar notificação pendente sobre mudança de status
    customer_cpf = repair.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
    if customer_cpf:
        try:
            status_labels = {
                'aguardando': '⏳ Aguardando',
                'em_analise': '🔍 Em Análise',
                'orcamento': '💰 Orçamento',
                'aprovado': '✅ Aprovado',
                'em_reparo': '🔧 Em Reparo',
                'concluido': '🎉 Concluído'
            }
            status_label = status_labels.get(new_status, new_status)
            
            # Salvar notificação pendente no banco
            save_pending_notification(
                cpf=customer_cpf,
                repair_id=repair_id,
                notification_type='status',
                title='Status do Reparo Atualizado',
                body=f'Seu reparo agora está: {status_label}',
                data={
                    'type': 'status',
                    'repair_id': repair_id,
                    'status': new_status,
                    'url': f'/mobile_app/?repair={repair_id}',
                    'tag': f'repair-{repair_id}-status'
                }
            )
        except Exception as e:
            print(f"Erro ao salvar notificação pendente: {e}")
    
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

def send_push_notification(cpf, title, body, data=None):
    """Envia notificação push para o cliente usando Web Push API"""
    try:
        from db import get_push_tokens_by_cpf
        tokens = get_push_tokens_by_cpf(cpf)
        
        if not tokens:
            return False
        
        for token_data in tokens:
            subscription = token_data.get('subscription')
            if not subscription:
                continue
            
            try:
                # Web Push API - enviar notificação
                import json as json_lib
                subscription_obj = subscription if isinstance(subscription, dict) else json_lib.loads(subscription)
                
                # Usar Web Push API do navegador (via JavaScript no frontend)
                # Ou usar pywebpush para enviar do backend
                # Por enquanto, vamos usar uma abordagem simples com fetch
                # O service worker vai receber a notificação
                return True
            except Exception as e:
                print(f"Erro ao enviar notificação push: {e}")
                continue
        
        return False
    except Exception as e:
        print(f"Erro ao buscar tokens de push: {e}")
        return False

@app.route('/admin/repairs/<repair_id>/message', methods=['POST'])
@login_required
def admin_send_message(repair_id):
    from datetime import datetime
    import json
    from db import get_push_tokens_by_cpf
    
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
    
    # Salvar notificação pendente
    customer_cpf = repair.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
    if customer_cpf:
        try:
            # Salvar notificação pendente no banco
            save_pending_notification(
                cpf=customer_cpf,
                repair_id=repair_id,
                notification_type='message',
                title='Nova Mensagem - Clínica CEL',
                body=message_content[:100],  # Limitar tamanho
                data={
                    'type': 'message',
                    'repair_id': repair_id,
                    'url': f'/mobile_app/?repair={repair_id}',
                    'tag': f'repair-{repair_id}-message'
                }
            )
        except Exception as e:
            print(f"Erro ao salvar notificação pendente: {e}")
    
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
        repair['updated_at'] = datetime.now().isoformat()
        
        save_repair(repair_id, repair)
        return redirect(url_for('admin_repairs'))
    
    return render_template('admin/edit_repair.html', repair=repair)

# Rota pública para cliente ver status
@app.route('/status/<repair_id>', methods=['GET'])
def public_repair_status(repair_id):
    repair = db_get_repair(repair_id)
    
    # Buscar TODOS os checklists associados a este reparo (com e sem assinatura)
    all_repair_checklists = get_checklists_by_repair(repair_id)
    
    # Checklists que precisam de assinatura (sem assinatura)
    repair_checklists = [cl for cl in all_repair_checklists if not cl.get('signature')]
    
    return render_template('status.html', repair=repair, repair_checklists=repair_checklists, all_repair_checklists=all_repair_checklists)

@app.route('/status/<repair_id>/budget/approve', methods=['POST'])
def public_approve_budget(repair_id):
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
        'action': 'Orçamento aprovado pelo cliente',
        'status': 'aprovado'
    })
    budget_amount = repair['budget'].get('amount') if isinstance(repair['budget'], dict) else repair['budget']
    repair['messages'].append({
        'type': 'budget_approved',
        'content': f'Você aprovou o orçamento de R$ {budget_amount:.2f if isinstance(budget_amount, (int, float)) else budget_amount}. O reparo será iniciado em breve.',
        'sent_at': datetime.now().isoformat()
    })
    save_repair(repair_id, repair)
    return jsonify({'success': True})

# API: Aprovar orçamento (para app mobile)
@app.route('/api/repair/<repair_id>/budget/approve', methods=['POST'])
def api_approve_budget(repair_id):
    """Aprova orçamento via API (app mobile)"""
    from datetime import datetime
    
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        repair = db_get_repair(repair_id)
        if not repair:
            return jsonify({'success': False, 'error': 'Reparo não encontrado'}), 404
        
        # Verificar se o reparo pertence ao CPF
        repair_cpf = repair.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
        if repair_cpf != cpf:
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        if not repair.get('budget'):
            return jsonify({'success': False, 'error': 'Orçamento não encontrado'}), 400
        
        repair['budget']['status'] = 'approved'
        repair['status'] = 'aprovado'
        repair['updated_at'] = datetime.now().isoformat()
        repair['history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': 'Orçamento aprovado pelo cliente',
            'status': 'aprovado'
        })
        budget_amount = repair['budget'].get('amount') if isinstance(repair['budget'], dict) else repair['budget']
        repair['messages'].append({
            'type': 'budget_approved',
            'content': f'Você aprovou o orçamento de R$ {budget_amount:.2f if isinstance(budget_amount, (int, float)) else budget_amount}. O reparo será iniciado em breve.',
            'sent_at': datetime.now().isoformat()
        })
        save_repair(repair_id, repair)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Rejeitar orçamento (para app mobile)
@app.route('/api/repair/<repair_id>/budget/reject', methods=['POST'])
def api_reject_budget(repair_id):
    """Rejeita orçamento via API (app mobile)"""
    from datetime import datetime
    
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        repair = db_get_repair(repair_id)
        if not repair:
            return jsonify({'success': False, 'error': 'Reparo não encontrado'}), 404
        
        # Verificar se o reparo pertence ao CPF
        repair_cpf = repair.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
        if repair_cpf != cpf:
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        if not repair.get('budget'):
            return jsonify({'success': False, 'error': 'Orçamento não encontrado'}), 400
        
        repair['budget']['status'] = 'rejected'
        repair['status'] = 'aguardando'
        repair['updated_at'] = datetime.now().isoformat()
        repair['history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': 'Orçamento rejeitado pelo cliente',
            'status': 'aguardando'
        })
        repair['messages'].append({
            'type': 'budget_rejected',
            'content': 'Você rejeitou o orçamento. Entre em contato conosco para mais informações.',
            'sent_at': datetime.now().isoformat()
        })
        save_repair(repair_id, repair)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Enviar mensagem (para app mobile)
@app.route('/api/repair/<repair_id>/message', methods=['POST'])
def api_send_message(repair_id):
    """Envia mensagem do cliente via API (app mobile)"""
    from datetime import datetime
    
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        message = data.get('message', '').strip()
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        if not message:
            return jsonify({'success': False, 'error': 'Mensagem não pode estar vazia'}), 400
        
        repair = db_get_repair(repair_id)
        if not repair:
            return jsonify({'success': False, 'error': 'Reparo não encontrado'}), 404
        
        # Verificar se o reparo pertence ao CPF
        repair_cpf = repair.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
        if repair_cpf != cpf:
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        if 'messages' not in repair:
            repair['messages'] = []
        
        repair['messages'].append({
            'type': 'customer',
            'content': message,
            'sent_at': datetime.now().isoformat()
        })
        repair['updated_at'] = datetime.now().isoformat()
        save_repair(repair_id, repair)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Assinar checklist (para app mobile)
@app.route('/api/repair/<repair_id>/checklist/<checklist_id>/signature', methods=['POST'])
def api_checklist_signature(repair_id, checklist_id):
    """Salva assinatura do checklist via API (app mobile)"""
    from datetime import datetime
    import base64
    import os
    
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        signature_data = data.get('signature', '')
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        if not signature_data:
            return jsonify({'success': False, 'error': 'Assinatura não fornecida'}), 400
        
        repair = db_get_repair(repair_id)
        if not repair:
            return jsonify({'success': False, 'error': 'Reparo não encontrado'}), 404
        
        # Verificar se o reparo pertence ao CPF
        repair_cpf = repair.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
        if repair_cpf != cpf:
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        checklist = db_get_checklist(checklist_id)
        if not checklist:
            return jsonify({'success': False, 'error': 'Checklist não encontrado'}), 404
        
        if checklist.get('repair_id') != repair_id:
            return jsonify({'success': False, 'error': 'Checklist não pertence a este reparo'}), 400
        
        # Salvar assinatura
        if ',' in signature_data:
            signature_data_clean = signature_data.split(',')[1]
        else:
            signature_data_clean = signature_data
        
        signatures_dir = os.path.join('static', 'signatures')
        if not os.path.exists(signatures_dir):
            os.makedirs(signatures_dir)
        
        signature_filename = f"checklist_signature_{checklist_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        signature_path = os.path.join(signatures_dir, signature_filename)
        
        signature_bytes = base64.b64decode(signature_data_clean)
        with open(signature_path, 'wb') as f:
            f.write(signature_bytes)
        
        checklist['signature'] = f"/static/signatures/{signature_filename}"
        checklist['signature_signed_at'] = datetime.now().isoformat()
        checklist['_signature_data'] = signature_data_clean
        checklist['updated_at'] = datetime.now().isoformat()
        
        save_checklist(checklist_id, checklist)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Assinar orçamento (para app mobile)
@app.route('/api/repair/<repair_id>/signature', methods=['POST'])
def api_repair_signature(repair_id):
    """Salva assinatura do orçamento via API (app mobile)"""
    from datetime import datetime
    import base64
    import os
    
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        signature_data = data.get('signature', '')
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        if not signature_data:
            return jsonify({'success': False, 'error': 'Assinatura não fornecida'}), 400
        
        repair = db_get_repair(repair_id)
        if not repair:
            return jsonify({'success': False, 'error': 'Reparo não encontrado'}), 404
        
        # Verificar se o reparo pertence ao CPF
        repair_cpf = repair.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
        if repair_cpf != cpf:
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        # Salvar assinatura
        if ',' in signature_data:
            signature_data_clean = signature_data.split(',')[1]
        else:
            signature_data_clean = signature_data
        
        signatures_dir = os.path.join('static', 'signatures')
        if not os.path.exists(signatures_dir):
            os.makedirs(signatures_dir)
        
        signature_filename = f"signature_{repair_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        signature_path = os.path.join(signatures_dir, signature_filename)
        
        signature_bytes = base64.b64decode(signature_data_clean)
        with open(signature_path, 'wb') as f:
            f.write(signature_bytes)
        
        repair['signature'] = {
            'image': f"/static/signatures/{signature_filename}",
            'signed_at': datetime.now().isoformat()
        }
        repair['_signature_data'] = signature_data_clean
        repair['updated_at'] = datetime.now().isoformat()
        repair['history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': 'Assinatura digital confirmada pelo cliente',
            'status': repair.get('status', 'aprovado')
        })
        repair['messages'].append({
            'type': 'signature',
            'content': 'Assinatura digital confirmada.',
            'sent_at': datetime.now().isoformat()
        })
        save_repair(repair_id, repair)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Download PDF (para app mobile - redireciona para rota pública)
@app.route('/api/repair/<repair_id>/pdf', methods=['GET'])
def api_download_repair_pdf(repair_id):
    """Redireciona para download do PDF do reparo"""
    return redirect(url_for('public_repair_pdf', repair_id=repair_id))

@app.route('/status/<repair_id>/pdf', methods=['GET'])
def public_repair_pdf(repair_id):
    """Gera PDF do reparo para cliente (público)"""
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
    
    # Cabeçalho com logo
    logo_path = os.path.join('static', 'images', 'logopdf.png')
    logo_img = None
    if os.path.exists(logo_path):
        try:
            from PIL import Image as PILImage
            pil_img = PILImage.open(logo_path)
            img_width, img_height = pil_img.size
            aspect_ratio = img_width / img_height
            max_height = 2.5*cm
            logo_width = max_height * aspect_ratio
            if logo_width > 4.5*cm:
                logo_width = 4.5*cm
                max_height = logo_width / aspect_ratio
            logo_img = Image(logo_path, width=logo_width, height=max_height)
        except Exception as e:
            logo_img = None
    
    company_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontSize=12,
        alignment=1,
        spaceAfter=6
    )
    
    company_info = Paragraph(
        f"<b>Clínica CEL</b><br/>"
        f"CNPJ: 62.891.287/0001-44<br/>"
        f"www.clinicacel.com.br",
        company_style
    )
    
    if logo_img:
        header_data = [[logo_img, company_info]]
        header_table = Table(header_data, colWidths=[5*cm, 11*cm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ]))
        story.append(header_table)
    else:
        story.append(company_info)
    
    story.append(Spacer(1, 0.8*cm))
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#FF8C00'),
        spaceAfter=12,
        alignment=1
    )
    story.append(Paragraph("COMPROVANTE DE REPARO", title_style))
    story.append(Spacer(1, 0.3*cm))
    
    # Informações do reparo
    info_value_style = ParagraphStyle(
        'InfoValue',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=6
    )
    
    story.append(Paragraph(f"<b>ID do Reparo:</b> {repair.get('id', 'N/A')}", info_value_style))
    story.append(Paragraph(f"<b>Dispositivo:</b> {repair.get('device_name', 'N/A')}", info_value_style))
    story.append(Paragraph(f"<b>Modelo:</b> {repair.get('device_model', 'N/A')}", info_value_style))
    story.append(Paragraph(f"<b>Status:</b> {repair.get('status', 'N/A')}", info_value_style))
    if repair.get('problem_description'):
        story.append(Paragraph(f"<b>Problema:</b> {repair.get('problem_description', '')}", info_value_style))
    
    story.append(Spacer(1, 0.5*cm))
    
    # Informações do cliente
    story.append(Paragraph("<b>Informações do Cliente:</b>", info_value_style))
    story.append(Paragraph(f"Nome: {repair.get('customer_name', 'N/A')}", styles['Normal']))
    story.append(Paragraph(f"Telefone: {repair.get('customer_phone', 'N/A')}", styles['Normal']))
    if repair.get('customer_cpf'):
        cpf = repair.get('customer_cpf', '')
        if len(cpf) == 11:
            formatted_cpf = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        else:
            formatted_cpf = cpf
        story.append(Paragraph(f"CPF: {formatted_cpf}", styles['Normal']))
    
    story.append(Spacer(1, 0.5*cm))
    
    # Orçamento
    if repair.get('budget'):
        budget_amount = repair['budget'].get('amount') if isinstance(repair['budget'], dict) else repair['budget']
        story.append(Paragraph(f"<b>Orçamento:</b> R$ {budget_amount:.2f if isinstance(budget_amount, (int, float)) else budget_amount}", info_value_style))
    
    # Construir PDF
    doc.build(story)
    buffer.seek(0)
    
    from flask import Response
    return Response(buffer, mimetype='application/pdf', headers={
        'Content-Disposition': f'inline; filename=reparo_{repair_id}.pdf'
    })

@app.route('/repairs', methods=['GET'])
def public_list_repairs():
    """Lista reparos do cliente por telefone ou email"""
    search_query = request.args.get('search', '').strip()
    
    if not search_query:
        return render_template('repairs_list.html', repairs=None, search_query=None)
    
    repairs = get_all_repairs()
    
    # Filtrar reparos por telefone ou email
    client_repairs = []
    for repair in repairs:
        customer_phone = repair.get('customer_phone', '').strip()
        customer_email = repair.get('customer_email', '').strip()
        
        # Normalizar busca (remover espaços, caracteres especiais)
        search_normalized = search_query.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').lower()
        phone_normalized = customer_phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').lower()
        email_normalized = customer_email.lower()
        
        if search_normalized in phone_normalized or search_normalized in email_normalized:
            client_repairs.append(repair)
    
    # Ordenar por data mais recente
    client_repairs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return render_template('repairs_list.html', repairs=client_repairs, search_query=search_query)

@app.route('/status/<repair_id>/budget/reject', methods=['POST'])
def public_reject_budget(repair_id):
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
        'action': 'Orçamento rejeitado pelo cliente',
        'status': 'aguardando'
    })
    repair['messages'].append({
        'type': 'budget_rejected',
        'content': 'Você rejeitou o orçamento. Entre em contato conosco para mais informações.',
        'sent_at': datetime.now().isoformat()
    })
    save_repair(repair_id, repair)
    return jsonify({'success': True})

@app.route('/status/<repair_id>/checklist/<checklist_id>/signature', methods=['POST'])
def public_save_checklist_signature(repair_id, checklist_id):
    import base64
    import os
    from datetime import datetime
    import json
    
    repair = db_get_repair(repair_id)
    if not repair:
        return jsonify({'success': False, 'error': 'Reparo não encontrado'})
    
    checklist = db_get_checklist(checklist_id)
    if not checklist or checklist.get('repair_id') != repair_id:
        return jsonify({'success': False, 'error': 'Checklist não encontrado'})
    
    data = request.get_json()
    signature_data = data.get('signature', '')
    
    if signature_data:
        # Criar pasta para assinaturas se não existir
        signatures_dir = os.path.join('static', 'checklist_photos')
        if not os.path.exists(signatures_dir):
            os.makedirs(signatures_dir)
        
        if ',' in signature_data:
            signature_data = signature_data.split(',')[1]
        
        signature_filename = f"checklist_signature_{checklist_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        signature_path = os.path.join(signatures_dir, signature_filename)
        
        signature_bytes = base64.b64decode(signature_data)
        with open(signature_path, 'wb') as f:
            f.write(signature_bytes)
        
        checklist['signature'] = f"/static/checklist_photos/{signature_filename}"
        checklist['signature_signed_at'] = datetime.now().isoformat()
        # Salvar também como base64 no banco (para persistência no Render)
        checklist['_signature_data'] = signature_data
        
        # Salvar checklist atualizado
        save_checklist(checklist_id, checklist)
        
        # Atualizar histórico do reparo
        repair['updated_at'] = datetime.now().isoformat()
        repair['history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': f'Assinatura digital do checklist {checklist_id} confirmada pelo cliente',
            'status': repair.get('status', 'aprovado')
        })
        
        repair['messages'].append({
            'type': 'checklist_signature',
            'content': f'Assinatura digital do checklist confirmada. Obrigado pela confiança!',
            'sent_at': datetime.now().isoformat()
        })
        
        save_repair(repair_id, repair)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Assinatura não fornecida'})

@app.route('/status/<repair_id>/signature', methods=['POST'])
def public_save_signature(repair_id):
    from datetime import datetime
    import json
    import base64
    import os
    
    data = request.get_json()
    signature_data = data.get('signature', '')
    
    repair = db_get_repair(repair_id)
    if not repair:
        return jsonify({'success': False, 'error': 'Reparo não encontrado'})
    
    # Criar pasta para assinaturas se não existir
    signatures_dir = os.path.join('static', 'signatures')
    if not os.path.exists(signatures_dir):
        os.makedirs(signatures_dir)
    
    # Salvar imagem da assinatura
    if signature_data:
        if ',' in signature_data:
            signature_data_clean = signature_data.split(',')[1]
        else:
            signature_data_clean = signature_data
        
        signature_filename = f"signature_{repair_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        signature_path = os.path.join(signatures_dir, signature_filename)
        
        signature_bytes = base64.b64decode(signature_data_clean)
        with open(signature_path, 'wb') as f:
            f.write(signature_bytes)
        
        repair['signature'] = {
            'image': f"/static/signatures/{signature_filename}",
            'signed_at': datetime.now().isoformat()
        }
        # Salvar também como base64 no banco (para persistência no Render)
        repair['_signature_data'] = signature_data_clean
        
        repair['updated_at'] = datetime.now().isoformat()
        repair['history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': 'Assinatura digital confirmada pelo cliente',
            'status': repair.get('status', 'aprovado')
        })
        repair['messages'].append({
            'type': 'signature',
            'content': 'Assinatura digital confirmada. O reparo será iniciado em breve.',
            'sent_at': datetime.now().isoformat()
        })
        
        save_repair(repair_id, repair)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Assinatura não fornecida'})

@app.route('/admin/repairs/<repair_id>/complete', methods=['POST'])
@login_required
def admin_complete_repair(repair_id):
    from datetime import datetime, timedelta
    import json
    
    repair = db_get_repair(repair_id)
    if not repair:
        return jsonify({'success': False, 'error': 'Reparo não encontrado'})
    
    repair['status'] = 'concluido'
    repair['completed_at'] = datetime.now().isoformat()
    repair['updated_at'] = datetime.now().isoformat()
    
    # Gerar garantia (90 dias)
    warranty_until = datetime.now() + timedelta(days=90)
    repair['warranty'] = {
        'period': '90 dias',
        'valid_until': warranty_until.isoformat(),
        'coverage': 'Peças e mão de obra'
    }
    
    repair['history'].append({
        'timestamp': datetime.now().isoformat(),
        'action': 'Reparo concluído - Garantia de 90 dias ativada',
        'status': 'concluido'
    })
    repair['messages'].append({
        'type': 'completed',
        'content': 'Seu reparo foi concluído com sucesso! Você possui 90 dias de garantia. Obrigado pela confiança!',
        'sent_at': datetime.now().isoformat()
    })
    
    save_repair(repair_id, repair)
    return jsonify({'success': True})

@app.route('/admin/orders', methods=['GET'])
@login_required
def admin_orders():
    """Página principal para gerenciar Ordens de Retirada"""
    orders = get_all_orders()
    repairs = get_all_repairs()
    checklists = get_all_checklists()
    
    # Enriquecer orders com dados dos reparos e checklists
    enriched_orders = []
    for order in orders:
        repair_id = order.get('repair_id')
        repair = next((r for r in repairs if r.get('id') == repair_id), None)
        
        if repair:
            conclusion_checklist_id = repair.get('conclusion_checklist_id')
            conclusion_checklist = None
            if conclusion_checklist_id:
                conclusion_checklist = next((c for c in checklists if c.get('id') == conclusion_checklist_id), None)
            
            enriched_order = order.copy()
            enriched_order['repair'] = repair
            enriched_order['conclusion_checklist'] = conclusion_checklist
            enriched_orders.append(enriched_order)
    
    # Ordenar por data mais recente
    enriched_orders.sort(key=lambda x: x.get('emitted_at', ''), reverse=True)
    
    # Reparos concluídos que podem ter OR emitida
    completed_repairs = [r for r in repairs if r.get('status') == 'concluido' and not r.get('order_id')]
    available_repairs = []
    for repair in completed_repairs:
        repair_id = repair.get('id')
        repair_checklists = get_checklists_by_repair(repair_id)
        
        # Verificar se existe checklist de conclusão
        conclusion_checklist = None
        for cl in repair_checklists:
            if cl.get('type') == 'conclusao':
                conclusion_checklist = cl
                break
        
        if conclusion_checklist:
            # Verificar se TODAS as assinaturas dos checklists foram feitas
            all_signed = True
            for cl in repair_checklists:
                if not cl.get('signature'):
                    all_signed = False
                    break
            
            # Só adicionar se todas as assinaturas estiverem feitas
            if all_signed:
                available_repairs.append({
                    'repair': repair,
                    'conclusion_checklist': conclusion_checklist
                })
    
    return render_template('admin/orders.html', orders=enriched_orders, available_repairs=available_repairs)

@app.route('/admin/suppliers', methods=['GET'])
@login_required
def admin_suppliers():
    """Página principal para gerenciar Fornecedores"""
    suppliers = get_all_suppliers()
    return render_template('admin/suppliers.html', suppliers=suppliers)

@app.route('/admin/abandoned-alerts', methods=['GET'])
@login_required
def admin_abandoned_alerts():
    """Sistema de alerta de aparelhos abandonados"""
    from datetime import datetime, timedelta
    
    repairs = get_all_repairs()
    alerts = []
    
    # Data atual
    now = datetime.now()
    # 60 dias atrás
    sixty_days_ago = now - timedelta(days=60)
    # 55 dias atrás (5 dias antes de completar 60)
    fifty_five_days_ago = now - timedelta(days=55)
    
    for repair in repairs:
        # Verificar se o reparo está concluído
        if repair.get('status') != 'concluido':
            continue
        
        # Verificar se não tem OR emitida
        if repair.get('order_id'):
            continue
        
        # Verificar data de conclusão
        completed_at = repair.get('completed_at')
        if not completed_at:
            # Se não tem completed_at, usar created_at como fallback
            completed_at = repair.get('created_at')
            if not completed_at:
                continue
        
        try:
            completed_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
            if completed_date.tzinfo is None:
                completed_date = completed_date.replace(tzinfo=None)
            
            # Calcular dias desde a conclusão
            days_since_completion = (now - completed_date.replace(tzinfo=None)).days
            
            # Se passou mais de 55 dias, criar alerta
            if days_since_completion >= 55:
                days_remaining = 60 - days_since_completion
                
                alert_level = 'critical' if days_since_completion >= 60 else 'warning'
                
                alerts.append({
                    'repair': repair,
                    'days_since_completion': days_since_completion,
                    'days_remaining': max(0, days_remaining),
                    'completed_date': completed_date,
                    'alert_level': alert_level
                })
        except Exception as e:
            print(f"Erro ao processar reparo {repair.get('id')}: {e}")
            continue
    
    # Ordenar por dias desde conclusão (mais antigos primeiro)
    alerts.sort(key=lambda x: x['days_since_completion'], reverse=True)
    
    return render_template('admin/abandoned_alerts.html', alerts=alerts)

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

@app.route('/admin/repairs/<repair_id>/checklist/conclusao', methods=['GET', 'POST'])
@login_required
def admin_checklist_conclusao(repair_id):
    import base64
    import os
    import uuid
    from datetime import datetime
    
    repair = db_get_repair(repair_id)
    if not repair:
        return "Reparo não encontrado", 404
    
    # Verificar se o reparo está concluído
    if repair.get('status') != 'concluido':
        return "O reparo precisa estar concluído para realizar o checklist de conclusão", 400
    
    if request.method == 'POST':
        # Criar pasta para fotos se não existir
        photos_dir = os.path.join('static', 'checklist_photos')
        if not os.path.exists(photos_dir):
            os.makedirs(photos_dir)
        
        checklist_id = str(uuid.uuid4())[:8]
        checklist_data = {
            'id': checklist_id,
            'type': 'conclusao',
            'repair_id': repair_id,
            'timestamp': datetime.now().isoformat(),
            'photos': {},
            'tests': {},
            'signature': None
        }
        
        # Salvar fotos (opcional na conclusão)
        photo_fields = ['imei_photo', 'placa_photo', 'conectores_photo']
        if '_photo_data' not in checklist_data:
            checklist_data['_photo_data'] = {}
        for field in photo_fields:
            if field in request.files:
                file = request.files[field]
                if file and file.filename:
                    filename = f"{field}_conclusao_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
                    filepath = os.path.join(photos_dir, filename)
                    file.save(filepath)
                    checklist_data['photos'][field] = f"/static/checklist_photos/{filename}"
                    # Salvar também como base64 no banco (para persistência no Render)
                    file.seek(0)  # Resetar posição do arquivo
                    file_data = file.read()
                    checklist_data['_photo_data'][filename] = base64.b64encode(file_data).decode('utf-8')
        
        # Salvar testes - apenas test_after na conclusão
        test_fields = [
            'test_after_screen', 'test_after_touch', 'test_after_camera',
            'test_after_battery', 'test_after_audio', 'test_after_buttons'
        ]
        for field in test_fields:
            checklist_data['tests'][field] = field in request.form
        
        # Assinatura será feita pelo cliente no link de acompanhamento, não no admin
        
        # Salvar checklist diretamente no banco de dados
        save_checklist(checklist_id, checklist_data)
        
        # Associar ao reparo
        if 'checklists' not in repair:
            repair['checklists'] = []
        if checklist_id not in repair['checklists']:
            repair['checklists'].append(checklist_id)
        repair['conclusion_checklist_id'] = checklist_id
        
        save_repair(repair_id, repair)
        
        return redirect(url_for('admin_repairs'))
    
    # GET - mostrar formulário
    return render_template('admin/checklist_conclusao.html', repair=repair)

@app.route('/admin/repairs/<repair_id>/or', methods=['GET', 'POST'])
@login_required
def admin_emit_or(repair_id):
    from datetime import datetime
    import uuid
    import base64
    import os
    
    repair = db_get_repair(repair_id)
    if not repair:
        return "Reparo não encontrado", 404
    
    # Validações: reparo deve estar concluído e ter checklist de conclusão
    if repair.get('status') != 'concluido':
        return "O reparo precisa estar concluído para emitir a Ordem de Retirada", 400
    
    # Buscar todos os checklists associados ao reparo
    repair_checklists = get_checklists_by_repair(repair_id)
    
    # Verificar se existe checklist de conclusão
    conclusion_checklist = None
    for cl in repair_checklists:
        if cl.get('type') == 'conclusao':
            conclusion_checklist = cl
            break
    
    if not conclusion_checklist:
        return "É necessário realizar o Checklist Antifraude de Conclusão antes de emitir a OR", 400
    
    # Verificar se TODAS as assinaturas dos checklists foram feitas pelo cliente
    unsigned_checklists = []
    for cl in repair_checklists:
        if not cl.get('signature'):
            unsigned_checklists.append(cl)
    
    if unsigned_checklists:
        checklist_types = []
        for cl in unsigned_checklists:
            if cl.get('type') == 'inicial':
                checklist_types.append('Checklist Antifraude Inicial')
            elif cl.get('type') == 'conclusao':
                checklist_types.append('Checklist Antifraude de Conclusão')
        
        return f"Não é possível emitir a OR. Faltam assinaturas do cliente nos seguintes checklists: {', '.join(checklist_types)}. O cliente deve acessar o link de acompanhamento e assinar todos os checklists antes da emissão da OR.", 400
    
    if request.method == 'POST':
        # Criar Ordem de Retirada
        order_id = str(uuid.uuid4())[:8]
        or_data = {
            'id': order_id,
            'repair_id': repair_id,
            'emitted_at': datetime.now().isoformat(),
            'emitted_by': session.get('admin_name', 'Raí Silva'),
            'observations': request.form.get('observations', ''),
            'customer_received': request.form.get('customer_received', '') == 'on'
        }
        
        # Assinaturas digitais são apenas no link do cliente, não na OR
        
        # Salvar OR diretamente no banco de dados
        save_order(order_id, repair_id, or_data)
        
        # Associar OR ao reparo
        repair['order_id'] = order_id
        repair['order_emitted_at'] = or_data['emitted_at']
        save_repair(repair_id, repair)
        
        # Redirecionar para visualizar/baixar a OR
        return redirect(url_for('admin_view_or', repair_id=repair_id))
    
    # GET - mostrar formulário
    # Passar lista de checklists sem assinatura para exibir no template
    # Calcular score de risco do cliente
    from db import calculate_customer_risk_score
    customer_cpf = repair.get('customer_cpf', '')
    risk_score = None
    if customer_cpf:
        risk_score = calculate_customer_risk_score(customer_cpf)
    
    return render_template('admin/emit_or.html', 
                         repair=repair, 
                         conclusion_checklist=conclusion_checklist, 
                         unsigned_checklists=unsigned_checklists,
                         risk_score=risk_score)

@app.route('/admin/repairs/<repair_id>/or/view', methods=['GET'])
@login_required
def admin_view_or(repair_id):
    repair = db_get_repair(repair_id)
    if not repair:
        return "Reparo não encontrado", 404
    
    order_id = repair.get('order_id')
    if not order_id:
        return redirect(url_for('admin_emit_or', repair_id=repair_id))
    
    order = db_get_order(order_id)
    if not order:
        return "Ordem de Retirada não encontrada", 404
    
    return render_template('admin/view_or.html', repair=repair, order=order)

@app.route('/status/<repair_id>/or/pdf', methods=['GET'])
def public_or_pdf(repair_id):
    """Gera PDF da OR para cliente (público)"""
    return admin_or_pdf_internal(repair_id)

@app.route('/admin/repairs/<repair_id>/or/pdf', methods=['GET'])
@login_required
def admin_or_pdf(repair_id):
    """Gera PDF da OR (requer login admin)"""
    return admin_or_pdf_internal(repair_id)

def admin_or_pdf_internal(repair_id):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.units import cm
    from io import BytesIO
    import os
    from datetime import datetime
    
    repair = db_get_repair(repair_id)
    if not repair:
        return "Reparo não encontrado", 404
    
    order_id = repair.get('order_id')
    if not order_id:
        return "Ordem de Retirada não encontrada", 404
    
    order = db_get_order(order_id)
    if not order:
        return "Ordem de Retirada não encontrada", 404
    
    # Criar PDF em memória
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Logo e cabeçalho - organizado em tabela para alinhamento horizontal
    logo_path = 'static/images/logopdf.png'
    logo_img = None
    if os.path.exists(logo_path):
        try:
            from PIL import Image as PILImage
            pil_logo = PILImage.open(logo_path)
            logo_width, logo_height = pil_logo.size
            logo_aspect = logo_width / logo_height
            
            # Manter proporção: altura máxima 2.5cm
            max_height = 2.5*cm
            logo_height_calc = max_height
            logo_width_calc = logo_height_calc * logo_aspect
            
            # Limitar largura máxima
            if logo_width_calc > 3*cm:
                logo_width_calc = 3*cm
                logo_height_calc = logo_width_calc / logo_aspect
            
            logo_img = Image(logo_path, width=logo_width_calc, height=logo_height_calc)
        except:
            logo_img = None
    
    company_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontSize=10,
        alignment=0,  # Left alignment para ficar ao lado da logo
        spaceAfter=4,
        leading=12
    )
    
    company_info = Paragraph(
        f"<b>Clínica CEL</b><br/>"
        f"CNPJ: 62.891.287/0001-44<br/>"
        f"www.clinicadomobile.com.br",
        company_style
    )
    
    # Criar tabela para alinhar logo e informações horizontalmente
    header_data = []
    if logo_img:
        # Com logo: logo à esquerda, informações à direita
        header_data.append([logo_img, company_info])
        col_widths = [4*cm, 12*cm]
        table_style = TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),  # Logo à esquerda
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),  # Informações à esquerda
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ])
    else:
        # Se não houver logo, centralizar as informações
        company_style_center = ParagraphStyle(
            'CompanyInfoCenter',
            parent=styles['Normal'],
            fontSize=12,
            alignment=1,  # Center alignment
            spaceAfter=6,
            leading=14
        )
        company_info_center = Paragraph(
            f"<b>Clínica CEL</b><br/>"
            f"CNPJ: 62.891.287/0001-44<br/>"
            f"www.clinicadomobile.com.br",
            company_style_center
        )
        header_data.append([company_info_center])
        col_widths = [16*cm]
        table_style = TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ])
    
    header_table = Table(header_data, colWidths=col_widths)
    header_table.setStyle(table_style)
    
    story.append(header_table)
    story.append(Spacer(1, 0.4*cm))
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#FF8C00'),
        spaceAfter=12,
        alignment=1
    )
    
    story.append(Paragraph("ORDEM DE SERVIÇO - OS", title_style))
    story.append(Spacer(1, 0.3*cm))
    
    # Informações da OR
    info_value_style = ParagraphStyle(
        'InfoValue',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black,
        spaceAfter=8,
        fontName='Helvetica-Bold',
        leading=11
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#FF8C00'),
        spaceAfter=0,
        spaceBefore=6,
        alignment=1  # Centralizado
    )
    
    # Estilo específico para títulos de assinatura (sem espaço após)
    signature_heading_style = ParagraphStyle(
        'SignatureHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#FF8C00'),
        spaceAfter=0,
        spaceBefore=6,
        alignment=1,  # Centralizado
        leading=14
    )
    
    story.append(Paragraph("INFORMAÇÕES DA ORDEM", heading_style))
    story.append(Paragraph(f"<b>Número da OR:</b> {order.get('id', 'N/A')}", info_value_style))
    story.append(Paragraph(f"<b>ID do Reparo:</b> {repair_id}", info_value_style))
    emitted_date = order.get('emitted_at', '')[:10] if order.get('emitted_at') else 'N/A'
    story.append(Paragraph(f"<b>Data de Emissão:</b> {emitted_date}", info_value_style))
    story.append(Paragraph(f"<b>Emitido por:</b> {order.get('emitted_by', 'N/A')}", info_value_style))
    story.append(Spacer(1, 0.2*cm))
    
    # Informações do Cliente
    story.append(Paragraph("CLIENTE", heading_style))
    customer_name = repair.get('customer_name', 'N/A')
    story.append(Paragraph(f"<b>Nome:</b> {customer_name}", info_value_style))
    customer_phone = repair.get('customer_phone', 'N/A')
    story.append(Paragraph(f"<b>Telefone:</b> {customer_phone}", info_value_style))
    
    if repair.get('customer_cpf'):
        cpf = repair.get('customer_cpf', '')
        if len(cpf) == 11:
            formatted_cpf = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        else:
            formatted_cpf = cpf
        story.append(Paragraph(f"<b>CPF:</b> <font face='Courier' size='9'>{formatted_cpf}</font>", info_value_style))
    
    if repair.get('customer_address'):
        story.append(Paragraph(f"<b>Endereço:</b> {repair.get('customer_address')}", info_value_style))
    
    story.append(Spacer(1, 0.2*cm))
    
    # Informações do Dispositivo
    story.append(Paragraph("DISPOSITIVO", heading_style))
    device_name = repair.get('device_name', 'N/A')
    story.append(Paragraph(f"<b>Nome do Dispositivo:</b> {device_name}", info_value_style))
    device_model = repair.get('device_model', 'N/A')
    story.append(Paragraph(f"<b>Modelo:</b> {device_model}", info_value_style))
    device_imei = repair.get('device_imei', 'N/A')
    story.append(Paragraph(f"<b>IMEI:</b> <font face='Courier' size='9'>{device_imei}</font>", info_value_style))
    story.append(Spacer(1, 0.2*cm))
    
    # Observações
    if order.get('observations'):
        obs_style = ParagraphStyle(
            'Observations',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=8,
            leading=11
        )
        story.append(Paragraph("OBSERVAÇÕES", heading_style))
        story.append(Paragraph(order.get('observations'), obs_style))
        story.append(Spacer(1, 0.2*cm))
    
    # Assinaturas - Organizadas em tabela lado a lado
    story.append(Spacer(1, 0.2*cm))
    
    signature_line_style = ParagraphStyle(
        'SignatureLine',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=4,
        leading=11,
        alignment=1  # Centralizado
    )
    
    # Assinaturas digitais são apenas no link do cliente
    # Na OR, as assinaturas são físicas (linha para assinar)
    
    # Linha de assinatura do cliente (física)
    customer_line = Table([['']], colWidths=[7*cm])
    customer_line.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), -2),  # Padding negativo para reduzir espaço
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    # Linha de assinatura do técnico (física)
    tech_line = Table([['']], colWidths=[7*cm])
    tech_line.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), -2),  # Padding negativo para reduzir espaço
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    # Adicionar assinatura do cliente (física)
    story.append(Paragraph("ASSINATURA DO CLIENTE", signature_heading_style))
    story.append(customer_line)
    story.append(Paragraph(f"<b>{repair.get('customer_name', 'Cliente')}</b>", signature_line_style))
    
    story.append(Spacer(1, 0.3*cm))
    
    # Adicionar assinatura do técnico (física)
    story.append(Paragraph("ASSINATURA DO TÉCNICO", signature_heading_style))
    story.append(tech_line)
    story.append(Paragraph(f"<b>{order.get('emitted_by', 'Raí Silva')}</b>", signature_line_style))
    
    # Construir PDF
    doc.build(story)
    buffer.seek(0)
    
    from flask import Response
    return Response(buffer.getvalue(), mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename=OR_{repair_id}_{order.get("id")}.pdf'
    })

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
        f"<b>Clínica CEL</b><br/>"
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
    
    # Assinatura Digital
    if repair.get('signature') and repair['signature'].get('image'):
        story.append(Paragraph("ASSINATURA DIGITAL", heading_style))
        signature_path = repair['signature']['image']
        # Normalizar o caminho - garantir que comece com 'static/'
        if signature_path.startswith('/static/'):
            signature_path = signature_path[1:]  # Remove a barra inicial: /static/ -> static/
        elif signature_path.startswith('static/'):
            pass  # Já está correto
        elif signature_path.startswith('/'):
            # Se começa com / mas não tem static, adicionar
            signature_path = 'static' + signature_path
        else:
            # Se não começa com nada, adicionar static/
            signature_path = 'static/' + signature_path.lstrip('/')
        
        # Tentar carregar a imagem da assinatura
        signature_loaded = False
        if os.path.exists(signature_path):
            try:
                # Verificar dimensões da imagem para manter proporção
                from PIL import Image as PILImage
                pil_sig = PILImage.open(signature_path)
                sig_width, sig_height = pil_sig.size
                sig_aspect = sig_width / sig_height
                
                # Definir largura máxima e calcular altura proporcional
                max_width = 10*cm
                sig_height_calc = max_width / sig_aspect
                if sig_height_calc > 5*cm:
                    sig_height_calc = 5*cm
                    max_width = sig_height_calc * sig_aspect
                
                signature_img = Image(signature_path, width=max_width, height=sig_height_calc)
                story.append(signature_img)
                signature_loaded = True
            except Exception as e:
                print(f"Erro ao carregar assinatura: {e}")
                # Tentar caminho alternativo
                alt_path = signature_path.replace('static/', '').replace('/static/', '')
                if os.path.exists(alt_path):
                    try:
                        from PIL import Image as PILImage
                        pil_sig = PILImage.open(alt_path)
                        sig_width, sig_height = pil_sig.size
                        sig_aspect = sig_width / sig_height
                        max_width = 10*cm
                        sig_height_calc = max_width / sig_aspect
                        if sig_height_calc > 5*cm:
                            sig_height_calc = 5*cm
                            max_width = sig_height_calc * sig_aspect
                        signature_img = Image(alt_path, width=max_width, height=sig_height_calc)
                        story.append(signature_img)
                        signature_loaded = True
                    except:
                        pass
        
        if signature_loaded:
            story.append(Spacer(1, 0.3*cm))
            signed_date = repair['signature'].get('signed_at', '')
            if signed_date:
                signed_date_formatted = signed_date[:16].replace('T', ' ')
            else:
                signed_date_formatted = 'N/A'
            story.append(Paragraph(f"<b>Assinado em:</b> {signed_date_formatted}", styles['Normal']))
            story.append(Spacer(1, 0.5*cm))
        else:
            # Mostrar mensagem mesmo se não conseguir carregar a imagem
            story.append(Paragraph("Assinatura digital presente (imagem não disponível)", styles['Normal']))
            signed_date = repair['signature'].get('signed_at', '')
            if signed_date:
                signed_date_formatted = signed_date[:16].replace('T', ' ')
                story.append(Paragraph(f"<b>Assinado em:</b> {signed_date_formatted}", styles['Normal']))
            story.append(Spacer(1, 0.5*cm))
    
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
    
    # Checklists Antifraude
    repair_checklists = get_checklists_by_repair(repair_id)
    
    if repair_checklists:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph("CHECKLISTS ANTIFRAUDE", heading_style))
        
        for checklist in repair_checklists:
            checklist_type_name = "Checklist Antifraude Inicial" if checklist.get('type') == 'inicial' else "Checklist Antifraude de Conclusão"
            story.append(Paragraph(f"<b>{checklist_type_name} - ID: {checklist.get('id', 'N/A')}</b>", info_value_style))
            
            checklist_date = checklist.get('timestamp', '')[:16] if checklist.get('timestamp') else 'N/A'
            story.append(Paragraph(f"<b>Data:</b> {checklist_date}", info_value_style))
            story.append(Spacer(1, 0.2*cm))
            
            # Fotos do Checklist
            if checklist.get('photos'):
                photos = checklist.get('photos', {})
                story.append(Paragraph("<b>📸 Fotos:</b>", info_value_style))
                
                photo_items = []
                if photos.get('imei_photo'):
                    photo_path = photos['imei_photo']
                    if photo_path.startswith('/static/'):
                        photo_path = photo_path[1:]
                    elif not photo_path.startswith('static/'):
                        photo_path = 'static/' + photo_path.lstrip('/')
                    
                    if os.path.exists(photo_path):
                        try:
                            from PIL import Image as PILImage
                            pil_photo = PILImage.open(photo_path)
                            photo_width, photo_height = pil_photo.size
                            photo_aspect = photo_width / photo_height
                            max_width = 6*cm
                            photo_height_calc = max_width / photo_aspect
                            if photo_height_calc > 4*cm:
                                photo_height_calc = 4*cm
                                max_width = photo_height_calc * photo_aspect
                            photo_img = Image(photo_path, width=max_width, height=photo_height_calc)
                            story.append(Paragraph("<b>Foto do IMEI:</b>", info_value_style))
                            story.append(photo_img)
                            story.append(Spacer(1, 0.2*cm))
                        except:
                            pass
                
                if photos.get('placa_photo'):
                    photo_path = photos['placa_photo']
                    if photo_path.startswith('/static/'):
                        photo_path = photo_path[1:]
                    elif not photo_path.startswith('static/'):
                        photo_path = 'static/' + photo_path.lstrip('/')
                    
                    if os.path.exists(photo_path):
                        try:
                            from PIL import Image as PILImage
                            pil_photo = PILImage.open(photo_path)
                            photo_width, photo_height = pil_photo.size
                            photo_aspect = photo_width / photo_height
                            max_width = 6*cm
                            photo_height_calc = max_width / photo_aspect
                            if photo_height_calc > 4*cm:
                                photo_height_calc = 4*cm
                                max_width = photo_height_calc * photo_aspect
                            photo_img = Image(photo_path, width=max_width, height=photo_height_calc)
                            story.append(Paragraph("<b>Foto da Placa:</b>", info_value_style))
                            story.append(photo_img)
                            story.append(Spacer(1, 0.2*cm))
                        except:
                            pass
                
                if photos.get('conectores_photo'):
                    photo_path = photos['conectores_photo']
                    if photo_path.startswith('/static/'):
                        photo_path = photo_path[1:]
                    elif not photo_path.startswith('static/'):
                        photo_path = 'static/' + photo_path.lstrip('/')
                    
                    if os.path.exists(photo_path):
                        try:
                            from PIL import Image as PILImage
                            pil_photo = PILImage.open(photo_path)
                            photo_width, photo_height = pil_photo.size
                            photo_aspect = photo_width / photo_height
                            max_width = 6*cm
                            photo_height_calc = max_width / photo_aspect
                            if photo_height_calc > 4*cm:
                                photo_height_calc = 4*cm
                                max_width = photo_height_calc * photo_aspect
                            photo_img = Image(photo_path, width=max_width, height=photo_height_calc)
                            story.append(Paragraph("<b>Foto dos Conectores:</b>", info_value_style))
                            story.append(photo_img)
                            story.append(Spacer(1, 0.2*cm))
                        except:
                            pass
            
            # Testes do Checklist
            if checklist.get('tests'):
                tests = checklist.get('tests', {})
                story.append(Paragraph("<b>🧪 Testes Realizados:</b>", info_value_style))
                
                # Mapeamento dos testes
                test_labels = {
                    'test_before_power': 'Botão Power',
                    'test_before_volume': 'Botões de Volume',
                    'test_before_silent': 'Botão Silenciar',
                    'test_before_home': 'Botão Home',
                    'test_before_other_buttons': 'Outros Botões',
                    'test_before_display_touch': 'Display e Touch',
                    'test_before_signal': 'Sinal da Operadora',
                    'test_before_proximity': 'Sensor de Proximidade',
                    'test_before_speaker': 'Auto-Falante',
                    'test_before_earpiece': 'Auricular',
                    'test_before_microphone': 'Microfone',
                    'test_before_touch_id': 'Touch ID',
                    'test_before_vibration': 'Vibra',
                    'test_before_front_camera': 'Câmera Frontal',
                    'test_before_back_camera': 'Câmera Traseira',
                    'test_before_flash': 'Flash',
                    'test_before_face_id': 'Face ID',
                    'test_before_wifi': 'Wi-FI',
                    'test_before_bluetooth': 'Bluetooth',
                    'test_before_charging': 'Carregamento',
                    'test_before_headphone': 'Fone de Ouvido',
                    'test_before_biometric': 'Sensor Biométrico',
                    'test_before_nfc': 'NFC',
                    'test_before_wireless_charging': 'Carga por Indução',
                    'test_after_power': 'Botão Power',
                    'test_after_volume': 'Botões de Volume',
                    'test_after_silent': 'Botão Silenciar',
                    'test_after_home': 'Botão Home',
                    'test_after_other_buttons': 'Outros Botões',
                    'test_after_display_touch': 'Display e Touch',
                    'test_after_signal': 'Sinal da Operadora',
                    'test_after_proximity': 'Sensor de Proximidade',
                    'test_after_speaker': 'Auto-Falante',
                    'test_after_earpiece': 'Auricular',
                    'test_after_microphone': 'Microfone',
                    'test_after_touch_id': 'Touch ID',
                    'test_after_vibration': 'Vibra',
                    'test_after_front_camera': 'Câmera Frontal',
                    'test_after_back_camera': 'Câmera Traseira',
                    'test_after_flash': 'Flash',
                    'test_after_face_id': 'Face ID',
                    'test_after_wifi': 'Wi-FI',
                    'test_after_bluetooth': 'Bluetooth',
                    'test_after_charging': 'Carregamento',
                    'test_after_headphone': 'Fone de Ouvido',
                    'test_after_biometric': 'Sensor Biométrico',
                    'test_after_nfc': 'NFC',
                    'test_after_wireless_charging': 'Carga por Indução'
                }
                
                test_list = []
                if checklist.get('type') == 'inicial':
                    # Testes ANTES
                    for test_key, test_label in test_labels.items():
                        if test_key.startswith('test_before_') and tests.get(test_key):
                            test_list.append(f"✅ {test_label} (Antes)")
                
                # Testes DEPOIS (para ambos os tipos)
                for test_key, test_label in test_labels.items():
                    if test_key.startswith('test_after_') and tests.get(test_key):
                        test_list.append(f"✅ {test_label} (Depois)")
                
                if test_list:
                    # Dividir em linhas para melhor visualização no PDF
                    for test_item in test_list:
                        story.append(Paragraph(test_item, styles['Normal']))
                else:
                    story.append(Paragraph("Nenhum teste registrado", styles['Normal']))
                
                story.append(Spacer(1, 0.2*cm))
            
            # Assinatura do Checklist
            if checklist.get('signature'):
                signature_path = checklist['signature']
                if signature_path.startswith('/static/'):
                    signature_path = signature_path[1:]
                elif not signature_path.startswith('static/'):
                    signature_path = 'static/' + signature_path.lstrip('/')
                
                if os.path.exists(signature_path):
                    try:
                        from PIL import Image as PILImage
                        pil_sig = PILImage.open(signature_path)
                        sig_width, sig_height = pil_sig.size
                        sig_aspect = sig_width / sig_height
                        max_width = 6*cm
                        sig_height_calc = max_width / sig_aspect
                        if sig_height_calc > 3*cm:
                            sig_height_calc = 3*cm
                            max_width = sig_height_calc * sig_aspect
                        signature_img = Image(signature_path, width=max_width, height=sig_height_calc)
                        story.append(Paragraph("<b>✍️ Assinatura Digital do Cliente:</b>", info_value_style))
                        story.append(signature_img)
                        story.append(Spacer(1, 0.2*cm))
                    except:
                        pass
            else:
                story.append(Paragraph("<b>✍️ Assinatura Digital:</b> Pendente", info_value_style))
            
            story.append(Spacer(1, 0.4*cm))
    
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

# Rotas para servir imagens do banco de dados (necessário no Render onde o sistema de arquivos é efêmero)
@app.route('/static/checklist_photos/<path:filename>')
def serve_checklist_photo(filename):
    """Serve imagens de checklist do banco de dados"""
    import base64
    from flask import Response
    
    # Buscar em todos os checklists
    checklists = get_all_checklists()
    
    for checklist in checklists:
        # Verificar fotos do checklist
        photos = checklist.get('photos', {})
        for field, photo_path in photos.items():
            if isinstance(photo_path, str) and filename in photo_path:
                # Verificar se há dados base64 salvos
                photo_data = checklist.get('_photo_data', {})
                if photo_data:
                    # PRIORIDADE 1: Buscar pelo campo (mais preciso - garante que cada campo tenha sua própria imagem)
                    if field in photo_data:
                        try:
                            img_data = base64.b64decode(photo_data[field])
                            # Detectar tipo MIME baseado na extensão
                            mimetype = 'image/png'
                            if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                                mimetype = 'image/jpeg'
                            elif filename.lower().endswith('.png'):
                                mimetype = 'image/png'
                            return Response(img_data, mimetype=mimetype)
                        except Exception as e:
                            print(f"Erro ao decodificar imagem {filename} pelo campo {field}: {e}")
                    
                    # PRIORIDADE 2: Buscar pelo filename exato
                    if filename in photo_data:
                        try:
                            img_data = base64.b64decode(photo_data[filename])
                            mimetype = 'image/png'
                            if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                                mimetype = 'image/jpeg'
                            return Response(img_data, mimetype=mimetype)
                        except Exception as e:
                            print(f"Erro ao decodificar imagem {filename}: {e}")
                    
                    # PRIORIDADE 3: Buscar por correspondência parcial (apenas se o filename começar com o campo)
                    for stored_filename, stored_data in photo_data.items():
                        # Verificar se o filename corresponde exatamente ou se começa com o campo
                        if (filename == stored_filename or 
                            (filename.startswith(field + '_') and stored_filename.startswith(field + '_') and filename in stored_filename) or
                            (stored_filename.startswith(field + '_') and stored_filename in filename)):
                            try:
                                img_data = base64.b64decode(stored_data)
                                mimetype = 'image/png'
                                if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                                    mimetype = 'image/jpeg'
                                return Response(img_data, mimetype=mimetype)
                            except Exception as e:
                                print(f"Erro ao decodificar imagem {filename}: {e}")
                                continue
        
        # Verificar assinatura do checklist
        signature = checklist.get('signature', '')
        if isinstance(signature, str) and filename in signature:
            sig_data = checklist.get('_signature_data')
            if sig_data:
                try:
                    img_data = base64.b64decode(sig_data)
                    return Response(img_data, mimetype='image/png')
                except Exception as e:
                    print(f"Erro ao decodificar assinatura {filename}: {e}")
    
    # Se não encontrou no banco, tentar do disco (fallback)
    photo_path = os.path.join('static', 'checklist_photos', filename)
    if os.path.exists(photo_path):
        try:
            with open(photo_path, 'rb') as f:
                img_data = f.read()
                # Detectar tipo MIME baseado na extensão
                mimetype = 'image/png'
                if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                    mimetype = 'image/jpeg'
                elif filename.lower().endswith('.png'):
                    mimetype = 'image/png'
                return Response(img_data, mimetype=mimetype)
        except Exception as e:
            print(f"Erro ao ler arquivo {photo_path}: {e}")
    
    return "Imagem não encontrada", 404

@app.route('/static/signatures/<path:filename>')
def serve_signature(filename):
    """Serve assinaturas do banco de dados"""
    import base64
    from flask import Response
    
    # Buscar em todos os reparos
    repairs = get_all_repairs()
    
    for repair in repairs:
        signature = repair.get('signature', {})
        if isinstance(signature, dict):
            sig_image = signature.get('image', '')
            if isinstance(sig_image, str) and filename in sig_image:
                # Verificar se há dados base64 salvos
                sig_data = repair.get('_signature_data')
                if sig_data:
                    try:
                        # Se tem vírgula, remover o prefixo data:image/png;base64,
                        if isinstance(sig_data, str) and ',' in sig_data:
                            sig_data = sig_data.split(',')[1]
                        img_data = base64.b64decode(sig_data)
                        return Response(img_data, mimetype='image/png')
                    except Exception as e:
                        print(f"Erro ao decodificar assinatura {filename}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
    
    # Se não encontrou no banco, tentar do disco (fallback)
    sig_path = os.path.join('static', 'signatures', filename)
    if os.path.exists(sig_path):
        try:
            with open(sig_path, 'rb') as f:
                img_data = f.read()
                return Response(img_data, mimetype='image/png')
        except Exception as e:
            print(f"Erro ao ler arquivo {sig_path}: {e}")
    
    return "Assinatura não encontrada", 404

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

# ========== ROTA PARA SERVIR O APP MOBILE ==========

@app.route('/mobile_app/')
def mobile_app():
    """Serve o app mobile PWA"""
    return send_from_directory('mobile_app', 'index.html')

@app.route('/mobile_app/manifest.json')
def mobile_app_manifest():
    """Serve o manifest.json com Content-Type correto"""
    from flask import Response
    import json
    import os
    
    manifest_path = os.path.join('mobile_app', 'manifest.json')
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
        
        # Garantir que todas as URLs sejam absolutas
        base_url = request.url_root.rstrip('/')
        
        # Converter start_url e scope para absolutos
        if manifest_data.get('start_url', '').startswith('/'):
            manifest_data['start_url'] = base_url + manifest_data['start_url']
        if manifest_data.get('scope', '').startswith('/'):
            manifest_data['scope'] = base_url + manifest_data['scope']
        
        # Converter URLs dos ícones para absolutos
        if 'icons' in manifest_data:
            for icon in manifest_data['icons']:
                if icon.get('src', '').startswith('/'):
                    icon['src'] = base_url + icon['src']
        
        response = Response(
            json.dumps(manifest_data, indent=2, ensure_ascii=False),
            mimetype='application/manifest+json',
            headers={
                'Content-Type': 'application/manifest+json; charset=utf-8',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Cache-Control': 'public, max-age=3600'
            }
        )
        return response
    return "Manifest não encontrado", 404

@app.route('/mobile_app/service-worker.js')
def mobile_app_service_worker():
    """Serve o service-worker.js com Content-Type correto e headers apropriados"""
    from flask import Response
    import os
    
    sw_path = os.path.join('mobile_app', 'service-worker.js')
    if os.path.exists(sw_path):
        with open(sw_path, 'r', encoding='utf-8') as f:
            sw_content = f.read()
        return Response(
            sw_content,
            mimetype='application/javascript',
            headers={
                'Content-Type': 'application/javascript; charset=utf-8',
                'Service-Worker-Allowed': '/mobile_app/',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Cache-Control': 'public, max-age=3600'
            }
        )
    return "Service Worker não encontrado", 404

@app.route('/mobile_app/<path:filename>')
def mobile_app_static(filename):
    """Serve arquivos estáticos do app mobile"""
    # Mapear extensões para MIME types
    mime_types = {
        '.json': 'application/json',
        '.js': 'application/javascript',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        '.css': 'text/css',
        '.html': 'text/html'
    }
    
    import os
    ext = os.path.splitext(filename)[1].lower()
    mimetype = mime_types.get(ext, 'application/octet-stream')
    
    response = send_from_directory('mobile_app', filename)
    if response.status_code == 200:
        response.headers['Content-Type'] = mimetype
        if filename == 'service-worker.js':
            response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Access-Control-Allow-Origin'] = '*'
    return response

# ========== APIs REST PARA O APP MOBILE ==========

import hashlib
import uuid
from datetime import datetime

def hash_password(password):
    """Gera hash SHA256 da senha"""
    return hashlib.sha256(password.encode()).hexdigest()

# API: Consultar CPF (verificar se existe serviço)
@app.route('/api/check-cpf', methods=['POST'])
def api_check_cpf():
    """Verifica se existe serviço cadastrado para o CPF"""
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        repairs = get_repairs_by_cpf(cpf)
        has_service = len(repairs) > 0
        has_password = get_customer_password_hash(cpf) is not None
        
        return jsonify({
            'success': True,
            'has_service': has_service,
            'has_password': has_password,
            'repairs_count': len(repairs)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Criar senha (primeiro acesso)
@app.route('/api/create-password', methods=['POST'])
def api_create_password():
    """Cria senha para cliente no primeiro acesso"""
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        password = data.get('password', '').strip()
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        if not password or len(password) < 6:
            return jsonify({'success': False, 'error': 'Senha deve ter no mínimo 6 caracteres'}), 400
        
        # Verificar se existe serviço
        repairs = get_repairs_by_cpf(cpf)
        if len(repairs) == 0:
            return jsonify({'success': False, 'error': 'Nenhum serviço encontrado para este CPF'}), 400
        
        # Verificar se já tem senha
        if get_customer_password_hash(cpf):
            return jsonify({'success': False, 'error': 'Senha já cadastrada. Use "Entrar" para fazer login.'}), 400
        
        # Salvar senha
        password_hash = hash_password(password)
        save_customer_password(cpf, password_hash)
        
        return jsonify({'success': True, 'message': 'Senha criada com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Login
@app.route('/api/login', methods=['POST'])
def api_login():
    """Faz login do cliente"""
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        password = data.get('password', '').strip()
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        if not password:
            return jsonify({'success': False, 'error': 'Senha obrigatória'}), 400
        
        # Verificar senha
        stored_hash = get_customer_password_hash(cpf)
        if not stored_hash:
            return jsonify({'success': False, 'error': 'CPF não cadastrado. Use "Primeiro Acesso".'}), 401
        
        password_hash = hash_password(password)
        if password_hash != stored_hash:
            return jsonify({'success': False, 'error': 'Senha incorreta'}), 401
        
        # Gerar token de sessão simples (em produção, usar JWT)
        session_token = hashlib.sha256(f"{cpf}{password_hash}{datetime.now().isoformat()}".encode()).hexdigest()
        
        return jsonify({
            'success': True,
            'token': session_token,
            'cpf': cpf
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Obter dados do reparo (para cliente logado)
@app.route('/api/my-repairs', methods=['POST'])
def api_my_repairs():
    """Retorna todos os reparos do cliente"""
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        repairs = get_repairs_by_cpf(cpf)
        
        # Formatar dados para o app
        repairs_data = []
        for repair in repairs:
            # Obter OR se existir
            order = get_order_by_repair(repair.get('id'))
            # Obter checklists
            checklists = get_checklists_by_repair(repair.get('id'))
            
            repair_info = {
                'id': repair.get('id'),
                'device_name': repair.get('device_name', ''),
                'device_model': repair.get('device_model', ''),
                'problem_description': repair.get('problem_description', ''),
                'status': repair.get('status', 'aguardando'),
                'budget': repair.get('budget'),
                'created_at': repair.get('created_at'),
                'updated_at': repair.get('updated_at'),
                'messages': repair.get('messages', []),
                'history': repair.get('history', []),
                'has_order': order is not None,
                'order_id': order.get('id') if order else None,
                'checklists_count': len(checklists)
            }
            repairs_data.append(repair_info)
        
        return jsonify({
            'success': True,
            'repairs': repairs_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Obter detalhes de um reparo específico
@app.route('/api/repair/<repair_id>', methods=['POST'])
def api_repair_details(repair_id):
    """Retorna detalhes completos de um reparo"""
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        repair = db_get_repair(repair_id)
        if not repair:
            return jsonify({'success': False, 'error': 'Reparo não encontrado'}), 404
        
        # Verificar se o reparo pertence ao CPF
        repair_cpf = repair.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
        if repair_cpf != cpf:
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        # Obter OR
        order = get_order_by_repair(repair_id)
        # Obter checklists
        checklists = get_checklists_by_repair(repair_id)
        
        return jsonify({
            'success': True,
            'repair': repair,
            'order': order,
            'checklists': checklists
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Solicitar orçamento
@app.route('/api/request-budget', methods=['POST'])
def api_request_budget():
    """Cria uma solicitação de orçamento"""
    try:
        data = request.get_json()
        
        # Validar dados obrigatórios
        required_fields = ['customer_name', 'customer_phone', 'customer_email', 'customer_cpf', 'device_brand', 'device_model', 'defect', 'description']
        for field in required_fields:
            if not data.get(field):
                field_name = field.replace('_', ' ').title()
                return jsonify({'success': False, 'error': f'Campo obrigatório: {field_name}'}), 400
        
        # Validar CPF
        cpf = data.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '')
        if len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF deve ter 11 dígitos'}), 400
        
        # Validar e-mail
        email = data.get('customer_email', '').strip()
        if '@' not in email or '.' not in email:
            return jsonify({'success': False, 'error': 'E-mail inválido'}), 400
        
        request_id = str(uuid.uuid4())[:8]
        request_data = {
            'customer_name': data.get('customer_name'),
            'customer_phone': data.get('customer_phone'),
            'customer_email': email,
            'customer_cpf': cpf,
            'device_brand': data.get('device_brand'),
            'device_model': data.get('device_model'),
            'defect': data.get('defect'),
            'description': data.get('description'),
            'created_at': datetime.now().isoformat()
        }
        
        save_budget_request(request_id, request_data)
        
        return jsonify({
            'success': True,
            'request_id': request_id,
            'message': 'Solicitação enviada com sucesso'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Registrar subscription de notificação push (Web Push API)
@app.route('/api/register-push-token', methods=['POST'])
def api_register_push_token():
    """Registra subscription Web Push para notificações push"""
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        subscription = data.get('subscription')
        device_info = data.get('device_info', {})
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        if not subscription:
            return jsonify({'success': False, 'error': 'Subscription obrigatória'}), 400
        
        # Salvar subscription (não apenas token)
        save_push_token(cpf, subscription, device_info)
        
        return jsonify({'success': True, 'message': 'Subscription registrada com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Buscar notificações pendentes (polling do service worker)
@app.route('/api/notifications/pending', methods=['POST'])
def api_get_pending_notifications():
    """Retorna notificações pendentes para o cliente (usado pelo service worker)"""
    from datetime import datetime
    
    try:
        data = request.get_json()
        cpf = data.get('cpf', '').strip().replace('.', '').replace('-', '').replace(' ', '')
        last_check = data.get('last_check', '')
        
        if not cpf or len(cpf) != 11:
            return jsonify({'success': False, 'error': 'CPF inválido'}), 400
        
        # Buscar notificações pendentes do banco
        since_timestamp = last_check if last_check else None
        notifications = get_pending_notifications(cpf, since_timestamp)
        
        # Formatar notificações
        formatted_notifications = []
        for notif in notifications[:10]:  # Limitar a 10
            formatted_notifications.append({
                'id': notif.get('id'),
                'type': notif.get('type'),
                'title': notif.get('title'),
                'body': notif.get('body'),
                'repair_id': notif.get('repair_id'),
                'timestamp': notif.get('timestamp'),
                'data': notif.get('data', {})
            })
        
        return jsonify({
            'success': True,
            'notifications': formatted_notifications,
            'last_check': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
