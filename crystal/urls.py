from django.urls import path

from . import views

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('make_cites/<int:publication_id>/', views.make_cites, name='make_cites'),
    path('make_cited_by/<int:publication_id>/', views.make_cited_by, name='make_cited_by'),
    path('show_pdf/<int:publication_id>/', views.show_pdf, name="show_pdf"),
    path('pub_status/<int:publication_pk>/<status>/', views.pub_status, name="pub_status"),
    path('pub/<int:publication_pk>/', views.pub_page, name="pub_page"),
    path('tabbed/', views.tabbed, name="tabbed")
]