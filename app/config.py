from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    auth_service_url: str = "https://grupo2-identidadusuario.onrender.com"
    catalog_service_url: str = "https://grupo-3-catalogo.onrender.com"
    cart_service_url: str = "http://127.0.0.1:4011"
    orders_service_url: str = "http://127.0.0.1:4012"
    shipping_service_url: str = "http://127.0.0.1:4013"
    payments_service_url: str = "http://127.0.0.1:4014"
    reports_service_url: str = "https://grupo-7-reporter-a-bash-y-streaming-production.up.railway.app"

    class Config:
        env_file = ".env"


settings = Settings()
