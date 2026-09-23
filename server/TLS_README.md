# HTTPS en ALFA-Sentinel

Toda la comunicación **agente ↔ servidor** y **navegador ↔ consola** viaja cifrada con TLS (versión mínima 1.2).
El agente solo confía en la **CA propia** del despliegue, no en las CA de Windows ni en las comerciales.
Por eso, aunque alguien en la red intercepte el tráfico o se haga pasar por el servidor, el agente corta la conexión
antes de enviar su credencial.

## 1. Generar los certificados (una vez, en el servidor)

```powershell
cd server
.venv\Scripts\activate
pip install -r requirements.txt          # agrega 'cryptography'
python generar_certificados.py --ip 192.168.81.1
```

Usa la IP con la que los agentes llegan al servidor. Si hay varias, repite `--ip`, y para nombres usa `--dns`.

El script crea lo siguiente:

| Archivo | Qué es | Dónde va |
|---|---|---|
| `server/certs/ca.key` | Clave privada de la CA. **Es el secreto más importante.** | Solo en el servidor |
| `server/certs/ca.crt` | CA pública | Servidor, agentes y Vite |
| `server/certs/server.key` | Clave privada del servidor | Solo en el servidor |
| `server/certs/server.crt` | Certificado del servidor (825 días) | Solo en el servidor |
| `agent/certs/ca.crt` | Copia automática de la CA pública | En cada endpoint |

`server/certs/` y `agent/certs/` están en `.gitignore` y **no se suben a git**.

Si cambia la IP del servidor, ejecuta `python generar_certificados.py --ip <nueva> --force-server`.
La CA se conserva, así que los agentes ya instalados siguen funcionando.

## 2. Arrancar el servidor

```powershell
cd server
python run_server.py            # https://0.0.0.0:8000
```

No arranques el servidor con `uvicorn asgi:app ...` a mano: así se levanta en HTTP.
Para depurar sin TLS usa `python run_server.py --insecure-dev`, que solo escucha en 127.0.0.1.

Con TLS activo, el servidor además:

- marca la cookie de sesión como `Secure` y `SameSite=Strict`;
- envía las cabeceras HSTS, `X-Frame-Options: DENY`, `nosniff` y `no-store`.

## 3. Agente

```powershell
python main.py --enroll ABCD-EFGH --server https://192.168.81.1:8000
```

Por defecto, el agente busca la CA en `agent/certs/ca.crt`. Para usar otra ruta, pasa `--ca C:\ruta\ca.crt`
o define la variable de entorno `ALFA_SENTINEL_CA_FILE`.

El agente se niega a conectarse en estos casos:

- **URL `http://` hacia cualquier IP que no sea 127.0.0.1.** El agente no llega a enviar nada.
- **Certificado firmado por otra CA, o IP que no figura en el certificado.** El agente muestra
  «certificado TLS NO confiable», no envía la credencial y no ejecuta ninguna orden de aislamiento.

## 4. Consola web (Vite en desarrollo)

`npm run dev` detecta `server/certs/` y hace lo siguiente:

- Sirve la consola en **https://localhost:5173**. La primera vez, el navegador muestra un aviso porque no conoce la CA.
  Para evitarlo, importa `server/certs/ca.crt` en «Entidades de certificación raíz de confianza» de Windows,
  **solo en el equipo del administrador**.
- Hace de proxy hacia `https://localhost:8000` y verifica el certificado contra la misma CA.
  Si el backend está en otra dirección, defínela con `ALFA_BACKEND_URL`.

## 5. Pruebas automáticas

Las pruebas de `tests/` siguen levantando `uvicorn main:app` en `http://127.0.0.1:<puerto>`.
Eso está permitido a propósito, porque el tráfico por loopback no sale del equipo.
