import os


class HoneyfileMonitor:

    def __init__(self, honeyfile_directory):

        self.honeyfile_directory = os.path.abspath(
            honeyfile_directory
        )

    def is_honeyfile(self, file_path):

        absolute_path = os.path.abspath(
            file_path
        )

        return absolute_path.startswith(
            self.honeyfile_directory
        )
