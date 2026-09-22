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

    print("--- [Vercel Build Script] Finalizado con éxito ---")

if __name__ == "__main__":
    main()
