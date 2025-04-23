from flask import Flask, request, render_template, redirect, url_for, flash
import uuid

app = Flask(__name__, template_folder="templates")
app.secret_key = 'my_key'  # Necessary for flash messages

class Account:
    """Class representing a bank account"""
    
    def __init__(self, account_number, pin, holder_name, balance=0):
        self.account_number = account_number
        self.pin = pin
        self.holder_name = holder_name
        self.balance = balance
        self.transaction_history = []
    
    def deposit(self, amount):
        if amount > 0:
            self.balance += amount
            self.transaction_history.append(f"Deposit: +${amount}")
            return True, f"${amount} deposited successfully. New balance: ${self.balance}"
        return False, "Invalid amount for deposit"
    
    def withdraw(self, amount):
        if amount <= 0:
            return False, "Invalid amount for withdrawal"
        if amount > self.balance:
            return False, "Insufficient funds"
        
        self.balance -= amount
        self.transaction_history.append(f"Withdrawal: -${amount}")
        return True, f"${amount} withdrawn successfully. New balance: ${self.balance}"
    
    def get_balance(self):
        return self.balance
    
    def get_transaction_history(self):
        return self.transaction_history


class Bank:
    """Class representing a bank with multiple accounts"""
    
    def __init__(self):
        self.accounts = {}
        self.cards = {}  # card_number: account_number mapping
        
        # Create some demo accounts
        self.create_account("123456", "1234", "John Doe", 5000)
        self.create_account("234567", "5678", "Jane Smith", 3500)
    
    def create_account(self, account_number, pin, holder_name, balance=0):
        new_account = Account(account_number, pin, holder_name, balance)
        self.accounts[account_number] = new_account
        card_number = "1" + account_number.zfill(15)  
        self.cards[card_number] = account_number
        return new_account
    
    def get_account_by_card(self, card_number):
        if card_number in self.cards:
            account_number = self.cards[card_number]
            return self.accounts.get(account_number)
        return None
    
    def authenticate(self, card_number, pin):
        account = self.get_account_by_card(card_number)
        if account and account.pin == pin:
            return True, account
        return False, None


class ATM:
    """Class representing an ATM machine"""
    
    def __init__(self, bank):
        self.bank = bank
        self.current_session = {}  # Store active sessions
    
    def start_session(self, card_number):
        account = self.bank.get_account_by_card(card_number)
        if account:
            session_id = str(uuid.uuid4())
            self.current_session[session_id] = {"card_number": card_number, "authenticated": False}
            return True, session_id
        return False, "Card not recognized"
    
    def authenticate(self, session_id, pin):
        if session_id not in self.current_session:
            return False, "Invalid session"
            
        session = self.current_session[session_id]
        card_number = session["card_number"]
        success, account = self.bank.authenticate(card_number, pin)
        
        if success:
            session["authenticated"] = True
            session["account"] = account
            return True, {
                "holder_name": account.holder_name,
                "account_number": account.account_number[-4:] # Show only last 4 digits
            }
        return False, "Invalid PIN"
    
    def check_balance(self, session_id):
        if not self._validate_session(session_id):
            return False, "Not authenticated"
            
        account = self.current_session[session_id]["account"]
        balance = account.get_balance()
        return True, {"balance": balance}
    
    def withdraw(self, session_id, amount):
        if not self._validate_session(session_id):
            return False, "Not authenticated"
            
        account = self.current_session[session_id]["account"]
        try:
            amount = float(amount)
        except ValueError:
            return False, "Invalid amount"
            
        success, message = account.withdraw(amount)
        if success:
            return True, {"message": message, "balance": account.get_balance()}
        return False, message
    
    def deposit(self, session_id, amount):
        if not self._validate_session(session_id):
            return False, "Not authenticated"
            
        account = self.current_session[session_id]["account"]
        try:
            amount = float(amount)
        except ValueError:
            return False, "Invalid amount"
            
        success, message = account.deposit(amount)
        if success:
            return True, {"message": message, "balance": account.get_balance()}
        return False, message
    
    def get_transactions(self, session_id):
        if not self._validate_session(session_id):
            return False, "Not authenticated"
            
        account = self.current_session[session_id]["account"]
        transactions = account.get_transaction_history()
        return True, {"transactions": transactions}
    
    def end_session(self, session_id):
        if session_id in self.current_session:
            del self.current_session[session_id]
        return True, "Session ended successfully"
    
    def _validate_session(self, session_id):
        return (session_id in self.current_session and 
                self.current_session[session_id].get("authenticated", False))


# Initialize our bank and ATM
bank = Bank()
atm = ATM(bank)


# Routes for serving HTML and handling form submissions
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/insert-card', methods=['GET', 'POST'])
def insert_card():
    if request.method == 'POST':
        card_number = request.form.get('card_number')
        success, result = atm.start_session(card_number)

        if success:
            return render_template('pin.html', session_id=result)

        flash("Card not recognized, please try again.", "error")
        return redirect(url_for('insert_card'))

    # GET request – just render the card input page
    return render_template('index.html')


@app.route('/verify-pin', methods=['POST'])
def verify_pin():
    session_id = request.form.get('session_id')
    pin = request.form.get('pin')
    success, result = atm.authenticate(session_id, pin)

    if success:
        return render_template('main_menu.html', user=result, session_id=session_id)

    flash("Invalid PIN. Please try again.", "error")
    return render_template('pin.html', session_id=session_id)

@app.route('/main-menu/<session_id>')
def main_menu(session_id):
    if not atm._validate_session(session_id):
        flash("Session expired or invalid. Please login again.", "error")
        return redirect(url_for('home'))

    account = atm.current_session[session_id]["account"]
    user_info = {
        "holder_name": account.holder_name,
        "account_number": account.account_number[-4:]
    }
    return render_template('main_menu.html', user=user_info, session_id=session_id)

@app.route('/check-balance/<session_id>')
def check_balance(session_id):
    success, result = atm.check_balance(session_id)
    if success:
        return render_template('check_balance.html', balance=result["balance"], session_id=session_id)

    flash("Unable to check balance: " + result, "error")
    return redirect(url_for('main_menu', session_id=session_id))

@app.route('/withdraw/<session_id>', methods=['GET', 'POST'])
def withdraw(session_id):
    if request.method == 'POST':
        amount = request.form.get('amount')
        success, result = atm.withdraw(session_id, amount)

        if success:
            return render_template('receipt_screen.html', 
                                   transaction_type="Withdrawal",
                                   amount=amount,
                                   message=result["message"],
                                   balance=result["balance"],
                                   session_id=session_id)
        else:
            flash(result, "error")
            return render_template('with_drawn.html', session_id=session_id)

    return render_template('with_drawn.html', session_id=session_id)

@app.route('/deposit/<session_id>', methods=['GET', 'POST'])
def deposit(session_id):
    if request.method == 'POST':
        amount = request.form.get('amount')
        success, result = atm.deposit(session_id, amount)

        if success:
            return render_template('receipt_screen.html',
                                   transaction_type="Deposit",
                                   amount=amount,
                                   message=result["message"],
                                   balance=result["balance"],
                                   session_id=session_id)
        else:
            flash(result, "error")
            return render_template('deposit_screen.html', session_id=session_id)

    return render_template('deposit_screen.html', session_id=session_id)

@app.route('/transactions/<session_id>', methods=['GET', 'POST'])
def transactions(session_id):
    success, result = atm.get_transactions(session_id)

    if success:
        return render_template('transactions.html', transactions=result["transactions"], session_id=session_id)

    flash("Unable to retrieve transactions: " + result, "error")
    return redirect(url_for('main_menu', session_id=session_id))

@app.route('/logout/<session_id>')
def logout(session_id):
    atm.end_session(session_id)
    flash("Thank you for using our ATM. Goodbye!", "success")
    return redirect(url_for('insert_card'))

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)
