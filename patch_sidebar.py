import re

with open(r'c:\Users\JosuG\Downloads\Erp Olivos\templates\components\sidebar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Desktop
block1_old = """            <a
              href="{% url 'inventario:insumos_list' %}"
              x-show="matchesSearch('Stock de Insumos', 'fitosanitarios fertilizantes deposito existencia')"
              class="flex items-center px-2.5 py-2 text-xs rounded-xl transition-all duration-150 group cursor-pointer {% if request.resolver_match.app_name == 'inventario' and request.resolver_match.url_name in 'insumos_list insumo_kardex' %}bg-[#3D4A2A] text-white font-bold shadow-xs border border-[#5A6E3F]{% else %}text-[#C8D6BC] hover:bg-white/10 hover:text-white border border-transparent{% endif %}"
            >
              <span class="truncate flex-1">Stock de Insumos</span>
            </a>"""

block1_new = block1_old + """

            <a
              href="{% url 'inventario:herramientas_list' %}"
              x-show="matchesSearch('Stock de Herramientas', 'herramientas panol prestamos')"
              class="flex items-center px-2.5 py-2 text-xs rounded-xl transition-all duration-150 group cursor-pointer {% if 'herramientas' in request.path %}bg-[#3D4A2A] text-white font-bold shadow-xs border border-[#5A6E3F]{% else %}text-[#C8D6BC] hover:bg-white/10 hover:text-white border border-transparent{% endif %}"
            >
              <span class="truncate flex-1">Stock de Herramientas</span>
            </a>

            <a
              href="{% url 'inventario:rodados_list' %}"
              x-show="matchesSearch('Parque de Rodados', 'maquinas rodados vehiculos mantenimiento')"
              class="flex items-center px-2.5 py-2 text-xs rounded-xl transition-all duration-150 group cursor-pointer {% if 'rodados' in request.path %}bg-[#3D4A2A] text-white font-bold shadow-xs border border-[#5A6E3F]{% else %}text-[#C8D6BC] hover:bg-white/10 hover:text-white border border-transparent{% endif %}"
            >
              <span class="truncate flex-1">Parque de Rodados</span>
            </a>"""

content = content.replace(block1_old, block1_new)

# 2. Mobile
block2_old = """            <a
              href="{% url 'inventario:insumos_list' %}"
              class="flex items-center px-3.5 py-2.5 text-xs rounded-xl font-medium {% if request.resolver_match.app_name == 'inventario' and request.resolver_match.url_name in 'insumos_list insumo_kardex' %}bg-[#3D4A2A] text-white font-bold border border-[#5A6E3F]{% else %}text-[#C8D6BC] bg-white/5 hover:bg-white/10{% endif %}"
            >
              <span>Stock de Insumos</span>
            </a>"""

block2_new = block2_old + """
            <a
              href="{% url 'inventario:herramientas_list' %}"
              class="flex items-center px-3.5 py-2.5 text-xs rounded-xl font-medium {% if 'herramientas' in request.path %}bg-[#3D4A2A] text-white font-bold border border-[#5A6E3F]{% else %}text-[#C8D6BC] bg-white/5 hover:bg-white/10{% endif %}"
            >
              <span>Stock de Herramientas</span>
            </a>
            <a
              href="{% url 'inventario:rodados_list' %}"
              class="flex items-center px-3.5 py-2.5 text-xs rounded-xl font-medium {% if 'rodados' in request.path %}bg-[#3D4A2A] text-white font-bold border border-[#5A6E3F]{% else %}text-[#C8D6BC] bg-white/5 hover:bg-white/10{% endif %}"
            >
              <span>Parque de Rodados</span>
            </a>"""

content = content.replace(block2_old, block2_new)

with open(r'c:\Users\JosuG\Downloads\Erp Olivos\templates\components\sidebar.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Sidebar updated successfully!")
