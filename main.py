import base64
from collections import defaultdict
from datetime import datetime
import hashlib
import json
from statistics import stdev
from typing import Counter
import jwt
import mysql.connector
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
import bcrypt
import mysql.connector.aio
import mysql.connector.cursor
import mysql.connector.cursor_cext
import numpy as np
import requests
from news_api import get_latest_finance_news
from llm import categorize_naration , chatbot_test
from contextlib import asynccontextmanager
from datetime import timedelta, timezone
from dotenv import load_dotenv
import os
from scipy import stats
import random
from datetime import datetime, timedelta
from faker import Faker
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

fake = Faker()

class YNAB_API:
    def __init__(
        self, 
        cursor: mysql.connector.cursor_cext.CMySQLCursor, 
        username: str, 
        password: str, 
        secret_key: str
    ) -> None:
        self.username = username
        self.cursor = cursor
        self.password = password
        self.secret_key = secret_key
    

    class get_user_transaction:
        def __init__(
            self,
            cursor: mysql.connector.cursor_cext.CMySQLCursor,
            user_id: int
        ) -> None:
            self.cursor = cursor
            self.user_id = user_id
        def get_all_transactions(self) -> list:
            self.cursor.execute(GET_USER_TRANSACTION_DATA, (self.user_id,))
            transactions = self.cursor.fetchall()
            return transactions
    
    class get_current_user:
        def __init__ (
                self,
                cursor: mysql.connector.cursor_cext.CMySQLCursor,
                api_key: str
        ) -> None:
            self.cursor = cursor
            self.api_key = api_key
        
        def get_user_id_from_api_key(self) -> int | None:
            self.cursor.execute(CHECK_API_KEY, (self.api_key,))
            user_id = self.cursor.fetchone()
            if user_id:
                return int(list(map(str, user_id))[0])  
            return None

    def check_account_linked(self) -> bool:
        self.cursor.execute(CHECK_ACCOUNT_LINK, (self.username,))
        user_account_linked =  self.cursor.fetchone()
        if user_account_linked:
            user_account_linked = list(map(bool, user_account_linked))[0]
            return user_account_linked
        return False
    
    def check_user_exists(self) -> bool:
        self.cursor.execute(CHECK_USER_EXISTS, (self.username,))
        user_id = self.cursor.fetchone()
        if user_id:
            return True
        return False
    
    def get_user_id(self) -> int:
        self.cursor.execute(CHECK_USER_EXISTS, (self.username,))
        user_id = self.cursor.fetchone()
        if user_id:
            user_id = int(list(map(str, user_id))[0])
            return user_id
        return 0

    def check_user_password(self) -> bool:
        self.cursor.execute(CHECK_USER_PASSWORD, (self.username,))
        result = self.cursor.fetchone()
        if result:
            db_password = list(map(str,result))[0]
            if bcrypt.checkpw(base64.b64encode(hashlib.sha256(str.encode(self.password)).digest()), str.encode(db_password)):
                return True
        return False

    def get_user_api_key(self) -> str:
        api_key = jwt.encode({"user_id": self.get_user_id(), "exp": datetime.now(tz=timezone.utc) + timedelta(days=30)}, self.secret_key, algorithm="HS256")
        return api_key

    def update_api_key(self) -> None:
        self.cursor.execute(ADD_API_KEY, (self.get_user_id(), self.get_user_api_key()))
    

                



# Database connection config
DB_CONFIG = {
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": int(str(os.getenv("DB_PORT"))), 
    "database": os.getenv("DB_NAME"),
    "ssl_disabled": False,
}

secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    raise ValueError("SECRET_KEY environment variable is not set")

narration_templates = [
    "ATM Withdrawal - {}",
    "Purchase at {}",
    "Online Purchase - {}",
    "Bill Payment - {}",
    "{} Order - {}",
    "Fund Transfer to {}",
    "UPI Transfer to {}",
    "EMI Payment - {}",
    "Salary Credit",
    "Refund from {}",
    "Cash Deposit at {}",
    "{} Subscription Payment",
]



# API SQL STARTUP queries
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    mobile_number VARCHAR(20) NOT NULL,
    category VARCHAR(255),
    salary_range INT,
    account_link_status BOOL NOT NULL DEFAULT false,
    bank_branch VARCHAR(255),
    ifsc_code VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_API_KEYS_TABLE = """
CREATE TABLE IF NOT EXISTS api_keys (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    api_key VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


CREATE_TRANSACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS transactions (
    txn_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    txn_type VARCHAR(255) NOT NULL,
    txn_mode VARCHAR(255) NOT NULL,
    txn_amount DECIMAL(15, 2) NOT NULL,
    txn_balance DECIMAL(15, 2) NOT NULL,
    txn_timestamp TIMESTAMP NOT NULL,
    txn_value_date DATE NOT NULL,
    txn_narration TEXT,
    txn_reference VARCHAR(255),
    txn_cat TEXT
);
"""

ADD_USER_CREDENTIALS = "INSERT INTO users (username, password, email, mobile_number) VALUES (%s, %s, %s, %s)"
CHECK_USER_EXISTS = "SELECT id FROM users WHERE username = %s"
CHECK_USER_PASSWORD = "SELECT password FROM users WHERE username = %s"
ADD_TRANSACTION_DATA = "INSERT INTO transactions (user_id, txn_type, txn_mode, txn_amount, txn_balance, txn_timestamp, txn_value_date, txn_narration, txn_reference, txn_cat) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
ADD_USER_DATA = "UPDATE users SET bank_branch = %s, ifsc_code = %s WHERE id = %s"
GET_USER_TRANSACTION_DATA = "SELECT txn_type, txn_mode, txn_amount, txn_balance, txn_timestamp, txn_value_date, txn_narration, txn_reference, txn_cat FROM transactions WHERE user_id = %s"
CHECK_ACCOUNT_LINK = "SELECT account_link_status FROM users WHERE username = %s"
ADD_ACCOUNT_LINK = "UPDATE users SET account_link_status = true WHERE id = %s"
ADD_API_KEY = "INSERT INTO api_keys (user_id, api_key) VALUES (%s, %s)"
CHECK_API_KEY = "SELECT user_id FROM api_keys WHERE api_key = %s"
GET_USER_DATA = "SELECT * FROM users WHERE id = %s"

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            cursor = cnx.cursor()
            cursor.execute(CREATE_USERS_TABLE)
            cursor.execute(CREATE_API_KEYS_TABLE)
            cursor.execute(CREATE_TRANSACTIONS_TABLE)
            cnx.commit()
            cursor.close()
            yield
    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:8080",
     "http://localhost:8081",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_user(request: Request):
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key missing in the headers"
        )
    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            cursor = cnx.cursor()
            if type(cursor) is mysql.connector.cursor_cext.CMySQLCursor:
                ynab_api = YNAB_API.get_current_user(cursor,api_key)
                user_id = ynab_api.get_user_id_from_api_key()
                print(user_id)
                if not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid API key"
                    )
                print(user_id)
                return user_id
    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )

@app.post("/create_user")
async def create_user(request: Request):
    username = request.headers.get("username")
    password = request.headers.get("password")
    email_id = request.headers.get("email_id")
    mobile_number = request.headers.get("mobile_number")
    salary_range = request.headers.get("salary_range")

    if not username or not password or not email_id or not mobile_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username, password, email, or mobile number not provided in headers"
        )

    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            cursor = cnx.cursor()

            # Check if the user already exists
            cursor.execute(CHECK_USER_EXISTS, (username,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User already exists"
                )

            # Insert the new user
            hashed_password = bcrypt.hashpw(base64.b64encode(hashlib.sha256(str.encode(password)).digest()), bcrypt.gensalt())
            cursor.execute(ADD_USER_CREDENTIALS, (username, hashed_password, email_id, mobile_number))
            cnx.commit()
            return {"message": "user_created"}

    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )


@app.post("/link_bank_account")
async def link_bank_account(user_id: int = Depends(get_current_user)):
    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            cursor = cnx.cursor()
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not exist"
                )
            cursor.execute(ADD_ACCOUNT_LINK, (user_id,))
            cnx.commit()
            return {"message": "bank_account_linked" }

    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
    


@app.post("/login")
async def login_user(request: Request) -> dict | None:
    username = request.headers.get("username")
    password = request.headers.get("password")

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Username or password not provided in the headers"
        )

    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            cursor = cnx.cursor()
            if type(cursor) is mysql.connector.cursor_cext.CMySQLCursor:
                if secret_key:
                    ynab_api = YNAB_API(cursor, username, password , secret_key)
                    user_exists = ynab_api.check_user_exists()
                    if not user_exists:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="User does not exist"
                        )
                
                    is_account_linked = ynab_api.check_account_linked()
                    is_password_correct = ynab_api.check_user_password()
                    if is_password_correct:
                        api_key = ynab_api.get_user_api_key()
                        ynab_api.update_api_key()
                        cnx.commit()
                        return {"message": "user_verified", "user_account_linked": is_account_linked , "api_key": api_key }
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid password"
                        )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="cursor type error"
                )
    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )


@app.get("/get_latest_finance_news")
async def get_latest_news(user_id: int = Depends(get_current_user)) -> dict | None:
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )
    news_json = get_latest_finance_news()
    if news_json:
        return news_json
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No finance news found"
        )

@app.post("/create_user_data")
async def create_user_data(user_id: int = Depends(get_current_user)):
    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            cursor = cnx.cursor(prepared=True)
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not exist"
                )
            random_user_data = generate_fake_account_data()
            if random_user_data:
                transactions = random_user_data['Account']['Transactions']['Transaction']
                transaction_data = []
                with ThreadPoolExecutor() as executor:
                    futures = []
                    for transaction in transactions:
                        txn_type = transaction['_type']
                        txn_mode = transaction['_mode']
                        txn_amount = transaction['_amount']
                        txn_balance = transaction['_currentBalance']
                        txn_timestamp = transaction['_transactionTimestamp']
                        txn_value_date = transaction['_valueDate']
                        txn_narration = transaction['_narration']
                        txn_reference = transaction['_reference']
                        futures.append(executor.submit(categorize_naration_with_timeout, txn_narration))

                    for transaction, future in zip(transactions, asyncio.as_completed([asyncio.wrap_future(f) for f in futures])):
                        try:
                            txn_cat = await future
                        except asyncio.TimeoutError:
                            txn_cat = 'UNCATEGORIZED'
                        txn_type = transaction['_type']
                        txn_mode = transaction['_mode']
                        txn_amount = transaction['_amount']
                        txn_balance = transaction['_currentBalance']
                        txn_timestamp = transaction['_transactionTimestamp']
                        txn_value_date = transaction['_valueDate']
                        txn_narration = transaction['_narration']
                        txn_reference = transaction['_reference']
                        transaction_data.append((user_id, txn_type, txn_mode, txn_amount, txn_balance, txn_timestamp, txn_value_date, txn_narration, txn_reference, txn_cat))

                cursor.executemany(ADD_TRANSACTION_DATA, transaction_data)
                cursor.execute(ADD_USER_DATA, (random_user_data['Account']['Summary']['_branch'], random_user_data['Account']['Summary']['_ifscCode'], user_id))
                cnx.commit()
                return {"message": "added_initial_transacrtions"}
    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )

def categorize_naration_with_timeout(input_prompt: str) -> str:
    try:
        return categorize_naration(input_prompt)
    except (requests.exceptions.Timeout, asyncio.TimeoutError):
        return 'UNCATEGORIZED'

@app.post('/chatbot')
async def chatbot(request: Request , user_id: int = Depends(get_current_user)):
    chat_arr = request.headers.get('chat')
    if not chat_arr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat history not found in the headers"
        )

    try:
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not exist"
                )
            chatbot_response = chatbot_test(chat_arr) 
            if chatbot_response:
                return {"response": chatbot_response}

    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API error: {err}"
        )


@app.post("/fetch_transactions")
async def fetch_user_transaction(user_id: int = Depends(get_current_user)) -> dict | None:
    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            if secret_key:
                cursor = cnx.cursor()
                if type(cursor) is mysql.connector.cursor_cext.CMySQLCursor:
                    if not user_id:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="User does not exist"
                        )
                    ynab_api = YNAB_API.get_user_transaction(cursor, user_id)
                    transactions = ynab_api.get_all_transactions()
                    transaction_entities = [
                        {
                            "_type": txn[0], 
                            "_mode": txn[1], 
                            "_amount": txn[2], 
                            "_currentBalance": txn[3], 
                            "_transactionTimestamp": txn[4], 
                            "_valueDate": txn[5], 
                            "_narration": txn[6], 
                            "_reference": txn[7], 
                            "_transactionCategory": txn[8] 
                        }
                        for txn in transactions
                    ]

                    return {"transactions": transaction_entities}

    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )

@app.post("/get_user_data")
async def get_user_data(user_id: int = Depends(get_current_user)):
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not exist"
            )
        try:
            with mysql.connector.connect(**DB_CONFIG) as cnx:
                cursor = cnx.cursor()
                cursor.execute(GET_USER_DATA, (user_id,))
                result = cursor.fetchone()
                if result is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User data not found"
                    )
                user_data = list(map(str, result))
                if user_data:
                    return {
                        "username": user_data[1],
                        "email": user_data[3],
                        "mobile_number": int(user_data[4]),
                        "category": user_data[5],
                        "salary_range": user_data[6],
                        "account_link_status": user_data[7],
                        "bank_branch": user_data[8],
                        "ifsc_code": user_data[9]
                    }
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User data not found"
                    )
        except mysql.connector.Error as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {err}"
            )

@app.post("/user_financial_data")
async def user_financial_data(user_id: int = Depends(get_current_user)):
    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not exist"
                )
            cursor = cnx.cursor()
            if type(cursor) is mysql.connector.cursor_cext.CMySQLCursor:
                ynab_api = YNAB_API.get_user_transaction(cursor, user_id)
                transactions = ynab_api.get_all_transactions()
                transaction_entities = [
                    {
                        "_type": str(txn[0]), 
                        "_mode": str(txn[1]), 
                        "_amount": float(txn[2]), 
                        "_currentBalance": float(txn[3]), 
                        "_transactionTimestamp": datetime.strptime(str(txn[4]), '%Y-%m-%d %H:%M:%S'), 
                        "_valueDate": datetime.strptime(str(txn[5]), '%Y-%m-%d'), 
                        "_narration": str(txn[6]), 
                        "_reference": str(txn[7]), 
                        "_transactionCategory": str(txn[8]) 
                    }
                    for txn in transactions
                ]

                cash_outflow = 0
                cash_inflow = 0
                transaction_amounts = []
                categories_list = []
                merchants_list = []
                daily_spending = {}
                
                max_spent_on = transaction_entities[0]["_narration"]
                max_spent = transaction_entities[0]["_amount"]
                max_spent_category = transaction_entities[0]["_transactionCategory"]
                max_spent_on_date = transaction_entities[0]["_valueDate"]
                least_spent = transaction_entities[0]["_amount"]
                least_spent_on = transaction_entities[0]["_narration"]
                least_spent_on_date = transaction_entities[0]["_valueDate"]
                least_spent_category = transaction_entities[0]["_transactionCategory"]

                # Process transactions
                for transaction in transaction_entities:
                        # Collect transaction amounts for average calculation
                        transaction_amounts.append(transaction["_amount"])
                        
                        # Collect categories and merchants for frequency analysis
                        categories_list.append(transaction["_transactionCategory"])
                        merchants_list.append(transaction["_narration"])
                        
                        # Track daily spending for velocity calculation
                        date_key = transaction["_valueDate"].date()
                        if transaction["_type"] == "DEBIT":
                            daily_spending[date_key] = daily_spending.get(date_key, 0) + transaction["_amount"]

                        # Original cash flow calculations
                        if transaction["_type"] == "DEBIT":
                            cash_outflow += transaction["_amount"]
                            if transaction["_amount"] > max_spent:
                                max_spent = transaction["_amount"]
                                max_spent_on = transaction["_narration"]
                                max_spent_on_date = transaction["_valueDate"]
                                max_spent_category = transaction["_transactionCategory"]
                        elif transaction["_type"] == "CREDIT":
                            cash_inflow += transaction["_amount"]
                            if transaction["_amount"] < least_spent:
                                least_spent = transaction["_amount"]
                                least_spent_on = transaction["_narration"]
                                least_spent_on_date = transaction["_valueDate"]
                                least_spent_category = transaction["_transactionCategory"]

                # Calculate new metrics
                savings = cash_inflow - cash_outflow
                
                # 1. Average Transaction Size
                avg_transaction_size = sum(transaction_amounts) / len(transaction_amounts) if transaction_amounts else 0
                
                # 2. Savings Ratio (as percentage)
                savings_ratio = (savings / cash_inflow * 100) if cash_inflow > 0 else 0
                
                # 3. Most Frequent Categories (top 5)
                category_frequency = Counter(categories_list)
                most_frequent_categories = dict(category_frequency.most_common(5))
                
                # 4. Common Merchants/Narrations (top 5)
                merchant_frequency = Counter(merchants_list)
                common_merchants = dict(merchant_frequency.most_common(5))
                
                # 5. Spending Velocity (average daily spending)
                avg_daily_spending = sum(daily_spending.values()) / len(daily_spending) if daily_spending else 0

                income_transactions = [t["_amount"] for t in transaction_entities if t["_type"] == "CREDIT"]
                expense_transactions = [t["_amount"] for t in transaction_entities if t["_type"] == "DEBIT"]

                income_consistency = stdev(income_transactions) if len(income_transactions) > 1 else 0
                spending_consistency = stdev(expense_transactions) if len(expense_transactions) > 1 else 0

                category_spending = {}
                for transaction in transaction_entities:
                    if transaction["_type"] == "DEBIT":
                        category = transaction["_transactionCategory"]
                        category_spending[category] = category_spending.get(category, 0) + transaction["_amount"]
                
                recurring_transactions = {}
                for transaction in transaction_entities:
                    narration = transaction["_narration"]
                    recurring_transactions[narration] = recurring_transactions.get(narration, 0) + transaction["_amount"]

                def calculate_trend_metrics(transactions_list):
                    """Calculate spending trends and patterns"""
                    dates = [t["_valueDate"] for t in transactions_list]
                    amounts = [t["_amount"] for t in transactions_list]
                    
                    if len(dates) > 1:
                        z = np.polyfit(range(len(dates)), amounts, 1)
                        trend = "increasing" if z[0] > 0 else "decreasing"
                        trend_strength = abs(z[0])
                    else:
                        trend = "insufficient data"
                        trend_strength = 0
                    
                    return trend, trend_strength

                def calculate_seasonality(transactions_list):
                    """Detect weekly and monthly spending patterns"""
                    daily_totals = defaultdict(float)
                    monthly_totals = defaultdict(float)
                    
                    for t in transactions_list:
                        if t["_type"] == "DEBIT":
                            daily_totals[t["_valueDate"].strftime("%A")] += t["_amount"]
                            monthly_totals[t["_valueDate"].strftime("%d")] += t["_amount"]
                    
                    return {
                        "daily_pattern": dict(daily_totals),
                        "monthly_pattern": dict(monthly_totals)
                    }

                def calculate_financial_health_score(metrics):
                    """
                    Calculate overall financial health score (0-100)
                    
                    Parameters:
                    metrics (dict): Dictionary containing financial metrics
                        - savings_ratio: Percentage of income saved
                        - spending_consistency: Standard deviation of spending
                        - income_consistency: Standard deviation of income
                        - spending_velocity: Average daily spending
                    
                    Returns:
                    float: Financial health score between 0 and 100
                    """
                    # 1. Savings Score (0-30 points)
                    savings_score = min(metrics["savings_ratio"] / 3, 30)  # 90% savings ratio would give max points
                    
                    # 2. Spending Consistency Score (0-20 points)
                    # Lower consistency number is better, normalize against average transaction size
                    consistency_baseline = 1000  # Baseline for normalization
                    spending_consistency_score = 20 * (1 - min(metrics["spending_consistency"] / consistency_baseline, 1))
                    
                    # 3. Income Consistency Score (0-20 points)
                    # For income, we want to normalize against the average income
                    income_baseline = metrics["cash_inflow"] / 2  # Using half of total inflow as baseline
                    income_consistency_score = 20 * (1 - min(metrics["income_consistency"] / income_baseline, 1))
                    
                    # 4. Spending Velocity Score (0-30 points)
                    # Compare daily spending against monthly income
                    daily_income = metrics["cash_inflow"] / 30
                    velocity_score = 30 * (1 - min(metrics["spending_velocity"] / daily_income, 1))
                    
                    # Calculate total score
                    total_score = (
                        savings_score + 
                        spending_consistency_score + 
                        income_consistency_score + 
                        velocity_score
                    )
                    
                    # Ensure score is between 0 and 100
                    return max(min(total_score, 100), 0)

                def analyze_spending_categories(transactions_list):
                    """Detailed category analysis with benchmarks"""
                    category_data = defaultdict(list)
                    for t in transactions_list:
                        if t["_type"] == "DEBIT":
                            category_data[t["_transactionCategory"]].append(t["_amount"])
                    
                    category_analysis = {}
                    for category, amounts in category_data.items():
                        category_analysis[category] = {
                            "total": sum(amounts),
                            "average": np.mean(amounts),
                            "volatility": stdev(amounts) if len(amounts) > 1 else 0,
                            "frequency": len(amounts)
                        }
                    return category_analysis

                def detect_anomalies(transactions_list):
                    """Detect unusual spending patterns"""
                    amounts = [t["_amount"] for t in transactions_list if t["_type"] == "DEBIT"]
                    if len(amounts) > 2:
                        z_scores = stats.zscore(amounts)
                        anomalies = [(transactions_list[i], z_scores[i]) 
                                for i in range(len(z_scores)) 
                                if abs(z_scores[i]) > 2]
                        return anomalies
                    return []

                def predict_future_expenses(transactions_list):
                    """Simple expense prediction for next month"""
                    recurring_expenses = defaultdict(list)
                    for t in transactions_list:
                        if t["_type"] == "DEBIT":
                            recurring_expenses[t["_narration"]].append(t["_amount"])
                    
                    predictions = {}
                    for merchant, amounts in recurring_expenses.items():
                        if len(amounts) >= 2:  # Only predict if we have at least 2 occurrences
                            predictions[merchant] = np.mean(amounts)
                    
                    return predictions

                # Calculate new metrics
                spending_trend, trend_strength = calculate_trend_metrics(transaction_entities)
                seasonality_patterns = calculate_seasonality(transaction_entities)
                financial_health_score = calculate_financial_health_score({
                    "savings_ratio": savings_ratio,
                    "spending_consistency": spending_consistency,
                    "income_consistency": income_consistency,
                    "spending_velocity": avg_daily_spending,
                    "cash_inflow": cash_inflow
                })
                detailed_category_analysis = analyze_spending_categories(transaction_entities)
                spending_anomalies = detect_anomalies(transaction_entities)
                predicted_expenses = predict_future_expenses(transaction_entities)

                # Enhanced return dictionary
                return {
                    "basic_metrics": {
                        "cash_inflow": cash_inflow,
                        "cash_outflow": cash_outflow,
                        "savings": savings,
                        "savings_ratio": round(savings_ratio, 2)
                    },
                    "transaction_extremes": {
                        "highest_expense": {
                            "amount": max_spent,
                            "description": max_spent_on,
                            "date": max_spent_on_date,
                            "category": max_spent_category
                        },
                        "lowest_transaction": {
                            "amount": least_spent,
                            "description": least_spent_on,
                            "date": least_spent_on_date,
                            "category": least_spent_category
                        }
                    },
                    "advanced_metrics": {
                        "average_transaction_size": round(avg_transaction_size, 2),
                        "spending_velocity": round(avg_daily_spending, 2),
                        "most_frequent_categories": most_frequent_categories,
                        "common_merchants": common_merchants,
                        "income_consistency": round(income_consistency, 2),
                        "spending_consistency": round(spending_consistency, 2),
                        "category_spending": category_spending,
                        "recurring_transactions": recurring_transactions
                    },
                    "predictive_analytics": {
                        "spending_trend": {
                            "direction": spending_trend,
                            "strength": round(trend_strength, 2)
                        },
                        "seasonality": seasonality_patterns,
                        "predicted_expenses": predicted_expenses
                    },
                    "financial_health": {
                        "overall_score": round(financial_health_score, 2),
                        "category_analysis": detailed_category_analysis,
                        "spending_anomalies": [
                            {
                                "transaction": anomaly[0],
                                "deviation_score": round(anomaly[1], 2)
                            } 
                            for anomaly in spending_anomalies
                        ]
                    }
                }

    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )



def generate_fake_transaction(current_balance, index):
    txn_types = ["DEBIT", "CREDIT"]
    modes = ["OTHERS", "ATM", "UPI", "ONLINE", "BANK_TRANSFER", "POS"]
    amount = random.uniform(10, 5000) if index % 3 else random.uniform(500, 10000)
    txn_type = random.choice(txn_types)
    transaction_date = datetime.now() - timedelta(days=index * random.randint(1, 3))

    template = random.choice(narration_templates)
    placeholders = template.count("{}")
    if placeholders == 1:
        narration = template.format(fake.company())
    elif placeholders == 2:
        narration = template.format(fake.company(), fake.company_suffix())
    else:
        narration = template

    # Update the current balance based on the transaction type
    if txn_type == "DEBIT":
        current_balance -= amount
    else:
        current_balance += amount

    return {
        "_txnId": f"M{random.randint(100000, 999999)}",
        "_type": txn_type,
        "_mode": random.choice(modes),
        "_amount": f"{amount:.2f}",
        "_currentBalance": f"{current_balance:.2f}",
        "_transactionTimestamp": transaction_date.isoformat(),
        "_valueDate": transaction_date.date().isoformat(),
        "_narration": narration,
        "_reference": fake.bothify(text="REF#######")
    }

def generate_fake_account_data(transaction_count=50):
    current_balance = random.uniform(10000, 100000)
    pending_balance = 0
    transactions = []

    for i in range(transaction_count):
        # Generate the transaction and update the current balance
        transaction = generate_fake_transaction(current_balance, i)
        transactions.append(transaction)
        current_balance = float(transaction["_currentBalance"])

        # Optionally track pending balance for certain conditions
        if transaction["_mode"] == "PENDING":  # Define your condition for pending here
            pending_balance += float(transaction["_amount"])

    return {
        "Account": {
            "Profile": {
                "Holders": {
                    "Holder": {
                        "_name": fake.name(),
                        "_dob": fake.date_of_birth(minimum_age=18, maximum_age=65).isoformat(),
                        "_mobile": fake.phone_number(),
                        "_nominee": random.choice(["REGISTERED", "NOT-REGISTERED"]),
                        "_email": fake.email(),
                        "_pan": fake.bothify(text="?????#####?"),
                        "_ckycCompliance": random.choice(["true", "false"])
                    },
                    "_type": random.choice(["JOINT", "SINGLE"])
                }
            },
            "Summary": {
                "Pending": {"_amount": f"{pending_balance:.2f}"},
                "_currentBalance": f"{current_balance:.2f}",
                "_currency": "INR",
                "_exchgeRate": f"{random.uniform(3, 7):.2f}",
                "_balanceDateTime": fake.iso8601(),
                "_type": random.choice(["CURRENT", "SAVINGS"]),
                "_branch": fake.city(),
                "_facility": random.choice(["CC", "OD"]),
                "_ifscCode": fake.bothify(text="????0??????"),
                "_micrCode": fake.bothify(text="#########"),
                "_openingDate": fake.date_between(start_date="-10y", end_date="today").isoformat(),
                "_currentODLimit": str(random.randint(10000, 50000)),
                "_drawingLimit": str(random.randint(5000, 25000)),
                "_status": random.choice(["ACTIVE", "INACTIVE", "CLOSED"])
            },
            "Transactions": {
                "Transaction": transactions,
                "_startDate": fake.date_between(start_date="-2y", end_date="-1y").isoformat(),
                "_endDate": fake.date_between(start_date="-1y", end_date="today").isoformat()
            },
            "_xmlns": "http://api.rebit.org.in/FISchema/deposit",
            "_xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "_xsi:schemaLocation": "http://api.rebit.org.in/FISchema/deposit ../FISchema/deposit.xsd",
            "_linkedAccRef": fake.bothify(text="REF##########"),
            "_maskedAccNumber": fake.bothify(text="##########"),
            "_version": "1.0",
            "_type": "deposit"
        }
    }


if __name__ == '__main__':
    print('Use "fastapi dev main.py" to run the server')
    print(generate_fake_account_data())
    quit()