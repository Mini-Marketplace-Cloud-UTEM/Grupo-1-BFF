from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    auth_service_url: str = "https://grupo2-identidadusuario.onrender.com"
    catalog_service_url: str = "https://grupo-3-catalogo.onrender.com"
    cart_service_url: str = "http://127.0.0.1:4011"
    orders_service_url: str = "http://127.0.0.1:4012"
    shipping_service_url: str = "http://127.0.0.1:4013"
    payments_service_url: str = "http://127.0.0.1:4014"
    reports_service_url: str = "https://grupo-7-reporter-a-bash-y-streaming-production.up.railway.app"

    # CORS: origenes permitidos para llamar al BFF desde el navegador.
    # `frontend_origins`: lista exacta separada por coma (dev local).
    # `frontend_origin_regex`: patron para los despliegues de Vercel (produccion
    # + previews de QA/Dev, cada uno con su subdominio). Asi restringimos a lo
    # nuestro sin romper ninguna URL de Vercel. Ambos configurables por env.
    frontend_origins: str = "http://localhost:5173,http://localhost:4173"
    frontend_origin_regex: str = r"https://.*\.vercel\.app"

    class Config:
        env_file = ".env"


settings = Settings()
