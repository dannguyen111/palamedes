from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('start/', views.start_chapter, name='start_chapter'), # New Path
]