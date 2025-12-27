from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('points/submit/', views.submit_points, name='submit_points'),
    path('points/assign/', views.assign_points, name='assign_points'),
]