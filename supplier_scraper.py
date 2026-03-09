
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
    Utiliza múltiplas estratégias com validação ESTRITA:
    1. Busca interna do site -> Filtra Links por Relevância -> Deep Scraping
    2. Busca externa via DuckDuckGo -> Filtra Links -> Deep Scraping
    
    Retorna uma lista de resultados ordenados por preço.
    """
    results = []
    
    # Normalizar query para comparação
    query_terms = [t.lower() for t in query.split() if len(t) > 2]
    
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

    def is_relevant_title(title, query_terms):
        """Verifica se o título é relevante para a busca"""
        if not title: return False
        title_lower = title.lower()
        
        # Verificar se pelo menos 40% dos termos da busca estão no título
        # Isso permite encontrar produtos mesmo que o nome varie um pouco
        matches = 0
        for term in query_terms:
            if term in title_lower:
                matches += 1
        
        if len(query_terms) > 0:
            relevance = matches / len(query_terms)
            return relevance >= 0.4  # Reduzido para 40% para ser menos estrito
        return True

    def extract_from_json_ld(soup, supplier_name, website):
        """Extrai produtos de dados estruturados JSON-LD"""
        products = []
        try:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    
                    for item in items:
                        item_type = item.get('@type', '')
                        if item_type == 'Product':
                            process_json_product(item, products, supplier_name, website)
                        elif item_type == 'ItemList' and 'itemListElement' in item:
                            for sub_item in item['itemListElement']:
                                if isinstance(sub_item, dict) and sub_item.get('item'):
                                    process_json_product(sub_item['item'], products, supplier_name, website)
                                else:
                                    process_json_product(sub_item, products, supplier_name, website)
                except:
                    continue
        except:
            pass
        return products

    def process_json_product(item, products, supplier_name, website):
        try:
            name = item.get('name')
            if not name or not is_relevant_title(name, query_terms): return

            offers = item.get('offers')
            price = 0
            url = item.get('url')

            if isinstance(offers, dict):
                price = offers.get('price')
                if not url: url = offers.get('url')
            elif isinstance(offers, list) and offers:
                price = offers[0].get('price')
                if not url: url = offers[0].get('url')
            
            if price:
                try:
                    price = float(price)
                except:
                    return

            if price and price > 0 and url:
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

        FORBIDDEN_CONTAINERS = [
            'header', 'footer', 'nav', 'aside', 'cart-drawer', 'mini-cart', 'search-modal',
            'mobile-menu', 'whatsapp-button', 'newsletter-popup', 'breadcrumb'
        ]

        price_elements = soup.find_all(string=re.compile(r'R\$\s*\d+'))
        if not price_elements:
            price_elements = soup.find_all(string=re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}'))
        
        for price_el in price_elements:
            try:
                price_text = price_el.strip()
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
                    classes = str(temp_node.get('class', [])).lower()
                    ids = str(temp_node.get('id', [])).lower()
                    if any(x in classes or x in ids for x in FORBIDDEN_CONTAINERS):
                        is_forbidden = True
                        break
                    temp_node = temp_node.parent
                
                if is_forbidden: continue

                current_node = container
                for _ in range(6):
                    if not current_node: break
                    
                    if current_node.name == 'a':
                        if is_valid_link(current_node, TITLE_BLACKLIST, website):
                            found_link = current_node
                            break
                            
                    links = current_node.find_all('a', href=True)
                    valid_links = []
                    for l in links:
                        if is_valid_link(l, TITLE_BLACKLIST, website):
                            valid_links.append(l)
                    
                    if valid_links:
                        best_link = None
                        for l in valid_links:
                            if l.find('img'):
                                best_link = l
                                break
                            classes = str(l.get('class', [])).lower()
                            if any(c in classes for c in ['title', 'name', 'product']):
                                best_link = l
                                break
                        found_link = best_link if best_link else valid_links[0]
                        break
                    current_node = current_node.parent
                    
                if not found_link: continue
                    
                link = urljoin(website, found_link['href'])
                title = found_link.get_text(strip=True)
                
                # Tentar melhorar o título
                if len(title) < 5 and current_node:
                    title_el = current_node.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'], class_=re.compile(r'title|name|product', re.I))
                    if title_el:
                        t_text = title_el.get_text(strip=True)
                        if len(t_text) > 3 and t_text.lower() not in TITLE_BLACKLIST:
                            title = t_text
                
                if not title or len(title) < 3 or title.lower() in TITLE_BLACKLIST:
                    continue

                # Na fase de busca de LINKS, não precisamos filtrar tão estritamente por preço > 5
                # pois o preço aqui pode ser parcial ou errado. O importante é o link.
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
        text = link_el.get_text(strip=True).lower()
        if not text:
            text = link_el.get('title', '').strip().lower()
        if not text:
            img = link_el.find('img')
            if img:
                alt = img.get('alt', '').strip()
                if alt: text = alt.lower()
        
        if not text: return False
        if len(text) < 3: return False
        
        for blacklisted in blacklist:
            if blacklisted in text:
                return False
        
        href = link_el.get('href', '').lower()
        if any(x in href for x in ['/cart', '/checkout', '/login', '/account', 'javascript:', '#', 'tel:', 'mailto:', 'wp-login', 'wp-admin', 'minha-conta']):
            return False
            
        if base_url:
            base_domain = urlparse(base_url).netloc
            href_domain = urlparse(href).netloc
            if href_domain and base_domain != href_domain:
                return False
            if '?s=' in href or 'search' in href or 'busca' in href:
                return False
        return True

    def search_duckduckgo_lite(query, site_url):
        try:
            domain = urlparse(site_url).netloc
            ddg_query = f"site:{domain} {query}"
            url = f"https://lite.duckduckgo.com/lite/?q={quote(ddg_query)}"
            headers = get_headers()
            headers['Referer'] = 'https://lite.duckduckgo.com/'
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200: return []
            soup = BeautifulSoup(resp.text, 'html.parser')
            links = []
            anchors = soup.find_all('a', class_='result-link')
            for a in anchors:
                href = a.get('href')
                title = a.get_text(strip=True)
                if href and href.startswith('http') and domain in href and is_relevant_title(title, query_terms):
                    links.append({'link': href, 'title': title})
            return links
        except:
            return []

    def fetch_product_details(url, supplier_name):
        try:
            resp = requests.get(url, headers=get_headers(), timeout=8)
            if resp.status_code != 200: return None
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Tenta JSON-LD primeiro
            json_products = extract_from_json_ld(soup, supplier_name, url)
            if json_products:
                return json_products[0]
            
            # Tenta heurística
            heuristic_products = extract_via_heuristic(soup, supplier_name, url)
            if heuristic_products:
                heuristic_products.sort(key=lambda x: len(x['title']), reverse=True)
                valid_products = [p for p in heuristic_products if p['price'] > 5]
                if valid_products:
                    return valid_products[0]
            return None
        except:
            return None

    def process_supplier(supplier):
        supplier_results = []
        website = supplier['website'].strip().rstrip('/')
        supplier_name = supplier.get('name', 'Fornecedor')
        
        # 1. Busca Interna -> Extrair Links
        search_urls = [
            f"{website}/?s={quote(query)}&post_type=product", 
            f"{website}/search?q={quote(query)}", 
            f"{website}/busca?q={quote(query)}",
            f"{website}/buscar?q={quote(query)}",
            f"{website}/loja/busca?q={quote(query)}"
        ]
        
        found_internal_links = []
        for url in search_urls:
            try:
                response = requests.get(url, headers=get_headers(), timeout=8)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # Extrair APENAS links relevantes
                    candidates = extract_via_heuristic(soup, supplier_name, website)
                    for cand in candidates:
                        found_internal_links.append(cand['link'])
                    if found_internal_links: break
            except:
                continue
        
        # 2. Busca Externa (DDG) -> Extrair Links
        if not found_internal_links:
            ddg_links = search_duckduckgo_lite(query, website)
            for item in ddg_links:
                found_internal_links.append(item['link'])

        # 3. Deep Scraping (Visitar Links Relevantes)
        unique_links = list(set(found_internal_links))[:6] # Limitar a 6 visitas para aumentar chance de sucesso
        for link in unique_links:
            details = fetch_product_details(link, supplier_name)
            if details and is_relevant_title(details['title'], query_terms):
                supplier_results.append(details)
                    
        return supplier_results

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_supplier = {executor.submit(process_supplier, s): s for s in valid_suppliers}
        for future in concurrent.futures.as_completed(future_to_supplier):
            try:
                data = future.result()
                if data: results.extend(data)
            except Exception: pass

    # Deduplicar e Ordenar
    unique_results = []
    seen_links = set()
    for r in results:
        if r['link'] not in seen_links:
            unique_results.append(r)
            seen_links.add(r['link'])
    unique_results.sort(key=lambda x: x['price'])
    
    return unique_results
