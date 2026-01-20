
import os

file_path = r"E:\celular\orcamento\assets\index-914650a4.js"
old_url = "https://horizons-cdn.hostinger.com/c87e5bd0-0873-4931-abc4-be3f368ff9a9/f740d32a6d28978657f2dcd73dc63cbc.png"
new_url = "/orcamento/logo.png"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if old_url in content:
        new_content = content.replace(old_url, new_url)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Logo URL replaced successfully.")
    else:
        print("Old logo URL not found in file.")
except Exception as e:
    print(f"Error: {e}")
