from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from datetime import datetime, timedelta
from decimal import Decimal
import calendar
from .models import MonthlyBudget, Category, Transaction, DailySummary, MonthlySummary, Goal

User = get_user_model()

@login_required(login_url='login')
def dashboard(request):
    """Main dashboard with budget overview"""
    user = request.user
    
    # Get active budget or most recent budget
    active_budget = MonthlyBudget.objects.filter(user=user, is_active=True).first()
    
    if not active_budget:
        # Check if user has any budgets at all
        has_budgets = MonthlyBudget.objects.filter(user=user).exists()
        if not has_budgets:
            # First time user - redirect to budget setup
            return redirect('budget_setup')
        else:
            # User has old budgets but none active
            active_budget = MonthlyBudget.objects.filter(user=user).first()
    
    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        monthly_budget=active_budget
    ).order_by('-date', '-created_at')[:10] if active_budget else []
    
    # Get goals
    goals = Goal.objects.filter(user=user, is_completed=False)[:5]
    
    # Calculate statistics
    context = {
        'user': user,
        'active_budget': active_budget,
        'recent_transactions': recent_transactions,
        'goals': goals,
    }
    
    if active_budget:
        context.update({
            'total_budget': active_budget.total_budget,
            'total_spent': active_budget.get_total_spent(),
            'total_income': active_budget.get_total_income(),
            'remaining_balance': active_budget.get_remaining_balance(),
            'categories_summary': active_budget.get_categories_summary(),
        })
    
    return render(request, 'Budgeting/dashboard.html', context)


@login_required(login_url='login')
def budget_setup(request):
    """Setup monthly budget and categories"""
    user = request.user
    
    # Check if user already has an active budget
    active_budget = MonthlyBudget.objects.filter(user=user, is_active=True).first()
    
    if request.method == 'POST':
        # Get form data
        total_budget = request.POST.get('total_budget')
        start_date = request.POST.get('start_date')
        
        # Validation
        errors = []
        
        if not total_budget:
            errors.append('Total budget is required')
        else:
            try:
                total_budget = Decimal(total_budget)
                if total_budget <= 0:
                    errors.append('Total budget must be greater than 0')
            except:
                errors.append('Invalid budget amount')
        
        if not start_date:
            errors.append('Start date is required')
        else:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except:
                errors.append('Invalid date format')
        
        if errors:
            return render(request, 'Budgeting/budget_setup.html', {
                'errors': errors,
                'total_budget': request.POST.get('total_budget'),
                'start_date': request.POST.get('start_date'),
                'active_budget': active_budget,
            })
        
        # Deactivate previous active budgets
        MonthlyBudget.objects.filter(user=user, is_active=True).update(is_active=False)
        
        # Create new budget
        budget = MonthlyBudget.objects.create(
            user=user,
            start_date=start_date,
            total_budget=total_budget,
            is_active=True
        )
        
        messages.success(request, 'Budget created successfully! Now add categories.')
        return redirect('category_setup', budget_id=budget.budgetId)
    
    return render(request, 'Budgeting/budget_setup.html', {
        'active_budget': active_budget,
    })


@login_required(login_url='login')
def category_setup(request, budget_id):
    """Setup budget categories"""
    budget = get_object_or_404(MonthlyBudget, budgetId=budget_id, user=request.user)
    
    # Get existing categories
    existing_categories = Category.objects.filter(monthly_budget=budget)
    
    # Predefined categories
    predefined = Category.PREDEFINED_CATEGORIES
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_predefined':
            # Add predefined category
            category_type = request.POST.get('category_type')
            allocated_amount = request.POST.get('allocated_amount')
            
            errors = []
            
            if not category_type:
                errors.append('Please select a category')
            
            if not allocated_amount:
                errors.append('Allocated amount is required')
            else:
                try:
                    allocated_amount = Decimal(allocated_amount)
                    if allocated_amount <= 0:
                        errors.append('Amount must be greater than 0')
                except:
                    errors.append('Invalid amount')
            
            if not errors:
                # Get category name from predefined list
                category_name = dict(predefined).get(category_type, 'Unknown')
                
                # Check if category already exists
                if not Category.objects.filter(monthly_budget=budget, category_type=category_type).exists():
                    Category.objects.create(
                        monthly_budget=budget,
                        category_name=category_name,
                        category_type=category_type,
                        allocated_amount=allocated_amount,
                        is_custom=False
                    )
                    messages.success(request, f'Category "{category_name}" added successfully!')
                else:
                    messages.warning(request, f'Category "{category_name}" already exists!')
                
                return redirect('category_setup', budget_id=budget_id)
        
        elif action == 'add_custom':
            # Add custom category
            category_name = request.POST.get('custom_category_name', '').strip()
            allocated_amount = request.POST.get('custom_allocated_amount')
            
            errors = []
            
            if not category_name:
                errors.append('Category name is required')
            
            if not allocated_amount:
                errors.append('Allocated amount is required')
            else:
                try:
                    allocated_amount = Decimal(allocated_amount)
                    if allocated_amount <= 0:
                        errors.append('Amount must be greater than 0')
                except:
                    errors.append('Invalid amount')
            
            if not errors:
                Category.objects.create(
                    monthly_budget=budget,
                    category_name=category_name,
                    allocated_amount=allocated_amount,
                    is_custom=True
                )
                messages.success(request, f'Custom category "{category_name}" added successfully!')
                return redirect('category_setup', budget_id=budget_id)
        
        elif action == 'finish':
            # Finish setup and go to dashboard
            messages.success(request, 'Budget setup completed!')
            return redirect('budgeting_dashboard')
    
    # Calculate total allocated
    total_allocated = sum(cat.allocated_amount for cat in existing_categories)
    remaining = budget.total_budget - total_allocated
    
    context = {
        'budget': budget,
        'existing_categories': existing_categories,
        'predefined_categories': predefined,
        'total_allocated': total_allocated,
        'remaining': remaining,
    }
    
    return render(request, 'Budgeting/category_setup.html', context)


@login_required(login_url='login')
def delete_category(request, category_id):
    """Delete a category"""
    category = get_object_or_404(Category, categoryId=category_id, monthly_budget__user=request.user)
    budget_id = category.monthly_budget.budgetId
    
    # Check if category has transactions
    if category.transactions.exists():
        messages.error(request, f'Cannot delete "{category.category_name}" because it has transactions.')
    else:
        category_name = category.category_name
        category.delete()
        messages.success(request, f'Category "{category_name}" deleted successfully!')
    
    return redirect('category_setup', budget_id=budget_id)


@login_required(login_url='login')
def transactions_list(request):
    """View all transactions"""
    user = request.user
    active_budget = MonthlyBudget.objects.filter(user=user, is_active=True).first()
    
    if not active_budget:
        messages.warning(request, 'Please set up your budget first.')
        return redirect('budget_setup')
    
    # Get all transactions for active budget
    transactions = Transaction.objects.filter(monthly_budget=active_budget).order_by('-date', '-created_at')
    
    # Filter by type if specified
    filter_type = request.GET.get('type')
    if filter_type in ['income', 'expense']:
        transactions = transactions.filter(transaction_type=filter_type)
    
    # Filter by category if specified
    category_id = request.GET.get('category')
    if category_id:
        transactions = transactions.filter(category_id=category_id)
    
    categories = Category.objects.filter(monthly_budget=active_budget)
    
    context = {
        'active_budget': active_budget,
        'transactions': transactions,
        'categories': categories,
        'filter_type': filter_type,
        'filter_category': category_id,
    }
    
    return render(request, 'Budgeting/transactions_list.html', context)


@login_required(login_url='login')
def add_transaction(request):
    """Add a new transaction (income or expense)"""
    user = request.user
    active_budget = MonthlyBudget.objects.filter(user=user, is_active=True).first()
    
    if not active_budget:
        messages.warning(request, 'Please set up your budget first.')
        return redirect('budget_setup')
    
    categories = Category.objects.filter(monthly_budget=active_budget)
    
    if request.method == 'POST':
        transaction_type = request.POST.get('transaction_type')
        amount = request.POST.get('amount')
        category_id = request.POST.get('category')
        date = request.POST.get('date')
        note = request.POST.get('note', '').strip()
        
        errors = []
        
        if not transaction_type or transaction_type not in ['income', 'expense']:
            errors.append('Please select transaction type')
        
        if not amount:
            errors.append('Amount is required')
        else:
            try:
                amount = Decimal(amount)
                if amount <= 0:
                    errors.append('Amount must be greater than 0')
            except:
                errors.append('Invalid amount')
        
        if transaction_type == 'expense' and not category_id:
            errors.append('Category is required for expenses')
        
        if not date:
            errors.append('Date is required')
        else:
            try:
                date = datetime.strptime(date, '%Y-%m-%d').date()
            except:
                errors.append('Invalid date format')
        
        if errors:
            return render(request, 'Budgeting/add_transaction.html', {
                'errors': errors,
                'categories': categories,
                'form_data': request.POST,
            })
        
        # Create transaction
        transaction = Transaction.objects.create(
            monthly_budget=active_budget,
            transaction_type=transaction_type,
            amount=amount,
            category_id=category_id if category_id else None,
            date=date,
            note=note
        )
        
        # Update daily summary
        DailySummary.update_or_create_for_date(active_budget, date)
        
        # Update monthly summary
        MonthlySummary.update_or_create_for_budget(active_budget)
        
        messages.success(request, f'{transaction_type.capitalize()} of {amount} added successfully!')
        return redirect('transactions_list')
    
    context = {
        'categories': categories,
        'today': timezone.now().date(),
    }
    
    return render(request, 'Budgeting/add_transaction.html', context)


@login_required(login_url='login')
def edit_transaction(request, transaction_id):
    """Edit an existing transaction"""
    transaction = get_object_or_404(Transaction, transactionId=transaction_id, monthly_budget__user=request.user)
    active_budget = transaction.monthly_budget
    categories = Category.objects.filter(monthly_budget=active_budget)
    
    if request.method == 'POST':
        transaction_type = request.POST.get('transaction_type')
        amount = request.POST.get('amount')
        category_id = request.POST.get('category')
        date = request.POST.get('date')
        note = request.POST.get('note', '').strip()
        
        errors = []
        
        if not transaction_type or transaction_type not in ['income', 'expense']:
            errors.append('Please select transaction type')
        
        if not amount:
            errors.append('Amount is required')
        else:
            try:
                amount = Decimal(amount)
                if amount <= 0:
                    errors.append('Amount must be greater than 0')
            except:
                errors.append('Invalid amount')
        
        if transaction_type == 'expense' and not category_id:
            errors.append('Category is required for expenses')
        
        if not date:
            errors.append('Date is required')
        else:
            try:
                date = datetime.strptime(date, '%Y-%m-%d').date()
            except:
                errors.append('Invalid date format')
        
        if errors:
            return render(request, 'Budgeting/edit_transaction.html', {
                'errors': errors,
                'transaction': transaction,
                'categories': categories,
            })
        
        # Store old date for summary updates
        old_date = transaction.date
        
        # Update transaction
        transaction.transaction_type = transaction_type
        transaction.amount = amount
        transaction.category_id = category_id if category_id else None
        transaction.date = date
        transaction.note = note
        transaction.save()
        
        # Update daily summaries (both old and new dates)
        DailySummary.update_or_create_for_date(active_budget, old_date)
        if old_date != date:
            DailySummary.update_or_create_for_date(active_budget, date)
        
        # Update monthly summary
        MonthlySummary.update_or_create_for_budget(active_budget)
        
        messages.success(request, 'Transaction updated successfully!')
        return redirect('transactions_list')
    
    context = {
        'transaction': transaction,
        'categories': categories,
    }
    
    return render(request, 'Budgeting/edit_transaction.html', context)


@login_required(login_url='login')
def delete_transaction(request, transaction_id):
    """Delete a transaction"""
    transaction = get_object_or_404(Transaction, transactionId=transaction_id, monthly_budget__user=request.user)
    
    if request.method == 'POST':
        active_budget = transaction.monthly_budget
        date = transaction.date
        
        transaction.delete()
        
        # Update daily summary
        DailySummary.update_or_create_for_date(active_budget, date)
        
        # Update monthly summary
        MonthlySummary.update_or_create_for_budget(active_budget)
        
        messages.success(request, 'Transaction deleted successfully!')
        return redirect('transactions_list')
    
    return render(request, 'Budgeting/delete_transaction.html', {'transaction': transaction})


@login_required(login_url='login')
def quick_add_transaction(request):
    """Quick add transaction (AJAX-friendly)"""
    user = request.user
    active_budget = MonthlyBudget.objects.filter(user=user, is_active=True).first()
    
    if not active_budget:
        messages.warning(request, 'Please set up your budget first.')
        return redirect('budget_setup')
    
    categories = Category.objects.filter(monthly_budget=active_budget)
    
    if request.method == 'POST':
        transaction_type = request.POST.get('transaction_type')
        amount = request.POST.get('amount')
        category_id = request.POST.get('category')
        note = request.POST.get('note', '').strip()
        
        errors = []
        
        if not transaction_type or transaction_type not in ['income', 'expense']:
            errors.append('Please select transaction type')
        
        if not amount:
            errors.append('Amount is required')
        else:
            try:
                amount = Decimal(amount)
                if amount <= 0:
                    errors.append('Amount must be greater than 0')
            except:
                errors.append('Invalid amount')
        
        if transaction_type == 'expense' and not category_id:
            errors.append('Category is required for expenses')
        
        if not errors:
            # Create transaction with today's date
            transaction = Transaction.objects.create(
                monthly_budget=active_budget,
                transaction_type=transaction_type,
                amount=amount,
                category_id=category_id if category_id else None,
                date=timezone.now().date(),
                note=note
            )
            
            # Update summaries
            DailySummary.update_or_create_for_date(active_budget, timezone.now().date())
            MonthlySummary.update_or_create_for_budget(active_budget)
            
            messages.success(request, f'{transaction_type.capitalize()} added successfully!')
            return redirect('budgeting_dashboard')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'Budgeting/quick_add_transaction.html', context)


@login_required(login_url='login')
def calendar_view(request):
    """Calendar view with daily spending totals"""
    user = request.user
    active_budget = MonthlyBudget.objects.filter(user=user, is_active=True).first()
    
    if not active_budget:
        messages.warning(request, 'Please set up your budget first.')
        return redirect('budget_setup')
    
    # Get month and year from query params or use current
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # Get calendar data
    cal = calendar.monthcalendar(year, month)
    
    # Get all transactions for this month
    first_day = datetime(year, month, 1).date()
    if month == 12:
        last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)
    
    transactions = Transaction.objects.filter(
        monthly_budget=active_budget,
        date__gte=first_day,
        date__lte=last_day
    )
    
    # Create daily summary dict
    daily_data = {}
    for transaction in transactions:
        date_key = transaction.date.strftime('%Y-%m-%d')
        if date_key not in daily_data:
            daily_data[date_key] = {'income': 0, 'expense': 0, 'net': 0, 'transactions': []}
        
        if transaction.transaction_type == 'income':
            daily_data[date_key]['income'] += float(transaction.amount)
        else:
            daily_data[date_key]['expense'] += float(transaction.amount)
        
        daily_data[date_key]['net'] = daily_data[date_key]['income'] - daily_data[date_key]['expense']
        daily_data[date_key]['transactions'].append(transaction)
    
    # Calculate navigation dates
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    context = {
        'active_budget': active_budget,
        'calendar': cal,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'daily_data': daily_data,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
    }
    
    return render(request, 'Budgeting/calendar_dashboard.html', context)


@login_required(login_url='login')
def goals_list(request):
    """View all goals"""
    user = request.user
    active_goals = Goal.objects.filter(user=user, is_completed=False).order_by('target_date')
    completed_goals = Goal.objects.filter(user=user, is_completed=True).order_by('-updated_at')
    
    context = {
        'active_goals': active_goals,
        'completed_goals': completed_goals,
    }
    
    return render(request, 'Budgeting/goals.html', context)


@login_required(login_url='login')
def create_goal(request):
    """Create a new goal"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        target_amount = request.POST.get('target_amount')
        target_date = request.POST.get('target_date')
        
        errors = []
        
        if not title:
            errors.append('Goal title is required')
        
        if not target_amount:
            errors.append('Target amount is required')
        else:
            try:
                target_amount = Decimal(target_amount)
                if target_amount <= 0:
                    errors.append('Target amount must be greater than 0')
            except:
                errors.append('Invalid target amount')
        
        if not target_date:
            errors.append('Target date is required')
        else:
            try:
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
                if target_date <= timezone.now().date():
                    errors.append('Target date must be in the future')
            except:
                errors.append('Invalid date format')
        
        if errors:
            messages.error(request, ' '.join(errors))
            return redirect('goals_list')
        
        Goal.objects.create(
            user=request.user,
            title=title,
            target_amount=target_amount,
            target_date=target_date
        )
        
        messages.success(request, f'Goal "{title}" created successfully!')
        return redirect('goals_list')
    
    return redirect('goals_list')


@login_required(login_url='login')
def update_goal_progress(request, goal_id):
    """Update goal progress by ADDING money"""
    goal = get_object_or_404(Goal, goalId=goal_id, user=request.user)
    
    if request.method == 'POST':
        amount_to_add = request.POST.get('progress')
        
        try:
            amount_to_add = Decimal(amount_to_add)
            
            # Check for negative numbers
            if amount_to_add < 0:
                messages.error(request, 'Cannot add negative amount')
                return redirect('goals_list')

            # Calculate what the NEW total would be
            new_total = goal.current_progress + amount_to_add

            # Validation: Don't let them save more than the target
            if new_total > goal.target_amount:
                messages.error(request, f'Cannot add {amount_to_add}. It exceeds the target! You only need {goal.target_amount - goal.current_progress} more.')
            else:
                # ✅ THIS IS THE FIX: We ADD to the existing amount
                goal.current_progress = new_total
                
                # Check completion
                if goal.current_progress >= goal.target_amount:
                    goal.is_completed = True
                    messages.success(request, f'🎉 Congratulations! Goal "{goal.title}" completed!')
                else:
                    goal.is_completed = False
                    messages.success(request, f'Added {amount_to_add} to your savings!')
                
                goal.save()
        except:
            messages.error(request, 'Invalid amount')
    
    return redirect('goals_list')
    """Update goal progress"""
    goal = get_object_or_404(Goal, goalId=goal_id, user=request.user)
    
    if request.method == 'POST':
        progress = request.POST.get('progress')
        
        try:
            progress = Decimal(progress)
            if progress < 0:
                messages.error(request, 'Progress cannot be negative')
            elif progress > goal.target_amount:
                messages.error(request, 'Progress cannot exceed target amount')
            else:
                goal.current_progress = progress
                
                # Check if goal is completed
                if progress >= goal.target_amount:
                    goal.is_completed = True
                    messages.success(request, f'🎉 Congratulations! Goal "{goal.title}" completed!')
                else:
                    goal.is_completed = False
                
                goal.save()
                messages.success(request, 'Goal progress updated successfully!')
        except:
            messages.error(request, 'Invalid progress amount')
    
    return redirect('goals_list')


@login_required(login_url='login')
def delete_goal(request, goal_id):
    """Delete a goal"""
    goal = get_object_or_404(Goal, goalId=goal_id, user=request.user)
    
    if request.method == 'POST':
        goal_title = goal.title
        goal.delete()
        messages.success(request, f'Goal "{goal_title}" deleted successfully!')
    
    return redirect('goals_list')


@login_required(login_url='login')
def toggle_goal_completion(request, goal_id):
    """Toggle goal completion status"""
    goal = get_object_or_404(Goal, goalId=goal_id, user=request.user)
    
    if request.method == 'POST':
        goal.is_completed = not goal.is_completed
        goal.save()
        
        status = 'completed' if goal.is_completed else 'reopened'
        messages.success(request, f'Goal "{goal.title}" {status}!')
    
    return redirect('goals_list')