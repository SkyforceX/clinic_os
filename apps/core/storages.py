import os

from django.core.files.storage import FileSystemStorage
from django.conf import settings

# cho phép ghi đè
class ResultsStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        location = getattr(settings, "RESULTS_ROOT",
                           os.path.join(settings.BASE_DIR, "data", "results"))
        super().__init__(location=location, base_url=None, *args, **kwargs)

    def get_available_name(self, name, max_length=None):
        # Nếu đã tồn tại thì xóa để luôn ghi đè
        if self.exists(name):
            self.delete(name)
        return name
