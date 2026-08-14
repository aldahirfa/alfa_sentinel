import os


class HoneyfileMonitor:

    def __init__(self, honeyfile_directory, known_paths=None):

        self.honeyfile_directory = os.path.abspath(
            honeyfile_directory
        )

        # Rutas reales de honeyfiles creados/reportados por este
        # agente (ver agent/honeyfile_deployer.py) -- pueden vivir en
        # cualquier carpeta (Desktop, Documents, ...), no solo dentro
        # de la carpeta local 'honeyfiles/' que se usaba antes de que
        # existiera el despliegue por plantilla.
        self.known_paths = {
            os.path.abspath(p) for p in (known_paths or [])
        }

    def is_honeyfile(self, file_path):

        absolute_path = os.path.abspath(
            file_path
        )

        if absolute_path in self.known_paths:
            return True

        return absolute_path.startswith(
            self.honeyfile_directory
        )
