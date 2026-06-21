from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    auth_service_url: str = "https://api-grupo2.onrender.com/api/v1"
    catalog_service_url: str = "http://127.0.0.1:4010"
    cart_service_url: str = "http://127.0.0.1:4011"
    orders_service_url: str = "http://127.0.0.1:4012"
    shipping_service_url: str = "http://127.0.0.1:4013"
    payments_service_url: str = "http://127.0.0.1:4014"
    reports_service_url: str = "http://127.0.0.1:4015"

    class Config:
        env_file = ".env"


settings = Settings()
