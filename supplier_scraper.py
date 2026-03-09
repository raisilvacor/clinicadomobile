
import requests
from bs4 import BeautifulSoup
import re
import concurrent.futures
from urllib.parse import urljoin, quote, urlparse
import json
import random

def search_product_in_suppliers(suppliers, query):
    """
    Busca um produto em todos os sites dos fornecedores cadastrados.
    Utiliza múltiplas estratégias:
    1. Busca interna do site -> Extrai Links -> Deep Scraping (Visita o produto)
    2. Busca externa via DuckDuckGo -> Deep Scraping
    
    Retorna uma lista de resultados ordenados por preço.
    """
    results = []
    
    # Filtrar fornecedores com site válido
    valid_suppliers = [s for s in suppliers if s.get('website') and s['website'].strip().startswith('http')]
    
    if not valid_suppliers:
        return []

    # User agents para rotação
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
    ]

    def get_headers():
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
        }

    def extract_from_json_ld(soup, supplier_name, website):
        """Extrai produtos de dados estruturados JSON-LD"""
        products = []
        try:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    # Pode ser uma lista ou um objeto único
                    items = data if isinstance(data, list) else [data]
                    
                    for item in items:
                        # Verifica se é um Produto ou Lista de Itens
                        item_type = item.get('@type', '')
                        
                        if item_type == 'Product':
                            process_json_product(item, products, supplier_name, website)
                        elif item_type == 'ItemList' and 'itemListElement' in item:
                            for sub_item in item['itemListElement']:
                                if isinstance(sub_item, dict) and sub_item.get('item'):
                                    # Às vezes o produto está aninhado em 'item'
                                    process_json_product(sub_item['item'], products, supplier_name, website)
                                else:
                                    process_json_product(sub_item, products, supplier_name, website)
                except:
                    continue
        except Exception as e:
            pass
        return products

    def process_json_product(item, products, supplier_name, website):
        """Processa um item JSON-LD e adiciona à lista se for válido"""
        try:
            name = item.get('name')
            if not name: return

            # Ofertas podem estar em 'offers'
            offers = item.get('offers')
            price = 0
            price_currency = 'BRL'
            url = item.get('url')

            if isinstance(offers, dict):
                price = offers.get('price')
                price_currency = offers.get('priceCurrency', 'BRL')
                if not url: url = offers.get('url')
            elif isinstance(offers, list) and offers:
                price = offers[0].get('price')
                price_currency = offers[0].get('priceCurrency', 'BRL')
                if not url: url = offers[0].get('url')
            
            # Tentar converter preço
            if price:
                try:
                    price = float(price)
                except:
                    return

            if price and price > 0 and url:
                # Normalizar URL
                if not url.startswith('http'):
                    url = urljoin(website, url)
                
                products.append({
                    'supplier_name': supplier_name,
                    'title': name,
                    'price': price,
                    'price_formatted': f"R$ {price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    'link': url,
                    'description': f"Encontrado via dados estruturados em {supplier_name}"
                })
        except:
            pass

    def extract_via_heuristic(soup, supplier_name, website):
        """Extração baseada em heurística visual (HTML)"""
        supplier_results = []
        
        # Lista negra de títulos genéricos para ignorar
        TITLE_BLACKLIST = [
            'ir para o conteúdo', 'skip to content', 'menu', 'carrinho', 'minha conta', 
            'entrar', 'cadastre-se', 'home', 'início', 'busca', 'pesquisa', 
            'checkout', 'finalizar compra', 'política de privacidade', 
            'termos de uso', 'contato', 'fale conosco', 'sobre nós', 'login', 
            'register', 'cart', 'my account', 'shop', 'loja', 'whatsapp',
            'adicionar ao carrinho', 'ver detalhes', 'comprar',
            'resultados da pesquisa', 'search results', 'resultados para', 
            'nenhum produto encontrado', 'filtrar', 'ordernar por', 'mais vendidos',
            'lançamentos', 'ofertas', 'categorias', 'produtos'
        ]

        # Containers proibidos (geralmente header/footer/sidebar)
        FORBIDDEN_CONTAINERS = [
            'header', 'footer', 'nav', 'aside', 'cart-drawer', 'mini-cart', 'search-modal',
            'mobile-menu', 'whatsapp-button', 'newsletter-popup', 'breadcrumb'
        ]

        # Estratégia: Encontrar todos os elementos que parecem ser preços
        price_elements = soup.find_all(string=re.compile(r'R\$\s*\d+'))
        
        if not price_elements:
            # Tentar formato sem R$ mas com , e .
            price_elements = soup.find_all(string=re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}'))
        
        for price_el in price_elements:
            try:
                price_text = price_el.strip()
                
                # Limpar preço
                match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', price_text)
                if not match:
                    match = re.search(r'(\d+,\d{2})', price_text)
                
                if match:
                    val_str = match.group(1)
                    val_float = float(val_str.replace('.', '').replace(',', '.'))
                else:
                    continue
                    
                price = val_float
                
                # Encontrar container
                container = price_el.parent
                found_link = None
                
                # Verificar se o container está em área proibida
                is_forbidden = False
                temp_node = container
                for _ in range(8):
                    if not temp_node: break
                    if temp_node.name in ['header', 'footer', 'nav']:
                        is_forbidden = True
                        break
                    # Verificar classes/ids comuns de áreas proibidas
                    classes = str(temp_node.get('class', [])).lower()
                    ids = str(temp_node.get('id', [])).lower()
                    if any(x in classes or x in ids for x in FORBIDDEN_CONTAINERS):
                        is_forbidden = True
                        break
                    temp_node = temp_node.parent
                
                if is_forbidden:
                    continue

                # Heurística melhorada: Subir até encontrar um container que pareça um card de produto
                current_node = container
                
                for _ in range(6): # Subir até 6 níveis
                    if not current_node: break
                    
                    # Se o próprio nó é um link
                    if current_node.name == 'a':
                        if is_valid_link(current_node, TITLE_BLACKLIST, website):
                            found_link = current_node
                            break
                            
                    # Procurar links dentro deste nó
                    links = current_node.find_all('a', href=True)
                    valid_links = []
                    for l in links:
                        if is_valid_link(l, TITLE_BLACKLIST, website):
                            valid_links.append(l)
                    
                    # Se encontrou links válidos
                    if valid_links:
                        # Preferir links que tenham imagem ou classe de título
                        best_link = None
                        for l in valid_links:
                            # Se tem imagem dentro, é forte candidato
                            if l.find('img'):
                                best_link = l
                                break
                            # Se tem classe de titulo
                            classes = str(l.get('class', [])).lower()
                            if any(c in classes for c in ['title', 'name', 'product']):
                                best_link = l
                                break
                        
                        found_link = best_link if best_link else valid_links[0]
                        break
                        
                    current_node = current_node.parent
                    
                if not found_link:
                    continue
                    
                link = urljoin(website, found_link['href'])
                title = found_link.get_text(strip=True)
                
                # Tentar melhorar o título se for muito curto
                if len(title) < 5 and current_node:
                    title_el = current_node.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'], class_=re.compile(r'title|name|product', re.I))
                    if title_el:
                        t_text = title_el.get_text(strip=True)
                        if len(t_text) > 3 and t_text.lower() not in TITLE_BLACKLIST:
                            title = t_text
                
                if not title or len(title) < 3 or title.lower() in TITLE_BLACKLIST:
                    continue

                if price > 0:
                    supplier_results.append({
                        'supplier_name': supplier_name,
                        'title': title,
                        'price': price,
                        'price_formatted': f"R$ {price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        'link': link,
                        'description': f"Encontrado via busca visual em {supplier_name}"
                    })
            except:
                continue
        return supplier_results

    def is_valid_link(link_el, blacklist, base_url=""):
        """Verifica se um link é válido para ser um produto"""
        text = link_el.get_text(strip=True).lower()
        
        # Tentar pegar texto do atributo title se não tiver texto visível
        if not text:
            text = link_el.get('title', '').strip().lower()

        if not text:
            # Se não tem texto, verifique se tem imagem com alt ou title
            img = link_el.find('img')
            if img:
                alt = img.get('alt', '').strip()
                if alt: text = alt.lower()
        
        if not text: return False
        if len(text) < 3: return False
        
        # Verificar se o texto está na blacklist
        for blacklisted in blacklist:
            if blacklisted in text:
                return False
        
        # Verificar href
        href = link_el.get('href', '').lower()
        if any(x in href for x in ['/cart', '/checkout', '/login', '/account', 'javascript:', '#', 'tel:', 'mailto:', 'wp-login', 'wp-admin', 'minha-conta']):
            return False
            
        # Evitar links para a própria página de busca (loop)
        if base_url:
            base_domain = urlparse(base_url).netloc
            href_domain = urlparse(href).netloc
            if href_domain and base_domain != href_domain:
                return False # Link externo (opcional, mas geralmente queremos produtos do fornecedor)
            
            if '?s=' in href or 'search' in href or 'busca' in href:
                return False
            
        return True

    def search_duckduckgo_lite(query, site_url):
        """Busca usando DuckDuckGo Lite (HTML puro) com operador site:"""
        try:
            domain = urlparse(site_url).netloc
            ddg_query = f"site:{domain} {query}"
            url = f"https://lite.duckduckgo.com/lite/?q={quote(ddg_query)}"
            
            headers = get_headers()
            headers['Referer'] = 'https://lite.duckduckgo.com/'
            
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            links = []
            
            # Extrair links do DDG Lite
            # A estrutura geralmente é tabelas com links
            anchors = soup.find_all('a', class_='result-link')
            
            for a in anchors:
                href = a.get('href')
                if href and href.startswith('http') and domain in href:
                    title = a.get_text(strip=True)
                    links.append({'link': href, 'title': title})
            
            return links
        except Exception as e:
            return []

    def fetch_product_details(url, supplier_name):
        """Acessa a página do produto para tentar pegar o preço"""
        try:
            resp = requests.get(url, headers=get_headers(), timeout=8)
            if resp.status_code != 200: return None
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Tenta JSON-LD primeiro (mais confiável)
            json_products = extract_from_json_ld(soup, supplier_name, url)
            if json_products:
                # Retorna o primeiro que tiver preço
                for p in json_products:
                    if p['price'] > 0:
                        return p
            
            # Tenta heurística na página do produto
            heuristic_products = extract_via_heuristic(soup, supplier_name, url)
            if heuristic_products:
                # Heurística pode pegar vários preços (relacionados etc), tenta pegar o maior destaque ou primeiro
                # Ordenar por tamanho do título (títulos maiores geralmente são descrições de produtos, títulos curtos podem ser lixo)
                # Ou ordenar pelo preço para evitar 0 ou muito baixo
                heuristic_products.sort(key=lambda x: len(x['title']), reverse=True)
                
                # Filtrar preços muito baixos (provavelmente parcela ou erro)
                valid_products = [p for p in heuristic_products if p['price'] > 5]
                
                if valid_products:
                    return valid_products[0]
                
            return None
        except:
            return None

    # Função principal para processar cada fornecedor
    def process_supplier(supplier):
        supplier_results = []
        website = supplier['website'].strip().rstrip('/')
        supplier_name = supplier.get('name', 'Fornecedor')
        
        # 1. Tentar busca interna
        search_urls = [
            f"{website}/?s={quote(query)}&post_type=product", 
            f"{website}/search?q={quote(query)}", 
            f"{website}/busca?q={quote(query)}",
            f"{website}/buscar?q={quote(query)}",
            f"{website}/loja/busca?q={quote(query)}"
        ]
        
        found_internal_links = []
        
        # Tenta busca interna primeiro para encontrar LINKS de produtos
        for url in search_urls:
            try:
                response = requests.get(url, headers=get_headers(), timeout=8)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Usar heurística para encontrar "candidates" na lista de busca
                    # Mas em vez de pegar os dados finais, pegamos apenas os LINKS
                    candidates = extract_via_heuristic(soup, supplier_name, website)
                    
                    for cand in candidates:
                        found_internal_links.append(cand['link'])
                        
                    if found_internal_links:
                        break
            except:
                continue
        
        # Deep Scraping: Visitar cada link encontrado (limitado a 3)
        # para garantir que pegamos o preço certo da página do produto
        unique_links = list(set(found_internal_links))[:3]
        
        for link in unique_links:
            details = fetch_product_details(link, supplier_name)
            if details:
                supplier_results.append(details)
        
        # 2. Se a busca interna retornou pouco ou nada, tenta DuckDuckGo (Deep Search)
        if len(supplier_results) == 0:
            ddg_links = search_duckduckgo_lite(query, website)
            # Para cada link encontrado no DDG, precisamos entrar para pegar o preço
            # Isso é lento, então limitamos a 3 primeiros resultados
            for item in ddg_links[:3]:
                details = fetch_product_details(item['link'], supplier_name)
                if details:
                    # Usa o título do DDG se o da página falhar, mas o preço da página
                    if not details['title'] or details['title'] == "Produto sem título":
                        details['title'] = item['title']
                    details['description'] = f"Encontrado via Busca Profunda em {supplier_name}"
                    supplier_results.append(details)
                    
        return supplier_results

    # Executar buscas em paralelo
    # Aumentamos workers e timeout total
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_supplier = {executor.submit(process_supplier, s): s for s in valid_suppliers}
        for future in concurrent.futures.as_completed(future_to_supplier):
            try:
                data = future.result()
                if data:
                    results.extend(data)
            except Exception as exc:
                print(f"Erro ao buscar: {exc}")

    # Deduplicar resultados por Link
    unique_results = []
    seen_links = set()
    for r in results:
        if r['link'] not in seen_links:
            unique_results.append(r)
            seen_links.add(r['link'])

    # Ordenar por preço
    unique_results.sort(key=lambda x: x['price'])
    
    return unique_results
