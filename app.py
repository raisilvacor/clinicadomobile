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
    get_all_suppliers,
    get_supplier as db_get_supplier,
    save_supplier,
    delete_supplier as db_delete_supplier
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
    return render_template('index.html', content=site_content)

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
    
    return render_template('admin/dashboard.html', abandoned_count=abandoned_count, critical_count=critical_count)

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
                    file.seek(0)  # Resetar posição do arquivo
                    file_data = file.read()
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
    repair['messages'].append({
        'type': 'budget_approved',
        'content': f'Você aprovou o orçamento de R$ {repair["budget"]["amount"]:.2f}. O reparo será iniciado em breve.',
        'sent_at': datetime.now().isoformat()
    })
    save_repair(repair_id, repair)
    return jsonify({'success': True})

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
            signature_data = signature_data.split(',')[1]
        
        signature_filename = f"signature_{repair_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        signature_path = os.path.join(signatures_dir, signature_filename)
        
        with open(signature_path, 'wb') as f:
            f.write(base64.b64decode(signature_data))
        
        repair['signature'] = {
            'image': f"/static/signatures/{signature_filename}",
            'signed_at': datetime.now().isoformat()
        }
        
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
    
    # Gerar garantia (30 dias)
    warranty_until = datetime.now() + timedelta(days=30)
    repair['warranty'] = {
        'period': '30 dias',
        'valid_until': warranty_until.isoformat(),
        'coverage': 'Peças e mão de obra'
    }
    
    repair['history'].append({
        'timestamp': datetime.now().isoformat(),
        'action': 'Reparo concluído - Garantia de 30 dias ativada',
        'status': 'concluido'
    })
    repair['messages'].append({
        'type': 'completed',
        'content': 'Seu reparo foi concluído com sucesso! Você possui 30 dias de garantia. Obrigado pela confiança!',
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
            'customer_received': request.form.get('customer_received', '') == 'on',
            'customer_signature': None
        }
        
        # Salvar assinatura do cliente na retirada (se houver)
        signature_data = request.form.get('signature_data', '')
        if signature_data:
            photos_dir = os.path.join('static', 'checklist_photos')
            if not os.path.exists(photos_dir):
                os.makedirs(photos_dir)
            
            signature_filename = f"or_signature_{repair_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            signature_path = os.path.join(photos_dir, signature_filename)
            
            if ',' in signature_data:
                signature_data_clean = signature_data.split(',')[1]
            else:
                signature_data_clean = signature_data
            
            signature_bytes = base64.b64decode(signature_data_clean)
            with open(signature_path, 'wb') as f:
                f.write(signature_bytes)
            
            or_data['customer_signature'] = f"/static/checklist_photos/{signature_filename}"
            # Salvar também como base64 no banco (para persistência no Render)
            or_data['_signature_data'] = signature_data_clean
        
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
    return render_template('admin/emit_or.html', repair=repair, conclusion_checklist=conclusion_checklist, unsigned_checklists=unsigned_checklists)

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

@app.route('/admin/repairs/<repair_id>/or/pdf', methods=['GET'])
@login_required
def admin_or_pdf(repair_id):
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
        f"<b>Clínica do Reparo</b><br/>"
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
            f"<b>Clínica do Reparo</b><br/>"
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
    
    story.append(Paragraph("ORDEM DE RETIRADA", title_style))
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
    
    # Verificar se há assinatura digital do cliente
    customer_sig_img = None
    if order.get('customer_signature'):
        signature_path = order['customer_signature']
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
                if sig_height_calc > 2.5*cm:
                    sig_height_calc = 2.5*cm
                    max_width = sig_height_calc * sig_aspect
                customer_sig_img = Image(signature_path, width=max_width, height=sig_height_calc)
            except:
                pass
    
    # Criar tabela com duas colunas para as assinaturas
    # Coluna 1: Cliente
    customer_col = []
    customer_col.append(Paragraph("ASSINATURA DO CLIENTE", heading_style))
    if customer_sig_img:
        customer_col.append(customer_sig_img)
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
    customer_col.append(customer_line)
    customer_col.append(Paragraph(f"<b>{repair.get('customer_name', 'Cliente')}</b>", signature_line_style))
    
    # Coluna 2: Técnico
    tech_col = []
    tech_col.append(Paragraph("ASSINATURA DO TÉCNICO", heading_style))
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
    tech_col.append(tech_line)
    tech_col.append(Paragraph(f"<b>{order.get('emitted_by', 'Raí Silva')}</b>", signature_line_style))
    
    # Adicionar cada coluna separadamente (uma abaixo da outra para melhor organização)
    story.append(Paragraph("ASSINATURA DO CLIENTE", signature_heading_style))
    if customer_sig_img:
        story.append(customer_sig_img)
    # Linha logo abaixo do título (sem espaçamento)
    story.append(customer_line)
    story.append(Paragraph(f"<b>{repair.get('customer_name', 'Cliente')}</b>", signature_line_style))
    
    story.append(Spacer(1, 0.3*cm))
    
    story.append(Paragraph("ASSINATURA DO TÉCNICO", signature_heading_style))
    # Linha logo abaixo do título (sem espaçamento)
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
        f"<b>Clínica do Reparo</b><br/>"
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
    story.append(Paragraph("ORDEM DE REPARO (OR)", title_style))
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
                
                test_list = []
                if checklist.get('type') == 'inicial':
                    if tests.get('test_before_screen'):
                        test_list.append("✅ Tela (Antes)")
                    if tests.get('test_before_touch'):
                        test_list.append("✅ Touch (Antes)")
                    if tests.get('test_before_camera'):
                        test_list.append("✅ Câmera (Antes)")
                    if tests.get('test_before_battery'):
                        test_list.append("✅ Bateria (Antes)")
                    if tests.get('test_before_audio'):
                        test_list.append("✅ Áudio (Antes)")
                    if tests.get('test_before_buttons'):
                        test_list.append("✅ Botões (Antes)")
                
                if tests.get('test_after_screen'):
                    test_list.append("✅ Tela (Depois)")
                if tests.get('test_after_touch'):
                    test_list.append("✅ Touch (Depois)")
                if tests.get('test_after_camera'):
                    test_list.append("✅ Câmera (Depois)")
                if tests.get('test_after_battery'):
                    test_list.append("✅ Bateria (Depois)")
                if tests.get('test_after_audio'):
                    test_list.append("✅ Áudio (Depois)")
                if tests.get('test_after_buttons'):
                    test_list.append("✅ Botões (Depois)")
                
                if test_list:
                    test_text = " | ".join(test_list)
                    story.append(Paragraph(test_text, styles['Normal']))
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
                    # Tentar buscar pelo filename completo ou parcial
                    for stored_filename, stored_data in photo_data.items():
                        if filename in stored_filename or stored_filename in filename or filename in photo_path:
                            try:
                                img_data = base64.b64decode(stored_data)
                                # Detectar tipo MIME baseado na extensão
                                mimetype = 'image/png'
                                if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                                    mimetype = 'image/jpeg'
                                elif filename.lower().endswith('.png'):
                                    mimetype = 'image/png'
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
            if filename in sig_image:
                sig_data = repair.get('_signature_data')
                if sig_data:
                    try:
                        img_data = base64.b64decode(sig_data)
                        return Response(img_data, mimetype='image/png')
                    except:
                        pass
    
    # Se não encontrou no banco, tentar do disco (fallback)
    sig_path = os.path.join('static', 'signatures', filename)
    if os.path.exists(sig_path):
        with open(sig_path, 'rb') as f:
            return Response(f.read(), mimetype='image/png')
    
    return "Assinatura não encontrada", 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
