"""Crée une sauvegarde horodatée de la base MySQL configurée."""
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Exporte la base MySQL configurée dans le dossier de sauvegarde."

    def handle(self, *args, **options):
        database = settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.mysql":
            raise CommandError("La sauvegarde requiert une base de données MySQL.")
        if not database.get("NAME") or not database.get("USER"):
            raise CommandError("DB_NAME et DB_USER doivent être configurés.")

        backup_dir = Path(settings.BACKUP_DIR)
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = backup_dir / f"supplier_management_{timestamp}.sql"
        arguments = [
            settings.MYSQLDUMP_PATH,
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            "--default-character-set=utf8mb4",
            "--host",
            database.get("HOST") or "localhost",
            "--port",
            str(database.get("PORT") or "3306"),
            "--user",
            database["USER"],
            "--databases",
            database["NAME"],
        ]
        environment = os.environ.copy()
        password = database.get("PASSWORD")
        if password:
            environment["MYSQL_PWD"] = password

        created_backup = False
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            with backup_path.open("xb") as output_file:
                created_backup = True
                result = subprocess.run(
                    arguments,
                    stdout=output_file,
                    stderr=subprocess.PIPE,
                    env=environment,
                    check=False,
                    timeout=3600,
                )
        except subprocess.TimeoutExpired as exc:
            if created_backup:
                backup_path.unlink(missing_ok=True)
            raise CommandError("mysqldump a dépassé le délai maximal d'une heure.") from exc
        except OSError as exc:
            if created_backup:
                backup_path.unlink(missing_ok=True)
            raise CommandError(
                f"Impossible d'exécuter mysqldump ou d'écrire la sauvegarde : {exc}"
            ) from exc

        if result.returncode:
            backup_path.unlink(missing_ok=True)
            details = result.stderr.decode("utf-8", errors="replace").strip()
            message = details or "aucun détail fourni"
            raise CommandError(
                f"mysqldump a échoué avec le code {result.returncode} : {message}"
            )
        if backup_path.stat().st_size == 0:
            backup_path.unlink(missing_ok=True)
            raise CommandError("mysqldump a terminé sans produire de données.")

        return str(backup_path.resolve())
