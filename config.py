from dotenv import load_dotenv
import os
from typing import Optional, List

# Загрузка переменных окружения из .env файла
load_dotenv()

TG_TOKEN: Optional[str] = os.environ.get("TG_TOKEN")
ADMIN_IDS: List[int] = [int(x) for x in os.environ.get("ADMIN_IDS", "").split()]


