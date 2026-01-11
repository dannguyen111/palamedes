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
    path('dues/paid/<int:pk>/', views.make_payment_treasurer, name='make_mark_paid'),
    path('dues/checkout_treasurer/<int:pk>/', views.mark_paid, name='mark_paid'),
    path('dues/unpaid_directory/', views.unpaid_directory, name='unpaid_directory'),
    path('dues/brothers_due/<int:pk>/', views.dues_member, name='brothers_due'),
    path('dues/manage/', views.manage_dues_creation, name='manage_dues_creation'),
    path('dues/payment_success/', views.payment_success, name='payment_success'),
    path('dues/checkout/<int:pk>/', views.process_payment, name='create_checkout_session'),
    path('dues/create_bulk_checkout_session/', views.create_bulk_checkout_session, name='create_bulk_checkout_session'),
    path('dues/payment_page/<int:pk>/', views.payment_page, name='payment_page'), 
    path('directory/', views.directory, name='brother_directory'),
    path('directory/member/<int:pk>/', views.brother_profile, name='brother_profile'),
    path('points/manage/', views.manage_points_creation, name='manage_points_creation'),
]