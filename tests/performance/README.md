# Prueba de rendimiento de navegación

Esta prueba mide las APIs que utiliza la consola React al entrar a cada módulo. Después del inicio de sesión solo ejecuta peticiones `GET`; el propio login sí actualiza `last_login_at`, igual que un inicio de sesión normal en la consola.

## 1. Preparación

Levanta normalmente el backend FastAPI y asegúrate de que PostgreSQL esté disponible.

```bash
cd server
uvicorn main:app --reload
```

En otra terminal, desde la raíz del repositorio, ejecuta el benchmark. Puedes pasar las credenciales por argumentos:

```bash
python tests/performance/benchmark_navigation.py --username TU_USUARIO --password "TU_PASSWORD"
```

O evitar que la contraseña quede escrita en el historial del terminal mediante variables de entorno.

### PowerShell

```powershell
$env:ALFA_TEST_USER="TU_USUARIO"
$env:ALFA_TEST_PASSWORD="TU_PASSWORD"
python tests/performance/benchmark_navigation.py
```

## 2. Medición directa del backend

La configuración por defecto usa:

```text
http://127.0.0.1:8000
```

Esto mide FastAPI + consultas PostgreSQL sin incluir Vite ni el navegador.

Se realizan 2 peticiones de calentamiento y luego 10 muestras por endpoint. Para aumentar las muestras:

```bash
python tests/performance/benchmark_navigation.py --runs 30 --warmup 3
```

## 3. Medición a través de Vite

Con el frontend levantado:

```bash
cd frontend
npm run dev
```

Ejecuta:

```bash
python tests/performance/benchmark_navigation.py --base-url http://127.0.0.1:5173
```

La diferencia entre `:8000` y `:5173` permite detectar si el proxy de desarrollo añade una demora relevante.

## 4. Guardar evidencia

Para guardar los resultados en JSON:

```bash
python tests/performance/benchmark_navigation.py --runs 30 --json-out rendimiento_backend.json
python tests/performance/benchmark_navigation.py --base-url http://127.0.0.1:5173 --runs 30 --json-out rendimiento_vite.json
```

El archivo contiene mediana, p95, promedio, mínimo, máximo y errores por endpoint.

## 5. Cómo interpretar los resultados

La clasificación mostrada por el script es únicamente diagnóstica, no un requisito formal del proyecto:

- hasta 200 ms: rápido;
- 200–500 ms: aceptable;
- 500–1000 ms: lento;
- más de 1000 ms: muy lento.

Para decidir qué optimizar se debe observar principalmente **p95**, no una sola ejecución. Si `:8000` ya es lento, el problema está principalmente en backend/BD. Si `:8000` es rápido pero la navegación visual continúa tardando, el foco pasa al frontend: recargas al montar páginas, caché, prefetch y renderizado.

## Pantallas cubiertas

- Dashboard (overview y serie de actividad)
- Endpoints
- Alertas
- Incidentes
- Honeyfiles
- Reglas heurísticas
- Acciones de respuesta
- Reportes
- Administración (usuarios, configuración y auditoría)
- Perfil
- Poll global de alertas abiertas
