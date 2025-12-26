from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import json
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'sua-chave-secreta-mude-isso-em-producao'

CONFIG_FILE = 'config.json'

def load_config():
    """Carrega o arquivo de configuração"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config):
    """Salva o arquivo de configuração"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_site_content():
    """Obtém o conteúdo do site do config"""
    config = load_config()
    return config.get('site_content', {})

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
        config = load_config()
        
        if password == config.get('admin_password', 'admin123'):
            session['logged_in'] = True
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
    config = load_config()
    site_content = config.get('site_content', {})
    hero = site_content.get('hero', {})
    
    if request.method == 'POST':
        hero['title'] = request.form.get('title', '')
        hero['subtitle'] = request.form.get('subtitle', '')
        hero['button_text'] = request.form.get('button_text', '')
        hero['background_image'] = request.form.get('background_image', '')
        
        site_content['hero'] = hero
        config['site_content'] = site_content
        save_config(config)
        
        return redirect(url_for('admin_hero'))
    
    return render_template('admin/hero.html', hero=hero)

@app.route('/admin/services', methods=['GET', 'POST'])
@login_required
def admin_services():
    config = load_config()
    site_content = config.get('site_content', {})
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
        
        site_content['services'] = services
        config['site_content'] = site_content
        save_config(config)
        
        return redirect(url_for('admin_services'))
    
    return render_template('admin/services.html', services=services)

@app.route('/admin/about', methods=['GET', 'POST'])
@login_required
def admin_about():
    config = load_config()
    site_content = config.get('site_content', {})
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
        
        site_content['about'] = about
        config['site_content'] = site_content
        save_config(config)
        
        return redirect(url_for('admin_about'))
    
    return render_template('admin/about.html', about=about)

@app.route('/admin/devices', methods=['GET', 'POST'])
@login_required
def admin_devices():
    config = load_config()
    site_content = config.get('site_content', {})
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
        
        site_content['devices'] = devices
        config['site_content'] = site_content
        save_config(config)
        
        return redirect(url_for('admin_devices'))
    
    return render_template('admin/devices.html', devices=devices)

@app.route('/admin/laboratory', methods=['GET', 'POST'])
@login_required
def admin_laboratory():
    config = load_config()
    site_content = config.get('site_content', {})
    laboratory = site_content.get('laboratory', {})
    
    if request.method == 'POST':
        laboratory['title'] = request.form.get('title', '')
        
        # Processar imagens
        images_text = request.form.get('images', '')
        laboratory['images'] = [img.strip() for img in images_text.split('\n') if img.strip()]
        
        site_content['laboratory'] = laboratory
        config['site_content'] = site_content
        save_config(config)
        
        return redirect(url_for('admin_laboratory'))
    
    return render_template('admin/laboratory.html', laboratory=laboratory)

@app.route('/admin/contact', methods=['GET', 'POST'])
@login_required
def admin_contact():
    config = load_config()
    site_content = config.get('site_content', {})
    contact = site_content.get('contact', {})
    
    if request.method == 'POST':
        contact['phone'] = request.form.get('phone', '')
        contact['email'] = request.form.get('email', '')
        contact['whatsapp'] = request.form.get('whatsapp', '')
        contact['address'] = request.form.get('address', '')
        contact['city'] = request.form.get('city', '')
        contact['hours_weekdays'] = request.form.get('hours_weekdays', '')
        contact['hours_saturday'] = request.form.get('hours_saturday', '')
        
        # Remover campos antigos se existirem
        contact.pop('phone1', None)
        contact.pop('phone2', None)
        contact.pop('email1', None)
        contact.pop('email2', None)
        
        site_content['contact'] = contact
        config['site_content'] = site_content
        save_config(config)
        
        return redirect(url_for('admin_contact'))
    
    return render_template('admin/contact.html', contact=contact)

@app.route('/admin/password', methods=['GET', 'POST'])
@login_required
def admin_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        config = load_config()
        config['admin_password'] = new_password
        save_config(config)
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/password.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
