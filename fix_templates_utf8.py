import os

def replace_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = False
    
    if "personal:orden_trabajo" in content:
        content = content.replace("personal:orden_trabajo", "campos:orden_trabajo")
        modified = True
        
    if "app_name == 'personal' and request.resolver_match.url_name == 'orden_trabajo'" in content:
        content = content.replace("app_name == 'personal' and request.resolver_match.url_name == 'orden_trabajo'", "app_name == 'campos' and request.resolver_match.url_name == 'orden_trabajo'")
        modified = True
        
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            replace_in_file(os.path.join(root, file))

print("Done replacing.")
