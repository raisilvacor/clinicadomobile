import sys
import os
# Adicionar diretório local de bibliotecas ao path
sys.path.append(os.path.join(os.path.dirname(__file__), 'libs'))

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, send_file, Response
import json
from functools import wraps
from io import BytesIO
from os_pdf import build_os_pdf
import secrets
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
    get_all_customers,
    get_customer,
    get_customer_by_doc,
    save_customer,
    delete_customer,
    get_all_transactions,
    get_transaction,
    save_transaction,
    delete_transaction,
    get_all_service_orders,
    get_service_order,
    get_service_order_by_public_token,
    save_service_order,
    delete_service_order,
    save_equipment,
    get_business_hours,
    save_business_hours,
    is_business_open as db_is_business_open,
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sua-chave-secreta-mude-isso-em-producao')

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
    is_open = db_is_business_open()
    from db import get_all_brands
    brands = get_all_brands()
    os_query = (request.args.get('os', '') or '').strip()
    os_lookup = None
    os_lookup_error = None
    if os_query:
        digits = _clean_digits(os_query)
        if digits:
            try:
                os_number = int(digits)
                found = None
                for o in get_all_service_orders():
                    if not isinstance(o, dict):
                        continue
                    if o.get('os_number') == os_number:
                        found = o
                        break
                if not found:
                    os_lookup_error = 'OS não encontrada.'
                else:
                    opened_at = found.get('opened_at')
                    if hasattr(opened_at, 'isoformat'):
                        opened_at = opened_at.isoformat()
                    opened_at = (opened_at or '').strip() or 'N/A'

                    os_lookup = {
                        'os_number': found.get('os_number'),
                        'status': found.get('status'),
                        'status_label': _status_label(found.get('status')),
                        'opened_at': opened_at,
                    }
            except Exception:
                os_lookup_error = 'Número de OS inválido.'
        else:
            os_lookup_error = 'Informe somente números.'

    return render_template(
        'index.html',
        content=site_content,
        is_open=is_open,
        brands=brands,
        os_query=os_query,
        os_lookup=os_lookup,
        os_lookup_error=os_lookup_error,
        page=None,
        page_title=None,
    )

def _render_site_page(page, page_title):
    site_content = get_site_content()
    is_open = db_is_business_open()
    from db import get_all_brands
    brands = get_all_brands()
    return render_template(
        'index.html',
        content=site_content,
        is_open=is_open,
        brands=brands,
        os_query='',
        os_lookup=None,
        os_lookup_error=None,
        page=page,
        page_title=page_title,
    )

@app.route('/servicos')
def site_servicos():
    return _render_site_page('servicos', 'Serviços | Clínica do Cell')

@app.route('/sobre')
def site_sobre():
    return _render_site_page('sobre', 'Sobre | Clínica do Cell')

@app.route('/dispositivos')
def site_dispositivos():
    return _render_site_page('dispositivos', 'Dispositivos | Clínica do Cell')

@app.route('/laboratorio')
def site_laboratorio():
    return _render_site_page('laboratorio', 'Laboratório | Clínica do Cell')

@app.route('/contato')
def site_contato():
    return _render_site_page('contato', 'Contato | Clínica do Cell')

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
    return render_template('admin/dashboard.html')

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
        contact['cnpj'] = request.form.get('cnpj', '')
        contact['phone'] = request.form.get('phone', '')
        contact['email'] = request.form.get('email', '')
        contact['whatsapp'] = request.form.get('whatsapp', '')
        contact['address'] = request.form.get('address', '')
        contact['city'] = request.form.get('city', '')
        contact['address2'] = request.form.get('address2', '')
        contact['city2'] = request.form.get('city2', '')
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
    try:
        config = get_budget_config()
        if not isinstance(config, list):
            config = []
    except Exception as e:
        print(f"Erro ao carregar budget_config: {e}")
        config = []
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_brand':
            brand_name = request.form.get('brand_name')
            if brand_name:
                # Check if brand exists
                if not any(b['brand'] == brand_name for b in config):
                    import base64
                    from PIL import Image
                    from io import BytesIO
                    
                    brand_logo_base64 = ""
                    if 'brand_logo' in request.files:
                        file = request.files['brand_logo']
                        if file and file.filename:
                            try:
                                img = Image.open(file)
                                if img.mode != 'RGBA':
                                    img = img.convert('RGBA')
                                
                                # Redimensionar se necessário
                                max_size = 300
                                if img.width > max_size or img.height > max_size:
                                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                                
                                output = BytesIO()
                                img.save(output, format='PNG', optimize=True)
                                brand_logo_base64 = f"data:image/png;base64,{base64.b64encode(output.getvalue()).decode('utf-8')}"
                            except Exception as e:
                                print(f"Erro ao processar logo da marca no orçamento: {e}")

                    config.append({
                        'brand': brand_name, 
                        'logo': brand_logo_base64,
                        'models': []
                    })
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

@app.route('/admin/nfse', methods=['GET'])
@login_required
def admin_nfse():
    """Redireciona para o portal oficial de NFS-e do governo"""
    return redirect('https://www.nfse.gov.br/EmissorNacional/Login?ReturnUrl=%2fEmissorNacional')

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

# ========== ROTAS DE CLIENTES REMOVIDAS ==========

def _clean_digits(value):
    import re
    return re.sub(r'\D', '', (value or '').strip())

def _parse_money(value):
    value = (value or '').strip()
    if not value:
        return 0.0
    cleaned = value.replace('R$', '').replace(' ', '')
    if ',' in cleaned and '.' in cleaned:
        cleaned = cleaned.replace('.', '').replace(',', '.')
    elif ',' in cleaned and '.' not in cleaned:
        cleaned = cleaned.replace(',', '.')
    try:
        return float(cleaned)
    except Exception:
        return 0.0

@app.route('/admin/financeiro', methods=['GET'])
@login_required
def admin_financeiro():
    q = request.args.get('q', '').strip()
    tx_type = request.args.get('type', '').strip()
    category = request.args.get('category', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    transactions = get_all_transactions()
    normalized = []
    for t in transactions:
        if not isinstance(t, dict):
            continue
        tx = t.copy()
        tx_id = tx.get('id')
        if not tx_id:
            continue
        tx['type'] = (tx.get('type') or '').strip()
        tx['category'] = (tx.get('category') or '').strip()
        tx['description'] = (tx.get('description') or '').strip()
        tx['payment_method'] = (tx.get('payment_method') or '').strip()
        tx['date'] = (tx.get('date') or '').strip()
        tx['amount'] = tx.get('amount', 0)
        try:
            tx['amount'] = float(tx['amount'])
        except Exception:
            tx['amount'] = _parse_money(str(tx['amount']))
        normalized.append(tx)

    filtered = []
    ql = q.lower()
    for tx in normalized:
        if tx_type and tx.get('type') != tx_type:
            continue
        if category and tx.get('category') != category:
            continue
        d = tx.get('date') or ''
        if start_date and d and d < start_date:
            continue
        if end_date and d and d > end_date:
            continue
        if q:
            if ql not in (tx.get('description') or '').lower() and ql not in (tx.get('category') or '').lower() and ql not in (tx.get('payment_method') or '').lower():
                continue
        filtered.append(tx)

    total_income = sum(t.get('amount', 0.0) for t in filtered if t.get('type') == 'entrada')
    total_expense = sum(t.get('amount', 0.0) for t in filtered if t.get('type') == 'saida')
    balance = total_income - total_expense

    categories = sorted({(t.get('category') or '').strip() for t in normalized if (t.get('category') or '').strip()})

    return render_template(
        'admin/financeiro.html',
        transactions=filtered,
        q=q,
        type=tx_type,
        category=category,
        start_date=start_date,
        end_date=end_date,
        categories=categories,
        total_income=total_income,
        total_expense=total_expense,
        balance=balance
    )

@app.route('/admin/financeiro/new', methods=['GET', 'POST'])
@login_required
def admin_new_transaction():
    if request.method == 'POST':
        import uuid
        from datetime import datetime

        tx_id = str(uuid.uuid4())[:8]
        tx_type = (request.form.get('type', '') or '').strip()
        tx_date = (request.form.get('date', '') or '').strip()
        if not tx_date:
            tx_date = datetime.now().date().isoformat()

        tx = {
            'id': tx_id,
            'type': tx_type,
            'amount': _parse_money(request.form.get('amount', '')),
            'description': (request.form.get('description', '') or '').strip(),
            'category': (request.form.get('category', '') or '').strip(),
            'payment_method': (request.form.get('payment_method', '') or '').strip(),
            'date': tx_date,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }

        if tx['type'] not in ['entrada', 'saida']:
            return render_template('admin/transaction_form.html', transaction=tx, error='Tipo inválido. Selecione Entrada ou Saída.')
        if tx['amount'] <= 0:
            return render_template('admin/transaction_form.html', transaction=tx, error='Valor inválido. Informe um valor maior que zero.')
        if not tx['description']:
            return render_template('admin/transaction_form.html', transaction=tx, error='Descrição é obrigatória.')
        if not tx['category']:
            return render_template('admin/transaction_form.html', transaction=tx, error='Categoria é obrigatória.')

        save_transaction(tx_id, tx)
        return redirect(url_for('admin_financeiro'))

    return render_template('admin/transaction_form.html', transaction=None)

@app.route('/admin/financeiro/<transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_transaction(transaction_id):
    transaction = get_transaction(transaction_id)
    if not transaction:
        return redirect(url_for('admin_financeiro'))

    if request.method == 'POST':
        from datetime import datetime

        tx_type = (request.form.get('type', '') or '').strip()
        tx_date = (request.form.get('date', '') or '').strip()

        updated = {
            'id': transaction_id,
            'type': tx_type,
            'amount': _parse_money(request.form.get('amount', '')),
            'description': (request.form.get('description', '') or '').strip(),
            'category': (request.form.get('category', '') or '').strip(),
            'payment_method': (request.form.get('payment_method', '') or '').strip(),
            'date': tx_date,
            'created_at': transaction.get('created_at'),
            'updated_at': datetime.now().isoformat(),
        }

        if updated['type'] not in ['entrada', 'saida']:
            return render_template('admin/transaction_form.html', transaction=updated, error='Tipo inválido. Selecione Entrada ou Saída.')
        if updated['amount'] <= 0:
            return render_template('admin/transaction_form.html', transaction=updated, error='Valor inválido. Informe um valor maior que zero.')
        if not updated['description']:
            return render_template('admin/transaction_form.html', transaction=updated, error='Descrição é obrigatória.')
        if not updated['category']:
            return render_template('admin/transaction_form.html', transaction=updated, error='Categoria é obrigatória.')

        save_transaction(transaction_id, updated)
        return redirect(url_for('admin_financeiro'))

    return render_template('admin/transaction_form.html', transaction=transaction)

@app.route('/admin/financeiro/<transaction_id>/delete', methods=['POST'])
@login_required
def admin_delete_transaction(transaction_id):
    delete_transaction(transaction_id)
    return redirect(url_for('admin_financeiro'))

# ========== ROTAS DE OS REMOVIDAS ==========

# ========== ROTAS DE SCORE DE QUALIDADE DO TÉCNICO ==========

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
            'website': request.form.get('website', ''),
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
        supplier['website'] = request.form.get('website', '')
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

@app.route('/admin/search-suppliers', methods=['GET'])
@login_required
def admin_search_suppliers():
    """Busca produtos nos sites dos fornecedores"""
    from supplier_scraper import search_product_in_suppliers
    
    query = request.args.get('query', '').strip()
    results = []
    error = None
    
    if query:
        try:
            suppliers = get_all_suppliers()
            results = search_product_in_suppliers(suppliers, query)
        except Exception as e:
            error = f"Erro ao buscar nos fornecedores: {str(e)}"
            print(f"Erro na busca de fornecedores: {e}")
    
    return render_template('admin/dashboard.html', 
                         supplier_results=results,
                         search_query=query,
                         search_error=error)

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

@app.route('/admin/mark-product-sold/<product_id>', methods=['POST'])
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
    from db import get_all_brands
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
        from db import save_brand
        
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
                    
                    # Preservar transparência se presente
                    if img.mode in ('RGBA', 'LA', 'P'):
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                    
                    # Redimensionar se muito grande (max 400px de largura ou altura)
                    max_size = 400
                    if img.width > max_size or img.height > max_size:
                        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                    
                    # Salvar como PNG para preservar transparência total
                    output = BytesIO()
                    img.save(output, format='PNG', optimize=True)
                    output.seek(0)
                    
                    # Converter para base64
                    file_data = output.getvalue()
                    brand_data['_image_data'] = base64.b64encode(file_data).decode('utf-8')
                    brand_data['image'] = f"/static/brand_images/{brand_id}.png"
                except Exception as e:
                    print(f"Erro ao processar imagem: {e}")
        
        save_brand(brand_id, brand_data)
        return redirect(url_for('admin_brands'))
    
    return render_template('admin/new_brand.html')

@app.route('/admin/brands/<brand_id>/delete', methods=['POST'])
@login_required
def admin_delete_brand(brand_id):
    """Deletar marca"""
    from db import delete_brand as db_delete_brand
    try:
        db_delete_brand(brand_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/static/brand_images/<path:filename>')
def serve_brand_image(filename):
    """Serve imagens de marcas do banco de dados"""
    import base64
    from flask import Response
    from db import get_all_brands
    
    brands = get_all_brands()
    for brand in brands:
        image_path = brand.get('image', '')
        if isinstance(image_path, str) and filename in image_path:
            image_data = brand.get('_image_data')
            if image_data:
                try:
                    img_data = base64.b64decode(image_data)
                    mimetype = 'image/png'
                    if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                        mimetype = 'image/jpeg'
                    return Response(img_data, mimetype=mimetype)
                except Exception as e:
                    print(f"Erro ao decodificar imagem {filename}: {e}")
    
    return "Imagem não encontrada", 404

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
    from datetime import datetime
    
    url_root = request.url_root.rstrip('/')
    
    urlset = ET.Element('urlset')
    urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')

    def _add_url(loc, changefreq=None, priority=None, lastmod=None):
        url = ET.SubElement(urlset, 'url')
        ET.SubElement(url, 'loc').text = loc
        if lastmod:
            ET.SubElement(url, 'lastmod').text = lastmod
        if changefreq:
            ET.SubElement(url, 'changefreq').text = changefreq
        if priority:
            ET.SubElement(url, 'priority').text = priority

    def _lastmod_from(value):
        if not value:
            return None
        if hasattr(value, 'date'):
            try:
                return value.date().isoformat()
            except Exception:
                return None
        if isinstance(value, str):
            v = value.strip()
            if not v:
                return None
            v = v.replace('Z', '+00:00')
            try:
                dt = datetime.fromisoformat(v)
                return dt.date().isoformat()
            except Exception:
                if len(v) >= 10 and v[4] == '-' and v[7] == '-':
                    return v[:10]
                return None
        return None
    
    # Página principal
    _add_url(url_root + '/', changefreq='daily', priority='1.0')

    # Páginas institucionais
    _add_url(f'{url_root}{url_for("site_servicos")}', changefreq='weekly', priority='0.9')
    _add_url(f'{url_root}{url_for("site_sobre")}', changefreq='monthly', priority='0.7')
    _add_url(f'{url_root}{url_for("site_dispositivos")}', changefreq='monthly', priority='0.7')
    _add_url(f'{url_root}{url_for("site_laboratorio")}', changefreq='monthly', priority='0.6')
    _add_url(f'{url_root}{url_for("site_contato")}', changefreq='monthly', priority='0.6')
    _add_url(f'{url_root}/orcamento/', changefreq='monthly', priority='0.6')
    
    # Loja
    _add_url(f'{url_root}{url_for("public_shop")}', changefreq='daily', priority='0.8')
    
    # Produtos
    products = get_all_products()
    for product in products:
        if not product.get('sold', False):
            product_id = product.get('id')
            if not product_id:
                continue
            lastmod = _lastmod_from(product.get('updated_at') or product.get('created_at'))
            _add_url(f'{url_root}{url_for("public_product", product_id=product_id)}', changefreq='weekly', priority='0.7', lastmod=lastmod)
    
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
