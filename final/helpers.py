from functools import wraps
from flask import session, redirect
from cs50 import SQL

from datetime import datetime


# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///database.db")


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def calculate_financial_summary(username):
    # Get the current year
    current_year = datetime.now().year
    print(f"CURRENT YEAR: {current_year}")

    # Calculate total income
    total_income_query = "SELECT IFNULL(SUM(amount), 0.0) AS total FROM transactions WHERE type = 'income' AND username = :username AND strftime('%Y', date) = strftime('%Y', :year || '-01-01')"
    total_income_result = db.execute(
        total_income_query, username=username, year=current_year
    )
    total_income = (
        total_income_result[0]["total"]
        if total_income_result and total_income_result[0]["total"] is not None
        else 0.0
    )

    # Print or log the result for debugging
    print(f"Total Income Result: {total_income_result}")

    # Calculate total expenses
    total_expenses_query = "SELECT IFNULL(SUM(amount), 0.0) AS total FROM transactions WHERE type = 'expense' AND username = :username AND strftime('%Y', date) = strftime('%Y', :year || '-01-01')"
    total_expenses_result = db.execute(
        total_expenses_query, username=username, year=current_year
    )
    total_expenses = (
        total_expenses_result[0]["total"]
        if total_expenses_result and total_expenses_result[0]["total"] is not None
        else 0.0
    )

    # Calculate net profit
    net_profit = total_income - total_expenses

    return total_income, total_expenses, net_profit


def get_items(form, section):
    items = []
    index = 1
    while True:
        item_key = f"{section}_item_{index}"
        cost_key = f"{section}_cost_{index}"

        item = form.get(item_key)
        cost = form.get(cost_key)

        if not item or not cost:
            break

        items.append((item, cost))
        index += 1

    return items


def calculate_total_cost(parts_items, labour_items, other_items):
    total_cost = 0.0

    for items in [parts_items, labour_items, other_items]:
        for _, cost in items:
            total_cost += float(cost)

    return total_cost


def usd(value):
    """Format value as USD."""
    return f"{value:,.2f}"


def format_number_with_commas(value):
    return "{:,.2f}".format(float(value))


def format_number_with_commas_no_decimal(value):
    return "{:,.0f}".format(float(value))
