from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    auth_service_url: str = "https://grupo2-identidadusuario.onrender.com"
    catalog_service_url: str = "https://grupo-3-catalogo.onrender.com"
    cart_service_url: str = "https://g4-carrito-checkout-inventario-y.onrender.com"
    orders_service_url: str = "https://grupo5-pedidos-mock-kdyl.onrender.com"
    shipping_service_url: str = "https://g6-despacho.onrender.com"
    payments_service_url: str = "https://g8-pagos-y-notificaciones.onrender.com"
    reports_service_url: str = "https://g7-reporteria-bash-streaming-dev.onrender.com"

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
