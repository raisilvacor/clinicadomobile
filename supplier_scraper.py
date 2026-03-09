
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
    1. Busca interna do site (heurística + JSON-LD)
    2. Busca externa via DuckDuckGo (site:domain)
    
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
            # print(f"Erro ao extrair JSON-LD: {e}")
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
        
        # Estratégia: Encontrar todos os elementos que parecem ser preços
        price_elements = soup.find_all(string=re.compile(r'R\$\s*\d+'))
        
        if not price_elements:
            # Tentar formato sem R$ mas com , e .
            price_elements = soup.find_all(string=re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}'))
        
        for price_el in price_elements:
            try:
                # Limpar preço
                price_str = price_el.strip()
                match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', price_str)
                if not match:
                    match = re.search(r'(\d+,\d{2})', price_str)
                
                if match:
                    val_str = match.group(1)
                    val_float = float(val_str.replace('.', '').replace(',', '.'))
                else:
                    continue
                    
                price = val_float
                
                # Encontrar container
                container = price_el.parent
                found_link = None
                
                # Subir até 5 níveis procurando um link
                for _ in range(5):
                    if not container: break
                    if container.name == 'a':
                        found_link = container
                        break
                    # Link com classe de titulo ou produto
                    links = container.find_all('a', href=True)
                    for l in links:
                        if len(l.get_text(strip=True)) > 5:
                            found_link = l
                            break
                    if found_link: break
                    container = container.parent
                    
                if not found_link:
                    continue
                    
                link = urljoin(website, found_link['href'])
                title = found_link.get_text(strip=True)
                
                # Tentar melhorar o título
                if len(title) < 5 and container:
                    title_el = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'], class_=re.compile(r'title|name'))
                    if title_el:
                        title = title_el.get_text(strip=True)
                
                if not title:
                    title = "Produto sem título"

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
            # print(f"Erro no DDG: {e}")
            return []

    def fetch_product_details(url, supplier_name):
        """Acessa a página do produto para tentar pegar o preço"""
        try:
            resp = requests.get(url, headers=get_headers(), timeout=5)
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
                return heuristic_products[0]
                
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
        
        found_internal = False
        
        # Tenta busca interna primeiro
        for url in search_urls:
            try:
                response = requests.get(url, headers=get_headers(), timeout=8)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Tenta JSON-LD
                    json_res = extract_from_json_ld(soup, supplier_name, website)
                    if json_res:
                        supplier_results.extend(json_res)
                        found_internal = True
                    
                    # Tenta Heurística
                    html_res = extract_via_heuristic(soup, supplier_name, website)
                    if html_res:
                        supplier_results.extend(html_res)
                        found_internal = True
                        
                    if found_internal:
                        break
            except:
                continue
        
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
