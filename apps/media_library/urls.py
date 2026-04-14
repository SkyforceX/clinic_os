from django.urls import path

from apps.media_library import views

app_name = "media_library"

urlpatterns = [
    path("",                      views.index,              name="index"),
    path("upload/",               views.upload,             name="upload"),
    path("upload/quill-image/",   views.upload_quill_image, name="upload_quill_image"),
    path("delete/<int:pk>/",      views.delete_file,        name="delete"),
    path("detail/<int:pk>/",      views.file_detail,        name="detail"),
    path("list.json",               views.list_json,          name="list_json"),
]
