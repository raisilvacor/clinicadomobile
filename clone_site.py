import requests
import os
import re
from urllib.parse import urljoin

url = "https://envio.oficinadocelular.com.br/?utm_source=ig&utm_medium=social&utm_content=link_in_bio&fbclid=PAb21jcAPbUqZleHRuA2FlbQIxMQBzcnRjBmFwcF9pZA81NjcwNjczNDMzNTI0MjcAAafE3eNtWfN3iMgt2etVVJtOA03YpaI5VGiseLlvPjdjNvK1_iwy0PuhIwgG0Q_aem_0fFeaAtL35bT68csy_AkeA"
base_url = "https://envio.oficinadocelular.com.br/"
output_dir = "orcamento"
assets_dir = os.path.join(output_dir, "assets")

if not os.path.exists(assets_dir):
    os.makedirs(assets_dir)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def download_file(file_url, local_path):
    try:
        print(f"Baixando asset: {file_url}")
        r = requests.get(file_url, headers=headers)
        r.raise_for_status()
        with open(local_path, 'wb') as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"Falha ao baixar {file_url}: {e}")
        return False

try:
    print(f"Baixando HTML: {url}")
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    html_content = response.text
    
    # Regex to find assets in /assets/ folder
    # Matches src="/assets/..." or href="/assets/..."
    asset_pattern = re.compile(r'(src|href)="(/assets/[^"]+)"')
    
    # Find all matches
    matches = asset_pattern.findall(html_content)
    
    # Deduplicate matches
    assets_to_download = set([m[1] for m in matches])
    
    # Also look for vite.svg
    if '/vite.svg' in html_content:
        assets_to_download.add('/vite.svg')

    print(f"Encontrados {len(assets_to_download)} assets.")
    
    for asset_path in assets_to_download:
        # asset_path is like /assets/foo.js or /vite.svg
        full_url = urljoin(base_url, asset_path)
        
        # Determine local filename
        filename = os.path.basename(asset_path)
        
        if asset_path.startswith('/assets/'):
            local_file_path = os.path.join(assets_dir, filename)
            relative_path_in_html = f"assets/{filename}"
        else:
            # root files like vite.svg
            local_file_path = os.path.join(output_dir, filename)
            relative_path_in_html = filename
            
        if download_file(full_url, local_file_path):
            # Replace in HTML
            # We replace the exact string found in the html (e.g. /assets/foo.js) with the relative path
            html_content = html_content.replace(asset_path, relative_path_in_html)
            
    # Remove the base tag if I added it previously (or don't add it this time)
    # The previous script added it, but here we are starting fresh from response.text
    
    # Save modified HTML
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print("Clone concluído com assets locais.")

except Exception as e:
    print(f"Erro geral: {e}")
