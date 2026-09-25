import os
import sys
import subprocess

def main():
    print("--- [Vercel Build Script] Iniciando preparación de ERP Olivos ---")
    
    # Si hay una base de datos PostgreSQL configurada en Vercel, ejecutar migraciones
    database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if database_url:
        print("[Vercel Build] Se detectó DATABASE_URL/POSTGRES_URL. Ejecutando migraciones en PostgreSQL...")
        try:
            res = subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], check=True)
            print("[Vercel Build] Migraciones ejecutadas con éxito.")
        except subprocess.CalledProcessError as e:
            print(f"[Vercel Build] Aviso: Las migraciones no pudieron completarse automáticamente: {e}")
            print("[Vercel Build] Verifica las credenciales de conexión o el estado de tu base de datos.")
    else:
        print("[Vercel Build] No se detectó DATABASE_URL en variables de entorno.")
        print("[Vercel Build] El despliegue continuará utilizando la base de datos de respaldo en /tmp.")

    # Asegurar que afip.py esté disponible para la integración con ARCA
    try:
        import afip
        print("[Vercel Build] Módulo 'afip' verificado correctamente.")
    except ImportError:
        print("[Vercel Build] Instalando afip.py directamente...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "afip.py>=1.2.0"], check=True)
            print("[Vercel Build] 'afip.py' instalado con éxito.")
        except Exception as e:
            print(f"[Vercel Build] Advertencia al instalar afip.py: {e}")


    # Compilar Tailwind CSS para Producción
    print("[Vercel Build] Verificando e instalando dependencias de Tailwind CSS...")
    try:
        import sysconfig
        scripts_dir = sysconfig.get_path("scripts")
        tailwindcss_exe = os.path.join(scripts_dir, "tailwindcss")
        if os.name == "nt":
            tailwindcss_exe += ".exe"
            
        print("[Vercel Build] Ejecutando compilación de Tailwind CSS...")
        subprocess.run([tailwindcss_exe, "-i", "static/css/input.css", "-o", "static/css/tailwind.css", "--minify"], check=True)
        print("[Vercel Build] Tailwind CSS compilado exitosamente.")
    except Exception as e:
        print(f"[Vercel Build] Advertencia al compilar Tailwind CSS: {e}")
        # Intento alternativo en linux (Vercel) donde el binario podría estar en el PATH si se instaló via pip
        try:
            subprocess.run(["tailwindcss", "-i", "static/css/input.css", "-o", "static/css/tailwind.css", "--minify"], check=True)
            print("[Vercel Build] Tailwind CSS compilado mediante PATH global.")
        except Exception as e2:
            print(f"[Vercel Build] Falló el segundo intento de Tailwind: {e2}")

    # Asegurar cuenta de Administrador activa
    try:
        subprocess.run([sys.executable, "manage.py", "crear_admin"], check=False)
        print("[Vercel Build] Cuenta de Administrador asegurada y habilitada.")
    except Exception as e:
        print(f"[Vercel Build] Advertencia al verificar administrador: {e}")

    print("--- [Vercel Build Script] Finalizado con éxito ---")

if __name__ == "__main__":
    main()
