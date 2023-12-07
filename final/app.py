from cs50 import SQL
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    make_response,
)
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from pytz import timezone
from forms import (
    LoginForm,
    RegistrationForm,
    ChangePasswordForm,
    IncomeForm,
    ExpenseForm,
    CustomerForm,
)
from flask import Flask, render_template, request, make_response
import pdfkit


from helpers import (
    login_required,
    calculate_financial_summary,
    usd,
    format_number_with_commas,
    format_number_with_commas_no_decimal,
)


# Configure application
app = Flask(__name__)
app.config["SECRET_KEY"] = "GodIsGreat"


app.jinja_env.filters["formatNumberWithCommas"] = format_number_with_commas

app.jinja_env.filters[
    "formatNumberWithCommasNoDecimal"
] = format_number_with_commas_no_decimal


# Custom filter
app.jinja_env.filters["usd"] = usd


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///database.db")


# Define the User model
class User:
    def __init__(self, username, hash):
        self.username = username
        self.hash = hash


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Registration Page
@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm(request.form)

    if request.method == "POST" and form.validate():
        username = form.username.data
        password = form.password.data
        confirm_password = form.confirm_password.data

        # Check if the username already exists
        existing_user = db.execute("SELECT * FROM users WHERE username = ?", username)

        if existing_user:
            flash("Username already taken. Please choose another.", "error")
            return redirect("/register")

        # Check if password and confirmation match
        if password != confirm_password:
            flash("Password and confirmation do not match.", "error")
            return redirect("/register")

        # Hash the password before storing it in the database
        hashed_password = generate_password_hash(password)

        # Add user to the database
        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            username,
            hashed_password,
        )

        # Log the user in
        session["user_id"] = username

        flash("Registration successful!", "success")
        return redirect("/")

    return render_template("register.html", form=form, active_page="register")


# Login Page
@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm(request.form)

    # Forget any user_id
    session.clear()

    if request.method == "POST" and form.validate():
        username = form.username.data
        password = form.password.data

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            flash("Invalid username or password. Please try again.", "error")
            return redirect("/login")

        session["user_id"] = rows[0]["username"]
        flash("Login successful!", "success")
        return redirect("/")

    return render_template("login.html", form=form, active_page="login")


# Change Password Page
@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change user password"""

    form = ChangePasswordForm(request.form)

    # Get username of the current user
    username = session.get("user_id")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure old password was submitted
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirmation = request.form.get("confirmation")

        if not old_password or not new_password or not confirmation:
            flash("Please fill in all fields.", "error")
            return redirect("/change_password")

        # Make sure old_password was entered correctly
        rows = db.execute("SELECT hash FROM users WHERE username = ?", username)

        print("Rows:", rows)  # Add this line for debugging

        if not check_password_hash(rows[0]["hash"], old_password):
            flash("Incorrect old password. Please try again.", "error")
            return redirect("/change_password")

        # Generate a hash of the new password
        hashed_password = generate_password_hash(new_password)

        # Update the user's password in the database
        db.execute(
            "UPDATE users SET hash = ? WHERE username = ?", hashed_password, username
        )

        # Flash a success message
        flash("Password changed successfully!", "success")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template(
            "change_password.html", form=form, active_page="change_password"
        )


# Logout
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/login")


# Home Page
@app.route("/")
@login_required
def home():
    username = session.get("user_id")

    # Calculate financial summary
    total_income, total_expenses, net_profit = calculate_financial_summary(username)

    # Fetch recent transactions from the database using CS50
    recent_transactions = db.execute(
        "SELECT * FROM transactions WHERE username = ? ORDER BY date DESC LIMIT 10",
        username,
    )

    # Fetch monthly net profit/loss data from the database
    monthly_data = db.execute(
        "SELECT strftime('%Y-%m', date) AS month, SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) AS net_profit FROM transactions WHERE username = ? GROUP BY month",
        username,
    )

    # Extract labels and values for the chart
    chart_labels = [entry["month"] for entry in monthly_data]
    chart_values = [entry["net_profit"] for entry in monthly_data]

    net_profit_is_negative = net_profit < 0

    return render_template(
        "home.html",
        total_income=total_income,
        total_expenses=total_expenses,
        net_profit=net_profit,
        recent_transactions=recent_transactions,
        chart_labels=chart_labels,
        chart_values=chart_values,
        net_profit_is_negative=net_profit_is_negative,
        active_page="home",
    )


# Income Page
@app.route("/income")
@login_required
def income():
    username = session.get("user_id")

    # Retrieve income transactions from the database
    transactions = db.execute(
        "SELECT * FROM transactions WHERE type = 'income' AND username = ?", username
    )
    return render_template(
        "income.html", transactions=transactions, active_page="income"
    )


# Add Income Page
@app.route("/add_income", methods=["GET", "POST"])
@login_required
def add_income():
    form = IncomeForm()

    username = session.get("user_id")

    if request.method == "POST":
        # Get form data
        description = request.form.get("description")
        amount = request.form.get("amount")
        date = request.form.get("date")

        # Validate form data
        if not description or not amount or not date:
            flash("Please fill in all fields.", "error")
            return redirect("add_income")

        # Insert income transaction into the database
        db.execute(
            "INSERT INTO transactions (username, type, description, amount, date) VALUES (?, 'income', ?, ?, ?)",
            username,
            description,
            amount,
            date,
        )
        flash("Income transaction added successfully!", "success")
        return redirect("/income")

    return render_template("add_income.html", form=form, active_page="income")


# Delete Income Page
@app.route("/delete_income", methods=["POST"])
@login_required
def delete_income():
    username = session.get("user_id")

    # Get the transaction_id from the form submission
    transaction_id = request.form.get("transaction_id")

    # Query the database to get the income transaction by ID
    result = db.execute("SELECT * FROM transactions WHERE id = ?", transaction_id)

    # Check if the result is not empty
    if result:
        transaction = result[0]

        # Check if the transaction belongs to the current user
        if transaction["username"] == username:
            # Delete the transaction from the database
            db.execute("DELETE FROM transactions WHERE id = ?", transaction_id)
            flash("Income transaction deleted successfully!", "success")
        else:
            flash("Invalid transaction or permission denied.", "error")
    else:
        flash("Transaction not found.", "error")

    # Redirect back to the income page
    return redirect("/income")


# Expense Page
@app.route("/expense")
@login_required
def expense():
    username = session.get("user_id")

    # Retrieve expense transactions from the database
    transactions = db.execute(
        "SELECT * FROM transactions WHERE type = 'expense' AND username = ?", username
    )
    return render_template(
        "expense.html", transactions=transactions, active_page="expense"
    )


# Add Expense Page
@app.route("/add_expense", methods=["GET", "POST"])
@login_required
def add_expense():
    form = ExpenseForm()

    username = session.get("user_id")

    if request.method == "POST":
        # Get form data
        description = request.form.get("description")
        amount = request.form.get("amount")
        date = request.form.get("date")

        # Validate form data
        if not description or not amount or not date:
            flash("Please fill in all fields.", "error")
            return redirect("/add_expense")

        # Insert expense transaction into the database
        db.execute(
            "INSERT INTO transactions (username, type, description, amount, date) VALUES (?, 'expense', ?, ?, ?)",
            username,
            description,
            amount,
            date,
        )
        flash("Expense transaction added successfully!", "success")
        return redirect("/expense")

    return render_template("add_expense.html", form=form, active_page="expense")


# Delete Expense Page
@app.route("/delete_expense", methods=["POST"])
@login_required
def delete_expense():
    username = session.get("user_id")

    # Get the transaction_id from the form submission
    transaction_id = request.form.get("transaction_id")

    # Query the database to get the expense transaction by ID
    result = db.execute(
        "SELECT * FROM transactions WHERE id = ? AND type = 'expense' AND username = ?",
        transaction_id,
        username,
    )

    # Check if the result is not empty
    if result:
        transaction = result[0]

        # Delete the transaction from the database
        db.execute("DELETE FROM transactions WHERE id = ?", transaction_id)
        flash("Expense transaction deleted successfully!", "success")
    else:
        flash("Invalid transaction or permission denied.", "error")

    # Redirect back to the expense page
    return redirect("/expense")


# Receipt Generation
@app.route("/generate_receipt", methods=["GET", "POST"])
@login_required
def generate_receipt():
    if request.method == "POST":
        # Retrieve data from the form
        customer_name = request.form.get("customer_name")
        customer_email = request.form.get("customer_email")
        customer_address = request.form.get("customer_address")
        customer_phone = request.form.get("customer_phone")
        customer_vehicle = request.form.get("customer_vehicle")
        vehicle_license_plate = request.form.get("vehicle_license_plate")
        vehicle_mileage = request.form.get("vehicle_mileage")
        receipt_date = request.form.get("receipt_date")

        # Retrieve data for Parts, Labour, Other sections
        parts_items = request.form.getlist("part_description[]")
        parts_costs = request.form.getlist("part_cost[]")
        labour_items = request.form.getlist("labour_description[]")
        labour_costs = request.form.getlist("labour_cost[]")
        other_items = request.form.getlist("other_description[]")
        other_costs = request.form.getlist("other_cost[]")
        # Retrieve data for discount
        discount_input = request.form.get(
            "discount", ""
        )  # Get the input or an empty string if not provided
        discount = (
            float(discount_input) if discount_input else 0
        )  # Convert to float or use 0 if empty

        # Calculate total cost
        total_cost = sum(
            [float(cost) for cost in parts_costs + labour_costs + other_costs]
        )
        discount_value = total_cost * (discount / 100)

        # Generate HTML for receipt
        receipt_template = render_template(
            "receipt_template.html",
            customer_name=customer_name,
            customer_email=customer_email,
            customer_address=customer_address,
            customer_phone=customer_phone,
            customer_vehicle=customer_vehicle,
            vehicle_license_plate=vehicle_license_plate,
            vehicle_mileage=vehicle_mileage,
            receipt_date=receipt_date,
            parts_items=zip(parts_items, parts_costs),
            labour_items=zip(labour_items, labour_costs),
            other_items=zip(other_items, other_costs),
            discount=discount,
            discount_value=discount_value,
            total_cost=total_cost,
        )

        pdf = pdfkit.from_string(receipt_template, False)

        # Serve PDF as a response
        response = make_response(pdf)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = "inline; filename=receipt.pdf"
        return response

    # If not a POST request, render the form
    return render_template("generate_receipt.html", active_page="generate_receipt")


# Customer Database
@app.route("/customers")
@login_required
def customers():
    customers_data = db.execute("SELECT * FROM customers")
    return render_template(
        "customers.html", customers=customers_data, active_page="customers"
    )


# Add Customer
@app.route("/add_customer", methods=["GET", "POST"])
@login_required
def add_customer():
    form = CustomerForm()

    username = session.get("user_id")

    if request.method == "POST" and form.validate():
        # Extract data from the form
        name = form.name.data
        number = form.number.data
        email = form.email.data
        address = form.address.data

        # Insert customer into the database
        db.execute(
            "INSERT INTO customers (username, name, number, email, address) VALUES (?, ?, ?, ?, ?)",
            username,
            name,
            number,
            email,
            address,
        )

        flash("Customer added successfully!", "success")
        return redirect("/customers")

    return render_template("add_customer.html", form=form, active_page="customers")


# Delete Customer
@app.route("/delete_customer", methods=["POST"])
@login_required
def delete_customer():
    username = session.get("user_id")

    # Get the customer_id from the form submission
    customer_id = request.form.get("customer_id")
    print(customer_id)

    # Query the database to get the income transaction by ID
    result = db.execute("SELECT * FROM customers WHERE id = ?", customer_id)

    # Check if the result is not empty
    if result:
        customer = result[0]

        # Check if the transaction belongs to the current user
        if customer["username"] == username:
            # Delete the transaction from the database
            db.execute("DELETE FROM customers WHERE id = ?", customer_id)
            flash("Customer deleted successfully!", "success")
        else:
            flash("Invalid customer or permission denied.", "error")
    else:
        flash("Customer not found.", "error")

    # Redirect back to the income page
    return redirect("/customers")


if __name__ == "__main__":
    app.run(debug=True)
