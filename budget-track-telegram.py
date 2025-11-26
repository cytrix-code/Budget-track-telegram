import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBudgetTracker:
    def __init__(self, data_file="telegram_budget_data.json"):
        self.data_file = data_file
        self.categories = {
            'income': ['Salary', 'Freelance', 'Investments', 'Gifts', 'Other Income'],
            'expense': ['Food', 'Transportation', 'Housing', 'Entertainment', 'Healthcare', 'Utilities', 'Shopping', 'Education', 'Other']
        }
        self.load_data()
    
    def load_data(self):
        """Load data from JSON file or initialize empty data structure"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, KeyError):
                self.initialize_data()
        else:
            self.initialize_data()
    
    def initialize_data(self):
        """Initialize empty data structure"""
        self.data = {
            'users': {},  # user_id: {transactions, budgets, savings_goals, total_savings}
        }
    
    def save_data(self):
        """Save data to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=4)
    
    def get_user_data(self, user_id: str):
        """Get or create user data"""
        if user_id not in self.data['users']:
            self.data['users'][user_id] = {
                'transactions': [],
                'budgets': {},
                'savings_goals': [],
                'total_savings': 0.0
            }
        return self.data['users'][user_id]
    
    def add_transaction(self, user_id: str, amount: float, category: str, transaction_type: str, description: str = ""):
        """Add a new transaction (income or expense)"""
        user_data = self.get_user_data(user_id)
        
        transaction = {
            'id': len(user_data['transactions']) + 1,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'amount': amount,
            'category': category,
            'type': transaction_type,
            'description': description
        }
        
        user_data['transactions'].append(transaction)
        
        # Update savings if it's income
        if transaction_type == 'income':
            user_data['total_savings'] += amount
        elif transaction_type == 'expense':
            user_data['total_savings'] -= amount
        
        self.save_data()
        return f"✅ {transaction_type.capitalize()} of ${amount:.2f} added successfully!"
    
    def set_budget(self, user_id: str, category: str, amount: float):
        """Set budget for a specific category"""
        user_data = self.get_user_data(user_id)
        user_data['budgets'][category] = {
            'amount': amount,
            'set_date': datetime.now().strftime("%Y-%m-%d")
        }
        self.save_data()
        return f"✅ Budget of ${amount:.2f} set for {category}"
    
    def add_savings_goal(self, user_id: str, name: str, target_amount: float, target_date: str):
        """Add a new savings goal"""
        user_data = self.get_user_data(user_id)
        goal = {
            'id': len(user_data['savings_goals']) + 1,
            'name': name,
            'target_amount': target_amount,
            'current_amount': 0.0,
            'target_date': target_date,
            'created_date': datetime.now().strftime("%Y-%m-%d")
        }
        user_data['savings_goals'].append(goal)
        self.save_data()
        return f"✅ Savings goal '{name}' added successfully!"
    
    def get_financial_summary(self, user_id: str, period: str = "current_month") -> Dict:
        """Get financial summary for the specified period"""
        user_data = self.get_user_data(user_id)
        now = datetime.now()
        
        if period == "current_month":
            start_date = datetime(now.year, now.month, 1)
            end_date = datetime(now.year, now.month + 1, 1) - timedelta(days=1) if now.month < 12 else datetime(now.year + 1, 1, 1) - timedelta(days=1)
        elif period == "last_month":
            last_month = now.month - 1 if now.month > 1 else 12
            year = now.year if now.month > 1 else now.year - 1
            start_date = datetime(year, last_month, 1)
            end_date = datetime(now.year, now.month, 1) - timedelta(days=1)
        else:  # all time
            start_date = datetime(2000, 1, 1)
            end_date = datetime(2100, 1, 1)
        
        transactions = user_data['transactions']
        period_transactions = [
            t for t in transactions
            if start_date <= datetime.strptime(t['date'], "%Y-%m-%d %H:%M:%S") <= end_date
        ]
        
        total_income = sum(t['amount'] for t in period_transactions if t['type'] == 'income')
        total_expenses = sum(t['amount'] for t in period_transactions if t['type'] == 'expense')
        net_savings = total_income - total_expenses
        
        # Calculate expenses by category
        expenses_by_category = {}
        for t in period_transactions:
            if t['type'] == 'expense':
                category = t['category']
                expenses_by_category[category] = expenses_by_category.get(category, 0) + t['amount']
        
        # Check budget compliance
        budget_alerts = []
        for category, budget_info in user_data['budgets'].items():
            spent = expenses_by_category.get(category, 0)
            budget = budget_info['amount']
            if spent > budget:
                budget_alerts.append(f"⚠️ {category}: ${spent:.2f} spent (budget: ${budget:.2f})")
        
        return {
            'period': period,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_savings': net_savings,
            'expenses_by_category': expenses_by_category,
            'budget_alerts': budget_alerts,
            'total_savings': user_data['total_savings']
        }
    
    def view_transactions(self, user_id: str, limit: int = 10):
        """View recent transactions"""
        user_data = self.get_user_data(user_id)
        transactions = user_data['transactions'][-limit:]
        
        if not transactions:
            return "No transactions found."
        
        message = "📋 Recent Transactions:\n\n"
        for t in reversed(transactions):
            emoji = "💰" if t['type'] == 'income' else "💸"
            message += f"{emoji} {t['date'][:10]}\n"
            message += f"   {t['type'].title()}: {t['category']}\n"
            message += f"   Amount: ${t['amount']:.2f}\n"
            if t['description']:
                message += f"   Note: {t['description']}\n"
            message += "\n"
        
        return message
    
    def view_savings_goals(self, user_id: str):
        """View all savings goals and progress"""
        user_data = self.get_user_data(user_id)
        goals = user_data['savings_goals']
        
        if not goals:
            return "No savings goals set."
        
        message = "🎯 Savings Goals:\n\n"
        for goal in goals:
            progress = (goal['current_amount'] / goal['target_amount']) * 100 if goal['target_amount'] > 0 else 0
            progress_bar = self._create_progress_bar(progress)
            
            message += f"🏁 {goal['name']}\n"
            message += f"   Target: ${goal['target_amount']:.2f}\n"
            message += f"   Saved: ${goal['current_amount']:.2f}\n"
            message += f"   Progress: {progress_bar}\n"
            message += f"   Due: {goal['target_date']}\n\n"
        
        return message
    
    def _create_progress_bar(self, progress: float, length: int = 10) -> str:
        """Create a visual progress bar"""
        filled = int(length * progress / 100)
        bar = '█' * filled + '░' * (length - filled)
        return f"{bar} {progress:.1f}%"

# Initialize the tracker
tracker = TelegramBudgetTracker()

# Telegram Bot Functions
def start(update, context):
    """Send welcome message when the command /start is issued."""
    welcome_text = """
💰 *Welcome to Your Personal Budget Tracker Bot!* 💰

I'll help you track your income, expenses, and savings goals. Here's what you can do:

*Main Commands:*
/start - Show this welcome message
/add_income - Add income transaction
/add_expense - Add expense transaction  
/set_budget - Set budget for categories
/summary - View financial summary
/transactions - View recent transactions
/goals - Manage savings goals
/help - Show help information

Let's get your finances organized! 💪
    """
    update.message.reply_text(welcome_text, parse_mode='Markdown')

def help_command(update, context):
    """Send help message when the command /help is issued."""
    help_text = """
📖 *Budget Tracker Help*

*Available Commands:*
/start - Welcome message
/add_income - Add income (salary, freelance, etc.)
/add_expense - Add expense (food, transport, etc.)
/set_budget - Set monthly budgets
/summary - Financial overview
/transactions - Recent transactions
/goals - Savings goals
/help - This help message

*How to use:*
1. Set your budgets with /set_budget
2. Add income with /add_income
3. Add expenses with /add_expense
4. Check your progress with /summary
5. Set savings goals with /goals

Your data is stored securely and privately! 🔒
    """
    update.message.reply_text(help_text, parse_mode='Markdown')

def add_income(update, context):
    """Start the process of adding income."""
    keyboard = []
    for category in tracker.categories['income']:
        keyboard.append([InlineKeyboardButton(category, callback_data=f"income_{category}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "💵 Choose income category:",
        reply_markup=reply_markup
    )

def add_expense(update, context):
    """Start the process of adding expense."""
    keyboard = []
    for category in tracker.categories['expense']:
        keyboard.append([InlineKeyboardButton(category, callback_data=f"expense_{category}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "💸 Choose expense category:",
        reply_markup=reply_markup
    )

def set_budget(update, context):
    """Start the process of setting a budget."""
    keyboard = []
    for category in tracker.categories['expense']:
        keyboard.append([InlineKeyboardButton(category, callback_data=f"budget_{category}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "📊 Choose category to set budget:",
        reply_markup=reply_markup
    )

def show_summary(update, context):
    """Show financial summary."""
    user_id = str(update.effective_user.id)
    summary = tracker.get_financial_summary(user_id)
    
    message = f"""
📊 *Financial Summary* ({summary['period'].replace('_', ' ').title()})

*Income & Expenses:*
💰 Total Income: ${summary['total_income']:.2f}
💸 Total Expenses: ${summary['total_expenses']:.2f}
📈 Net Savings: ${summary['net_savings']:.2f}
💼 Total Savings: ${summary['total_savings']:.2f}
    """
    
    if summary['expenses_by_category']:
        message += "\n*Expenses by Category:*\n"
        for category, amount in summary['expenses_by_category'].items():
            message += f"  • {category}: ${amount:.2f}\n"
    
    if summary['budget_alerts']:
        message += "\n*🚨 Budget Alerts:*\n"
        for alert in summary['budget_alerts']:
            message += f"  {alert}\n"
    
    update.message.reply_text(message, parse_mode='Markdown')

def show_transactions(update, context):
    """Show recent transactions."""
    user_id = str(update.effective_user.id)
    message = tracker.view_transactions(user_id)
    update.message.reply_text(message, parse_mode='Markdown')

def show_goals(update, context):
    """Show savings goals."""
    user_id = str(update.effective_user.id)
    message = tracker.view_savings_goals(user_id)
    
    keyboard = [
        [InlineKeyboardButton("➕ Add New Goal", callback_data="add_goal")],
        [InlineKeyboardButton("📈 Update Goal Progress", callback_data="update_goal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

def button_handler(update, context):
    """Handle button callbacks."""
    query = update.callback_query
    query.answer()
    
    user_id = str(update.effective_user.id)
    data = query.data
    
    if data.startswith('income_'):
        category = data.replace('income_', '')
        context.user_data['pending_income'] = {'category': category}
        query.edit_message_text(f"💵 Adding {category} income\n\nPlease enter the amount:")
    
    elif data.startswith('expense_'):
        category = data.replace('expense_', '')
        context.user_data['pending_expense'] = {'category': category}
        query.edit_message_text(f"💸 Adding {category} expense\n\nPlease enter the amount:")
    
    elif data.startswith('budget_'):
        category = data.replace('budget_', '')
        context.user_data['pending_budget'] = {'category': category}
        query.edit_message_text(f"📊 Setting budget for {category}\n\nPlease enter the budget amount:")
    
    elif data == 'add_goal':
        context.user_data['pending_goal'] = {'step': 'name'}
        query.edit_message_text("🎯 Let's add a new savings goal!\n\nWhat would you like to call this goal?")
    
    elif data == 'update_goal':
        user_data = tracker.get_user_data(user_id)
        if not user_data['savings_goals']:
            query.edit_message_text("No savings goals found. Add one first!")
            return
        
        keyboard = []
        for goal in user_data['savings_goals']:
            keyboard.append([InlineKeyboardButton(goal['name'], callback_data=f"update_{goal['id']}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("Select goal to update:", reply_markup=reply_markup)

def handle_message(update, context):
    """Handle user messages for various inputs."""
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    try:
        # Handle income amount
        if 'pending_income' in context.user_data:
            amount = float(text)
            category = context.user_data['pending_income']['category']
            result = tracker.add_transaction(user_id, amount, category, 'income')
            del context.user_data['pending_income']
            update.message.reply_text(result)
        
        # Handle expense amount
        elif 'pending_expense' in context.user_data:
            amount = float(text)
            category = context.user_data['pending_expense']['category']
            result = tracker.add_transaction(user_id, amount, category, 'expense')
            del context.user_data['pending_expense']
            update.message.reply_text(result)
        
        # Handle budget amount
        elif 'pending_budget' in context.user_data:
            amount = float(text)
            category = context.user_data['pending_budget']['category']
            result = tracker.set_budget(user_id, category, amount)
            del context.user_data['pending_budget']
            update.message.reply_text(result)
        
        # Handle savings goal steps
        elif 'pending_goal' in context.user_data:
            step = context.user_data['pending_goal']['step']
            
            if step == 'name':
                context.user_data['pending_goal']['name'] = text
                context.user_data['pending_goal']['step'] = 'amount'
                update.message.reply_text("Great! Now enter the target amount:")
            
            elif step == 'amount':
                amount = float(text)
                context.user_data['pending_goal']['target_amount'] = amount
                context.user_data['pending_goal']['step'] = 'date'
                update.message.reply_text("Perfect! Now enter the target date (YYYY-MM-DD):")
            
            elif step == 'date':
                target_date = text
                name = context.user_data['pending_goal']['name']
                target_amount = context.user_data['pending_goal']['target_amount']
                
                result = tracker.add_savings_goal(user_id, name, target_amount, target_date)
                del context.user_data['pending_goal']
                update.message.reply_text(result)
    
    except ValueError:
        update.message.reply_text("❌ Please enter a valid number!")
    except Exception as e:
        update.message.reply_text(f"❌ An error occurred: {str(e)}")

def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # REPLACE "YOUR_BOT_TOKEN_HERE" WITH YOUR ACTUAL BOT TOKEN
    updater = Updater("8594331460:AAETxTtfsyXZ6zAxEvQewcApsGRUE8m5gzU", use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("add_income", add_income))
    dp.add_handler(CommandHandler("add_expense", add_expense))
    dp.add_handler(CommandHandler("set_budget", set_budget))
    dp.add_handler(CommandHandler("summary", show_summary))
    dp.add_handler(CommandHandler("transactions", show_transactions))
    dp.add_handler(CommandHandler("goals", show_goals))
    
    # Add callback query handler for buttons
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    # Add message handler for text messages
    dp.add_handler(MessageHandler(Filters.text, handle_message))

    # Start the Bot
    print("Bot is running...")
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == '__main__':
    main()