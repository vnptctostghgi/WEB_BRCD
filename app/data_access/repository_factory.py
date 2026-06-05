from app.data_access.app_repository import AppRepository
from app.data_access.supabase_repository import SupabaseRepository
from app.settings import Settings


def build_repository(settings: Settings):
    if settings.app_database_backend.lower() == "supabase":
        return SupabaseRepository(
            settings.supabase_rest_url,
            settings.supabase_secret_key.get_secret_value(),
        )
    return AppRepository(settings.app_database_path)
