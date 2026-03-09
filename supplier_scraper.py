
import requests
from bs4 import BeautifulSoup
import re
import concurrent.futures
from urllib.parse import urljoin, quote

def search_product_in_suppliers(suppliers, query):
    """
    Busca um produto em todos os sites dos fornecedores cadastrados.
    Retorna uma lista de resultados ordenados por preço.
    """
    results = []
    
    # Filtrar fornecedores com site válido
    valid_suppliers = [s for s in suppliers if s.get('website') and s['website'].strip().startswith('http')]
    
    if not valid_suppliers:
        return []

    # Função auxiliar para buscar em um único fornecedor
    def fetch_supplier(supplier):
        supplier_results = []
        website = supplier['website'].strip().rstrip('/')
        supplier_name = supplier.get('name', 'Fornecedor Desconhecido')
        
        # Tentar adivinhar a URL de busca
        # Padrões comuns: /?s=query, /search?q=query, /busca?q=query, /buscar?q=query
        search_urls = [
            f"{website}/?s={quote(query)}&post_type=product", # WooCommerce comum
            f"{website}/search?q={quote(query)}", # Shopify e outros
            f"{website}/busca?q={quote(query)}", # VTEX e BR
            f"{website}/buscar?q={quote(query)}",
            f"{website}/loja/busca?q={quote(query)}"
        ]
        
        # Headers para evitar bloqueio simples
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Tentar a primeira URL que retornar 200 e tiver conteúdo
        for url in search_urls:
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Heurística para encontrar produtos
                    # Estratégia: Encontrar todos os elementos que parecem ser preços
                    price_elements = soup.find_all(string=re.compile(r'R\$\s*\d+'))
                    
                    if not price_elements:
                        # Tentar formato sem R$ mas com , e .
                        price_elements = soup.find_all(string=re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}'))
                    
                    for price_el in price_elements:
                        try:
                            # Subir na árvore até encontrar um container de produto (div, li, article)
                            # Ou simplesmente o pai comum com um link e imagem
                            
                            # Limpar preço
                            price_str = price_el.strip()
                            # Extrair número: R$ 1.200,50 -> 1200.50
                            # Remover tudo que não for dígito ou vírgula (que será o separador decimal brasileiro)
                            # Mas cuidado com o ponto de milhar
                            
                            # Regex para capturar valor: 1.200,50 ou 1200,50
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
                            found_title = None
                            
                            # Subir até 5 níveis procurando um link que pareça título
                            for _ in range(5):
                                if not container: break
                                
                                # Tentar achar link neste nível ou abaixo
                                if container.name == 'a':
                                    found_link = container
                                else:
                                    # Link com classe de titulo ou produto
                                    links = container.find_all('a', href=True)
                                    for l in links:
                                        # Heuristica: link tem texto razoavel e imagem perto?
                                        if len(l.get_text(strip=True)) > 5:
                                            found_link = l
                                            break
                                            
                                if found_link:
                                    break
                                container = container.parent
                                
                            if not found_link:
                                continue
                                
                            link = urljoin(website, found_link['href'])
                            title = found_link.get_text(strip=True)
                            
                            # Se o título for muito curto (ex: "Comprar"), tentar achar outro elemento de texto
                            if len(title) < 5 and container:
                                title_el = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'], class_=re.compile(r'title|name'))
                                if title_el:
                                    title = title_el.get_text(strip=True)
                            
                            if not title:
                                title = "Produto sem título"

                            # Adicionar resultado se tiver título e preço > 0
                            if price > 0:
                                # Evitar duplicatas (mesmo link)
                                if not any(r['link'] == link for r in supplier_results):
                                    supplier_results.append({
                                        'supplier_name': supplier_name,
                                        'title': title,
                                        'price': price,
                                        'price_formatted': f"R$ {price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                                        'link': link,
                                        'description': f"Encontrado em {supplier_name}"
                                    })
                        except Exception as e:
                            # print(f"Erro ao processar elemento: {e}")
                            continue
                            
                    # Se encontrou algo, parar de tentar outras URLs de busca neste fornecedor
                    if supplier_results:
                        break
            except Exception as e:
                # print(f"Erro ao acessar {url}: {e}")
                continue
                
        return supplier_results

    # Executar buscas em paralelo
    # Usar ThreadPoolExecutor para IO-bound tasks
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_supplier = {executor.submit(fetch_supplier, s): s for s in valid_suppliers}
        for future in concurrent.futures.as_completed(future_to_supplier):
            try:
                data = future.result()
                if data:
                    results.extend(data)
            except Exception as exc:
                print(f"Exceção ao buscar fornecedor: {exc}")

    # Ordenar por preço (menor para maior)
    # Filtrar resultados irrelevantes (preço muito baixo ou título nada a ver)
    # Aqui assumimos que o scraper funcionou bem.
    results.sort(key=lambda x: x['price'])
    
    return results
