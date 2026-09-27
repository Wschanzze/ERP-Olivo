import re

with open("templates/components/sidebar.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Reemplazar el Carrusel Horizontal de Modulos (Lineas 572-619 aprox)
start_marker = "<!-- Carrusel Horizontal de Módulos -->"
end_marker = "<!-- Lista Deslizable de Vistas Móviles -->"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("No se encontraron los marcadores")
    exit(1)

new_carrusel = """<!-- Carrusel Horizontal de Módulos -->
    <div class="flex-shrink-0 bg-[#161F0E] border-b border-[#2C381D] px-2 py-3">
      <div class="flex items-start space-x-2 overflow-x-auto pb-1 custom-scrollbar px-1 justify-center min-w-min">
        <!-- 1. Tableros -->
        <button type="button" @click="activeModule = 'tableros'" class="flex-shrink-0 w-16 flex flex-col items-center justify-center transition-all duration-150 cursor-pointer group bg-transparent border-0 select-none">
          <svg class="w-8 h-8 transition-all duration-150" :class="activeModule === 'tableros' ? 'text-[#E5B842] scale-110 opacity-100 drop-shadow-[0_2px_10px_rgba(229,184,66,0.35)]' : 'text-[#8FA872]/80 opacity-70 group-hover:text-[#E5B842] group-hover:opacity-100'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
          <span class="text-[10px] leading-none mt-1.5 tracking-tight transition-colors" :class="activeModule === 'tableros' ? 'text-white font-bold' : 'text-[#8FA872]/70 group-hover:text-white font-medium'">Tableros</span>
        </button>

        <!-- 2. Campo -->
        {% if not user.is_authenticated or user.is_admin_general or user.puede_ver_campo %}
        <button type="button" @click="activeModule = 'campo'" class="flex-shrink-0 w-16 flex flex-col items-center justify-center transition-all duration-150 cursor-pointer group bg-transparent border-0 select-none">
          <svg class="w-8 h-8 transition-all duration-150" :class="activeModule === 'campo' ? 'text-[#4ADE80] scale-110 opacity-100 drop-shadow-[0_2px_10px_rgba(74,222,128,0.35)]' : 'text-[#8FA872]/80 opacity-70 group-hover:text-[#4ADE80] group-hover:opacity-100'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
          <span class="text-[10px] leading-none mt-1.5 tracking-tight transition-colors" :class="activeModule === 'campo' ? 'text-white font-bold' : 'text-[#8FA872]/70 group-hover:text-white font-medium'">Campo</span>
        </button>
        {% endif %}

        <!-- 3. Finanzas -->
        {% if not user.is_authenticated or user.is_admin_general or user.puede_ver_finanzas %}
        <button type="button" @click="activeModule = 'finanzas'" class="flex-shrink-0 w-16 flex flex-col items-center justify-center transition-all duration-150 cursor-pointer group bg-transparent border-0 select-none">
          <svg class="w-8 h-8 transition-all duration-150" :class="activeModule === 'finanzas' ? 'text-[#34D399] scale-110 opacity-100 drop-shadow-[0_2px_10px_rgba(52,211,153,0.35)]' : 'text-[#8FA872]/80 opacity-70 group-hover:text-[#34D399] group-hover:opacity-100'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span class="text-[10px] leading-none mt-1.5 tracking-tight transition-colors" :class="activeModule === 'finanzas' ? 'text-white font-bold' : 'text-[#8FA872]/70 group-hover:text-white font-medium'">Finanzas</span>
        </button>
        {% endif %}

        <!-- 4. Personal -->
        {% if not user.is_authenticated or user.is_admin_general or user.puede_ver_personal %}
        <button type="button" @click="activeModule = 'personal'" class="flex-shrink-0 w-16 flex flex-col items-center justify-center transition-all duration-150 cursor-pointer group bg-transparent border-0 select-none">
          <svg class="w-8 h-8 transition-all duration-150" :class="activeModule === 'personal' ? 'text-[#A3E635] scale-110 opacity-100 drop-shadow-[0_2px_10px_rgba(163,230,53,0.35)]' : 'text-[#8FA872]/80 opacity-70 group-hover:text-[#A3E635] group-hover:opacity-100'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span class="text-[10px] leading-none mt-1.5 tracking-tight transition-colors" :class="activeModule === 'personal' ? 'text-white font-bold' : 'text-[#8FA872]/70 group-hover:text-white font-medium'">Personal</span>
        </button>
        {% endif %}

        <!-- 5. Almazara -->
        {% if not user.is_authenticated or user.is_admin_general or user.puede_ver_almazara %}
        <button type="button" @click="activeModule = 'almazara'" class="flex-shrink-0 w-16 flex flex-col items-center justify-center transition-all duration-150 cursor-pointer group bg-transparent border-0 select-none">
          <svg class="w-8 h-8 transition-all duration-150" :class="activeModule === 'almazara' ? 'text-[#FBBF24] scale-110 opacity-100 drop-shadow-[0_2px_10px_rgba(251,191,36,0.35)]' : 'text-[#8FA872]/80 opacity-70 group-hover:text-[#FBBF24] group-hover:opacity-100'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          <span class="text-[10px] leading-none mt-1.5 tracking-tight transition-colors" :class="activeModule === 'almazara' ? 'text-white font-bold' : 'text-[#8FA872]/70 group-hover:text-white font-medium'">Almazara</span>
        </button>
        {% endif %}
      </div>
    </div>

    """

content = content[:start_idx] + new_carrusel + content[end_idx:]

# 2. Remover Emojis del texto en la seccion MOVIL
# Para asegurarnos de no borrar codigo HTML o iconos de otra parte, 
# solo limpiamos la sección móvil.
mobile_nav_idx = content.find('<!-- Lista Deslizable de Vistas Móviles -->')
end_mobile_nav_idx = content.find('<!-- Pie Móvil -->')

if mobile_nav_idx != -1 and end_mobile_nav_idx != -1:
    mobile_nav = content[mobile_nav_idx:end_mobile_nav_idx]
    
    emoji_pattern = re.compile(
        "["
        u"\U0001f600-\U0001f64f"  # emoticons
        u"\U0001f300-\U0001f5ff"  # symbols & pictographs
        u"\U0001f680-\U0001f6ff"  # transport & map symbols
        u"\U0001f700-\U0001f77f"  # alchemical symbols
        u"\U0001f780-\U0001f7ff"  # Geometric Shapes Extended
        u"\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
        u"\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
        u"\U0001fa00-\U0001fa6f"  # Chess Symbols
        u"\u2600-\u27bf"          # misc symbols and dingbats
        "]+", flags=re.UNICODE)
    
    mobile_nav = emoji_pattern.sub('', mobile_nav)
    mobile_nav = mobile_nav.replace('<span> ', '<span>')
    mobile_nav = mobile_nav.replace('<span>  ', '<span>')
    
    content = content[:mobile_nav_idx] + mobile_nav + content[end_mobile_nav_idx:]

with open("templates/components/sidebar.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Exito")
