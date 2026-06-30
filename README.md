# Grupo 1 — BFF (Backend for Frontend)

API que consume el frontend React del marketplace. Traduce y orquesta las
llamadas hacia los servicios de los grupos 2-8. El frontend **solo** habla
con este servicio — nunca directo con los demás.

Contrato completo (fuente de verdad): [`marketplace-contracts/services/group-1-bff/openapi.yaml`](https://github.com/Mini-Marketplace-Cloud-UTEM/marketplace-contracts/blob/main/services/group-1-bff/openapi.yaml).

## Stack

- Python 3.10 + FastAPI + Docker — mismo stack que usa Grupo 6 (el único
  grupo con un servicio real desplegado hasta ahora), y lo que pide la
  lista de tecnologías del curso (Render + Python).
- `httpx` para llamar a los servicios de los demás grupos (sin DB propia:
  el BFF no persiste nada, solo orquesta).

## Estado actual

- ✅ `/health` y manejo de errores estándar (`{code, message, details?, correlationId?}`).
- ✅ `/v1/auth/*` implementado contra Grupo 2 (única URL real en producción hoy, ver `registro-de-servicios.md`), con traducción snake_case → camelCase.
- ⚠️ `/v1/products*`, `/v1/categories`, `/v1/cart*`, `/v1/orders*` son **stubs** (501) — los servicios de Grupo 3/4/5 todavía no tienen URL real ni mock confirmado. Ver el TODO en cada router (`app/routers/`).
- ⚠️ Validación de JWT centralizada vía `POST /auth/validate` de Grupo 2 (`app/dependencies.py`), implementada pero todavía no se usa en ningún endpoint (los stubs no la requieren aún).

## Configuración y ejecución local

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
cp .env.example .env         # ajustar URLs según registro-de-servicios.md
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

## Docker

```bash
docker build -t grupo1-bff .
docker run -d -p 8000:8000 --env-file .env grupo1-bff
```

## Despliegue y CI/CD

> **Estado honesto para evaluación (E3 Cloud):** el BFF usa **deploy
> automatizado por plataforma** (auto-deploy nativo de Render al hacer push a
> `main`), **no un pipeline de CI/CD propio**. No existe `.github/workflows/` ni
> ninguna automatización de tests/lint previa al despliegue. Render construye la
> imagen a partir del `Dockerfile` en cada push; si el build de Docker falla, el
> deploy no se promueve y queda en línea la última versión sana. Eso es un
> *build check*, no una suite de CI. Se documenta tal cual es.

### 1. Cómo se despliega hoy

| Aspecto | Detalle |
|---|---|
| Plataforma | Render (`https://grupo-1-bff.onrender.com`) |
| Trigger | `git push` a `main` de este repo |
| Mecanismo | Render detecta el `Dockerfile`, construye la imagen y la levanta |
| Pasos automáticos | `docker build` (instala `requirements.txt`) → arranque `uvicorn app.main:app` en el puerto 8000 |
| Pasos manuales | Ninguno en el flujo normal |
| Build aprox. | ~2–5 min |

- **No hay `render.yaml`** en el repo: toda la configuración (variables de
  entorno, plan, comando de arranque) vive en el dashboard de Render. El deploy
  se hace **desde el `Dockerfile`**, no desde un buildpack.
- El contenedor expone y escucha en el **puerto 8000** (`EXPOSE 8000` +
  `--port 8000` en el `CMD`); Render está configurado para enrutar a ese puerto.
- **Plan free → *cold start*:** el servicio se duerme tras inactividad. La
  primera petición tras el sueño tarda varios segundos y puede parecer un error
  de red/CORS transitorio que se resuelve al reintentar. Hay una ruta raíz
  `GET/HEAD /` para que los health checks de Render no devuelvan 404 (commit
  `6db17f9`).
- El frontend (Vercel) llega al BFF por CORS, habilitado explícitamente en
  `app/main.py` (commit `08c2711`); sin eso el preflight `OPTIONS` falla.

### 2. ¿Hay CI (tests / lint automatizados)?

**No.** Estado verificado del repo:
- No existe `.github/workflows/` ni ningún otro runner de CI.
- No hay carpeta de tests ni `pytest` en `requirements.txt` — no hay nada que un
  CI pudiera ejecutar hoy.
- La única validación previa al deploy es que la **imagen Docker construya** en
  Render. Si falla, Render mantiene en línea la última versión que sí construyó.

> Mejora futura (no implementada): workflow de GitHub Actions que corra lint y
> tests (cuando existan) en cada PR antes del merge a `main`, e idealmente un
> `docker build` de validación.

### 3. Variables de entorno

Se configuran en el **dashboard de Render**, nunca en el repo (`.env` está en
`.gitignore`). Plantilla en [`.env.example`](.env.example). Son las URLs de los
servicios de los demás grupos que el BFF consume:

| Variable | Para qué |
|---|---|
| `AUTH_SERVICE_URL` | Grupo 2 (Auth / validación de JWT) |
| `CATALOG_SERVICE_URL` | Grupo 3 (Catálogo) |
| `CART_SERVICE_URL` | Grupo 4 (Carro / Checkout) |
| `ORDERS_SERVICE_URL` | Grupo 5 (Pedidos) |
| `SHIPPING_SERVICE_URL` | Grupo 6 (Despacho) |
| `PAYMENTS_SERVICE_URL` | Grupo 8 (Pagos) |
| `REPORTS_SERVICE_URL` | Grupo 7 (Reportería) |

Las URLs reales/vivas están en
`marketplace-contracts/registro-de-servicios.md`. Mientras un servicio diga
"pendiente" ahí, se apunta a su mock (Prism) o a `127.0.0.1`. Cambiar una
variable en Render requiere **redeploy** para tomar efecto.

### 4. Reproducir el deploy desde cero

**Local (con Docker, igual que Render):**
```bash
git clone https://github.com/Mini-Marketplace-Cloud-UTEM/Grupo-1-BFF.git
cd Grupo-1-BFF
cp .env.example .env          # ajustar URLs según registro-de-servicios.md
docker build -t grupo1-bff .
docker run -d -p 8000:8000 --env-file .env grupo1-bff
# Swagger: http://127.0.0.1:8000/docs
```

**Local (sin Docker):** ver [Configuración y ejecución local](#configuración-y-ejecución-local).

**Desplegar en Render desde cero:**
1. New → Web Service → conectar este repo. Render detecta el `Dockerfile`.
2. Configurar las variables de entorno de la tabla anterior.
3. Confirmar que el puerto del servicio sea 8000.
4. Deploy. A partir de ahí, cada push a `main` redeploya automáticamente.

### 5. Rollback

No hay rollback automatizado (no hay CI que lo gestione). Es **manual vía
dashboard de Render**: pestaña de Deploys → **Rollback** al deploy anterior, o
re-deploy de un commit previo. Alternativa por Git: `git revert <commit>` y push
a `main` dispara un nuevo deploy con el estado revertido.

## Próximos pasos

1. Implementar `/v1/products*` y `/v1/categories` contra el mock Prism de Grupo 3 (`marketplace-contracts/data-dictionary/contratos-mock.md`).
2. Implementar `/v1/cart*` contra Grupo 4.
3. Implementar `POST /v1/orders` llamando a `POST /v1/checkout` de Grupo 4 (no reimplementar la orquestación — ver `decisiones-ejecutivas-2026-06-19.md` #1).
4. Desplegar en Render y actualizar la fila propia en `marketplace-contracts/registro-de-servicios.md`.
