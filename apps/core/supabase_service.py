"""
Servicio de Integración con Supabase Auth (GoTrue API).
Maneja autenticación, registro, administración y sincronización de usuarios con Supabase.
"""

import json
import logging
import urllib.request
import urllib.error
from django.conf import settings

logger = logging.getLogger(__name__)


class SupabaseAuthService:
    @classmethod
    def get_config(cls):
        url = getattr(settings, 'SUPABASE_URL', '').rstrip('/')
        anon_key = getattr(settings, 'SUPABASE_ANON_KEY', '')
        secret_key = getattr(settings, 'SUPABASE_SECRET_KEY', '')
        return url, anon_key, secret_key

    @classmethod
    def is_configured(cls) -> bool:
        url, anon_key, _ = cls.get_config()
        return bool(url and anon_key)

    @classmethod
    def _make_request(cls, endpoint: str, method: str = 'GET', data: dict = None, use_secret: bool = False, timeout: int = 10):
        url, anon_key, secret_key = cls.get_config()
        if not url:
            return False, None, "Supabase no está configurado (falta SUPABASE_URL)."

        api_key = secret_key if use_secret and secret_key else anon_key
        if not api_key:
            return False, None, "Clave de API de Supabase no configurada."

        full_url = f"{url}/auth/v1/{endpoint.lstrip('/')}"
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if use_secret and secret_key:
            headers['Authorization'] = f"Bearer {secret_key}"
        elif anon_key:
            headers['Authorization'] = f"Bearer {anon_key}"

        body_bytes = None
        if data is not None:
            body_bytes = json.dumps(data).encode('utf-8')

        req = urllib.request.Request(full_url, data=body_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.getcode()
                response_text = response.read().decode('utf-8')
                result_data = json.loads(response_text) if response_text else {}
                return True, result_data, None
        except urllib.error.HTTPError as e:
            try:
                err_text = e.read().decode('utf-8')
                err_json = json.loads(err_text)
                msg = err_json.get('msg') or err_json.get('error_description') or err_json.get('message') or str(e)
            except Exception:
                msg = str(e)
            logger.warning(f"Supabase HTTP error {e.code} on {endpoint}: {msg}")
            return False, None, msg
        except urllib.error.URLError as e:
            logger.error(f"Error de conexión con Supabase en {endpoint}: {e.reason}")
            return False, None, f"Error de conexión con el servidor de autenticación: {e.reason}"
        except Exception as e:
            logger.error(f"Excepción inesperada en llamada a Supabase {endpoint}: {e}")
            return False, None, str(e)

    @classmethod
    def sign_in(cls, email: str, password: str):
        """
        Autentica un usuario con email y contraseña en Supabase Auth.
        Retorna (exito, datos_usuario, mensaje_error).
        """
        if not cls.is_configured():
            return False, None, "Supabase no está configurado."

        payload = {
            'email': email.strip().lower(),
            'password': password,
        }
        success, data, err = cls._make_request('token?grant_type=password', method='POST', data=payload)
        if not success:
            if err and ('invalid login credentials' in err.lower() or 'invalid_grant' in err.lower()):
                err = "Correo electrónico o contraseña incorrectos."
            elif err and 'email not confirmed' in err.lower():
                err = "La dirección de correo electrónico aún no ha sido confirmada en Supabase."
            return False, None, err

        user_obj = data.get('user', {})
        user_info = {
            'supabase_uid': user_obj.get('id'),
            'email': user_obj.get('email', '').strip().lower(),
            'access_token': data.get('access_token'),
            'refresh_token': data.get('refresh_token'),
            'user_metadata': user_obj.get('user_metadata', {}) or {},
        }
        return True, user_info, None

    @classmethod
    def admin_create_user(cls, email: str, password: str, rol: str = 'OPERARIO', first_name: str = '', last_name: str = '', finca_id=None):
        """
        Crea un usuario confirmado directamente en Supabase mediante la API de administración (Secret Key).
        Retorna (exito, datos_usuario, mensaje_error).
        """
        metadata = {
            'rol': rol,
            'first_name': first_name,
            'last_name': last_name,
            'email_verified': True,
        }
        if finca_id:
            metadata['finca_id'] = finca_id

        payload = {
            'email': email.strip().lower(),
            'password': password,
            'email_confirm': True,
            'user_metadata': metadata,
        }
        success, data, err = cls._make_request('admin/users', method='POST', data=payload, use_secret=True)
        if not success:
            return False, None, err

        user_info = {
            'supabase_uid': data.get('id'),
            'email': data.get('email', '').strip().lower(),
            'user_metadata': data.get('user_metadata', {}) or {},
        }
        return True, user_info, None

    @classmethod
    def admin_update_user_password(cls, supabase_uid: str, new_password: str):
        """Actualiza la contraseña de un usuario en Supabase."""
        payload = {'password': new_password}
        success, data, err = cls._make_request(f'admin/users/{supabase_uid}', method='PUT', data=payload, use_secret=True)
        return success, data, err

    @classmethod
    def admin_delete_user(cls, supabase_uid: str):
        """Elimina un usuario en Supabase Auth."""
        success, data, err = cls._make_request(f'admin/users/{supabase_uid}', method='DELETE', use_secret=True)
        return success, err

    @classmethod
    def recover_password_email(cls, email: str):
        """Solicita el envío de un correo de recuperación de contraseña vía Supabase."""
        payload = {'email': email.strip().lower()}
        success, data, err = cls._make_request('recover', method='POST', data=payload)
        return success, err
