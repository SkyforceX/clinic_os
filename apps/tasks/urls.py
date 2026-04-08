from django.urls import path
from apps.tasks.web.views.task_views import (
    ajax_load_more_done, ajax_move_stage, ajax_reorder,
    pipeline_board, task_create, task_detail,
)

app_name = "tasks"

urlpatterns = [
    path("",                               pipeline_board,      name="board"),
    path("new/",                           task_create,         name="create"),
    path("<int:task_id>/",                 task_detail,         name="detail"),
    path("<int:task_id>/move/",            ajax_move_stage,     name="ajax_move"),
    path("api/reorder/",                   ajax_reorder,        name="ajax_reorder"),
    path("api/load-more/",                 ajax_load_more_done, name="ajax_load_more"),
]
