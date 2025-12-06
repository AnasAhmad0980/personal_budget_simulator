from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='budgeting_dashboard'),
    
    # Budget Setup
    path('budget/setup/', views.budget_setup, name='budget_setup'),
    path('budget/<int:budget_id>/categories/', views.category_setup, name='category_setup'),
    path('category/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    
    # Transactions
    path('transactions/', views.transactions_list, name='transactions_list'),
    path('transactions/add/', views.add_transaction, name='add_transaction'),
    path('transactions/<int:transaction_id>/edit/', views.edit_transaction, name='edit_transaction'),
    path('transactions/<int:transaction_id>/delete/', views.delete_transaction, name='delete_transaction'),
    path('transactions/quick-add/', views.quick_add_transaction, name='quick_add_transaction'),
    
    # Calendar
    path('calendar/', views.calendar_view, name='calendar_view'),
    
    # Goals
    path('goals/', views.goals_list, name='goals_list'),
    path('goals/create/', views.create_goal, name='create_goal'),
    path('goals/<int:goal_id>/update-progress/', views.update_goal_progress, name='update_goal_progress'),
    path('goals/<int:goal_id>/delete/', views.delete_goal, name='delete_goal'),
    path('goals/<int:goal_id>/toggle-completion/', views.toggle_goal_completion, name='toggle_goal_completion'),
]