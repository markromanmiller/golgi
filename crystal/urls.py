from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('rank/', views.rank, name='rank'),
    path('make_cites/<int:publication_id>/', views.make_cites, name='make_cites'),
    path('make_cited_by/<int:publication_id>', views.make_cited_by, name='make_cited_by')
]