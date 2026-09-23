import re

with open('templates/components/sidebar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace url tags
content = content.replace("url 'personal:orden_trabajo'", "url 'campos:orden_trabajo'")
content = content.replace("request.resolver_match.app_name == 'personal' and request.resolver_match.url_name == 'orden_trabajo'", "request.resolver_match.app_name == 'campos' and request.resolver_match.url_name == 'orden_trabajo'")

# We need to move the mobile / desktop sidebar links from the Personal section to the Campo section.
# The desktop sidebar is grouped by `x-show="activeModule === 'personal'"` etc.
# In activeModule === 'campos', let's inject it.

# 1. Desktop sidebar (Lefthand Module Submenu)
campos_desktop = """          <div x-show="activeModule === 'campos'" x-transition:enter="transition-opacity ease-out duration-200" class="space-y-1">"""
campos_desktop_add = """
          <a
            href="{% url 'campos:orden_trabajo' %}"
            x-show="matchesSearch('Órdenes de Trabajo', 'orden tarea planificacion asignacion')"
            class="flex items-center px-2.5 py-2 text-xs rounded-xl transition-all duration-150 group cursor-pointer {% if request.resolver_match.app_name == 'campos' and request.resolver_match.url_name == 'orden_trabajo' %}bg-[#3D4A2A] text-white font-bold shadow-xs border border-[#5A6E3F]{% else %}text-[#C8D6BC] hover:bg-white/10 hover:text-white border border-transparent{% endif %}"
          >
            <span class="truncate flex-1">Órdenes de Trabajo</span>
          </a>"""
content = content.replace(campos_desktop, campos_desktop + campos_desktop_add)

# Now remove from personal_desktop
personal_desktop = """          <a
            href="{% url 'campos:orden_trabajo' %}"
            x-show="matchesSearch('Órdenes de Trabajo', 'orden tarea planificacion asignacion')"
            class="flex items-center px-2.5 py-2 text-xs rounded-xl transition-all duration-150 group cursor-pointer {% if request.resolver_match.app_name == 'campos' and request.resolver_match.url_name == 'orden_trabajo' %}bg-[#3D4A2A] text-white font-bold shadow-xs border border-[#5A6E3F]{% else %}text-[#C8D6BC] hover:bg-white/10 hover:text-white border border-transparent{% endif %}"
          >
            <span class="truncate flex-1">Órdenes de Trabajo</span>
          </a>"""
# wait, because I replaced `personal:` with `campos:`, the one currently inside personal module now looks like `personal_desktop` above.
# but I added it to campos_desktop. So it exists twice now.
# Instead of doing that, let's just do a manual string manipulation or regex.
