# Guía de contribución — Grupo 1 (BFF)

## Flujo de ramas

Tres ramas de larga vida:

| Rama   | Para qué | Despliegue |
|--------|----------|------------|
| `Dev`  | Integración diaria del equipo. | — |
| `QA`   | Validación / pruebas antes de producción. | — |
| `main` | Producción. Solo entra lo ya probado. | Render (auto-deploy) |

Promoción en un solo sentido:

```
feature/mi-cambio  →  Dev  →  QA  →  main
```

### Cómo trabajar una tarea

1. `git checkout Dev && git pull`.
2. `git checkout -b feature/lo-que-haces` (desde `Dev`).
3. Antes de subir, corre localmente lo mismo que el CI:
   ```bash
   pip install ruff
   ruff check .
   python -c "import app.main"
   docker build -t bff-ci .
   ```
4. Sube tu rama y abre un **Pull Request hacia `Dev`**.
5. El **CI** (GitHub Actions) corre en el PR: `ruff`, chequeo de import y build
   de la imagen Docker. Si sale ✗ rojo, arréglalo antes de pedir revisión.

### Promover

- **`Dev → QA`** por PR cuando algo está listo para probar.
- **`QA → main`** por PR cuando QA está OK. Al mergear, Render redespliega solo.

## Reglas de protección (GitHub → Settings → Branches)

En `main` y `QA`: requerir PR + check de CI (**build**) en verde; prohibir push directo.

> Render redespliega solo al actualizar `main`; **eso no es el CI**. El CI es el
> workflow de GitHub Actions que valida el código en cada push/PR.

## CORS / seguridad

El BFF ya no acepta `*`. Los orígenes permitidos salen de `app/config.py`
(`FRONTEND_ORIGINS` exactos + `FRONTEND_ORIGIN_REGEX` para `*.vercel.app`),
configurables por variable de entorno en Render. Ver `.env.example`.
