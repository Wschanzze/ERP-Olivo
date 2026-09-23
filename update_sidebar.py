import re

with open('templates/components/sidebar.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Desktop Menu Extract
desktop_link = re.search(r'(<a[^>]*href="{% url \'campos:orden_trabajo\' %}"[^>]*>.*?</a>)', html, re.DOTALL)
if desktop_link:
    link_html = desktop_link.group(1)
    # Remove from everywhere
    html = html.replace(link_html, "")
    
    # Insert into campo (desktop)
    # Look for <!-- ── CAMPO & OPERACIONES ── -->\n        <template x-if="activeModule === 'campo'">\n          <div class="space-y-1">
    target_desktop = """        <!-- ── CAMPO & OPERACIONES ── -->
        <template x-if="activeModule === 'campo'">
          <div class="space-y-1">"""
    
    html = html.replace(target_desktop, target_desktop + "\n" + link_html)
    
# Mobile Menu Extract
# We might have another link for mobile! Let's check for it.
mobile_link = re.search(r'(<a[^>]*href="{% url \'campos:orden_trabajo\' %}"[^>]*class="flex items-center px-3.5 py-2.5.*?</a>)', html, re.DOTALL)
if mobile_link:
    link_html = mobile_link.group(1)
    html = html.replace(link_html, "")
    
    target_mobile = """        <!-- Vistas Campo -->
        <template x-if="activeModule === 'campo'">
          <div class="space-y-1.5">"""
    html = html.replace(target_mobile, target_mobile + "\n" + link_html)

# Spotlight Extract
# Change the module label inside spotlight from 'Personal' to 'Campo'
html = html.replace(
    "x-show=\"matchesSpotlight({title: 'Órdenes de Trabajo', module: 'Personal', tags: 'tareas planificacion ordenes'})\"",
    "x-show=\"matchesSpotlight({title: 'Órdenes de Trabajo', module: 'Campo', tags: 'tareas planificacion ordenes'})\""
)
html = html.replace(
    "@click=\"spotlightOpen = false; selectModule('personal')\"",
    "@click=\"spotlightOpen = false; selectModule('campo')\""
)
html = html.replace(
    "<span class=\"text-[10px] text-[#8FA872] font-mono\">Personal</span>",
    "<span class=\"text-[10px] text-[#8FA872] font-mono\">Campo</span>"
)

with open('templates/components/sidebar.html', 'w', encoding='utf-8') as f:
    f.write(html)
    
print("Sidebar Updated!")
