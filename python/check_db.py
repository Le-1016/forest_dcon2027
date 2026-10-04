import os

import psycopg
import torch

with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT mission_id FROM missions ORDER BY id LIMIT 1"
        )
        mission_id = cursor.fetchone()[0]

print(f"FOREST Python connected to PostgreSQL: {mission_id}")
print(
    f"PyTorch {torch.__version__}: "
    f"tensor sum = {torch.tensor([1, 2, 3]).sum().item()}"
)
