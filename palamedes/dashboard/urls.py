from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('points/', views.points_hub, name='points_hub'),
    path('points/submit/', views.submit_points, name='submit_points'),
    path('points/assign/', views.assign_points, name='assign_points'),
    path('inbox/', views.inbox, name='inbox'),
    path('points/manage/<int:pk>/', views.manage_point_request, name='manage_point'),
    path('ledger/', views.chapter_ledger, name='chapter_ledger'),
    path('dues/', views.dues_dashboard, name='dues_dashboard'),
    path('dues/manage/', views.manage_dues_creation, name='manage_dues_creation'),
    path('dues/pay/<int:pk>/', views.pay_due, name='pay_due'),
    path('directory/', views.directory, name='brother_directory'),
    path('directory/member/<int:pk>/', views.brother_profile, name='brother_profile'),
    path('points/manage/', views.manage_points_creation, name='manage_points_creation'),
]