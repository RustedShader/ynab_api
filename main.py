import base64
import datetime
import hashlib
import json
import jwt
import mysql.connector
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
import bcrypt
from news_api import get_latest_finance_news
from llm import categorize_naration
from contextlib import asynccontextmanager
from datetime import timedelta, timezone
from dotenv import load_dotenv
import os


load_dotenv()

# Database connection config
DB_CONFIG = {
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": int(str(os.getenv("DB_PORT"))), 
    "database": os.getenv("DB_NAME"),
    "ssl_disabled": False,
}





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
    txn_cat TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

ADD_USER_CREDENTIALS = "INSERT INTO users (username, password, email, mobile_number) VALUES (%s, %s, %s, %s)"
CHECK_USER_EXISTS = "SELECT id FROM users WHERE username = %s"
CHECK_USER_PASSWORD = "SELECT password FROM users WHERE username = %s"
ADD_TRANSACTION_DATA = "INSERT INTO transactions (user_id, txn_type, txn_mode, txn_amount, txn_balance, txn_timestamp, txn_value_date, txn_narration, txn_reference, txn_cat) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
GET_USER_TRANSACTION_DATA = "SELECT txn_type, txn_mode, txn_amount, txn_balance, txn_timestamp, txn_value_date, txn_narration, txn_reference, txn_cat FROM transactions WHERE user_id = %s"
CHECK_ACCOUNT_LINK = "SELECT account_link_status FROM users WHERE username = %s"
ADD_ACCOUNT_LINK = "UPDATE users SET account_link_status = true WHERE username = %s"
ADD_API_KEY = "INSERT INTO api_keys (user_id, api_key) VALUES (%s, %s)"
CHECK_API_KEY = "SELECT user_id FROM api_keys WHERE api_key = %s"


with open('client_data.json', 'r') as f:
    user_json = json.load(f)

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
    allow_origins=origins,
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
            cursor.execute(CHECK_API_KEY, (api_key,))
            user_id = cursor.fetchone()
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )

            return user_id[0] # type: ignore

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
async def link_bank_account(request: Request, user_id: int = Depends(get_current_user)):
    username = request.headers.get("username")

    if not username :
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Username or password not provided in the headers"
        )

    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            cursor = cnx.cursor()
            cursor.execute(CHECK_USER_EXISTS, (username,))
            user_id = cursor.fetchone() # type: ignore
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not exist"
                )
            cursor.execute(ADD_ACCOUNT_LINK, (username,))
            cnx.commit()
            return {"message": "bank_account_linked" }

    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
    


@app.post("/login")
async def login_user(request: Request):
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
            cursor.execute(CHECK_USER_EXISTS, (username,))
            user_id = cursor.fetchone()
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not exist"
                )
            cursor.execute(CHECK_ACCOUNT_LINK, (username,))
            user_account_linked = cursor.fetchone()[0] # type: ignore
            cursor.execute(CHECK_USER_PASSWORD, (username,))
            result = cursor.fetchone()
            if result:
                db_password = str(result[0]) # type: ignore
                if bcrypt.checkpw(base64.b64encode(hashlib.sha256(str.encode(password)).digest()), str.encode(db_password)):
                    api_key = jwt.encode({"user_id": user_id[0], "exp": datetime.datetime.now(tz=timezone.utc) + timedelta(days=30)}, "YNABISTHEBEST", algorithm="HS256") # type: ignore
                    cursor.execute(ADD_API_KEY, (user_id[0], api_key)) # type: ignore
                    cnx.commit()
                    return {"message": "user_verified", "user_account_linked": user_account_linked , "api_key": api_key }
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid password"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not exist"
                )

    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )

@app.get("/get_latest_finance_news")
async def get_latest_news(user_id: int = Depends(get_current_user)):
    news_json = get_latest_finance_news()
    if news_json:
        return news_json
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No finance news found"
        )

@app.post("/create_user_data")
async def create_user_data(request: Request , user_id: int = Depends(get_current_user)):
    username = request.headers.get('username')

    if not username:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Username not found in the headers"
        )

    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            cursor = cnx.cursor()
            cursor.execute(CHECK_USER_EXISTS, (username,))
            user_id = cursor.fetchone() # type: ignore
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not exist"
                )

            user_id = user_id[0] # type: ignore

            # Insert each transaction
            if user_json:
                transactions = user_json['Account']['Transactions']['Transaction']
                for transaction in transactions:
                    txn_type = transaction['_type']
                    txn_mode = transaction['_mode']
                    txn_amount = transaction['_amount']
                    txn_balance = transaction['_currentBalance']
                    txn_timestamp = transaction['_transactionTimestamp']
                    txn_value_date = transaction['_valueDate']
                    txn_narration = transaction['_narration']
                    txn_reference = transaction['_reference']
                    txn_cat = categorize_naration(txn_narration)

                    # Insert the transaction data
                    cursor.execute(ADD_TRANSACTION_DATA, (user_id, txn_type, txn_mode, txn_amount, txn_balance, txn_timestamp, txn_value_date, txn_narration, txn_reference, txn_cat)) # type: ignore

                # Commit all transaction inserts
                cnx.commit()

            return {"message": "Added initial transactions"}

    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )

@app.post("/fetch_transactions")
async def fetch_user_transactions(request: Request , user_id: int = Depends(get_current_user)):
    username = request.headers.get('username')

    if not username:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Username not found in the headers"
        )

    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            cursor = cnx.cursor()
            cursor.execute(CHECK_USER_EXISTS, (username,))
            user_id = cursor.fetchone() # type: ignore
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not exist"
                )

            user_id = user_id[0] # type: ignore
            cursor.execute(GET_USER_TRANSACTION_DATA, (user_id,)) # type: ignore
            transactions = cursor.fetchall()
            transaction_entities = [
                {
                    # "_txnId": str(txn[0]), # type: ignore
                    "_type": txn[0], # type: ignore
                    "_mode": txn[1], # type: ignore
                    "_amount": txn[2], # type: ignore
                    "_currentBalance": txn[3], # type: ignore
                    "_transactionTimestamp": txn[4], # type: ignore
                    "_valueDate": txn[5], # type: ignore
                    "_narration": txn[6], # type: ignore
                    "_reference": txn[7], # type: ignore
                    "_transactionCategory": txn[8]  # type: ignore # Deriving category based on narration
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
async def get_user_data(request: Request , user_id: int = Depends(get_current_user)):
    username = request.headers.get("username")

    if not username:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Username not found in the headers"
        )

    try:
        with mysql.connector.connect(**DB_CONFIG) as cnx:
            cursor = cnx.cursor()
            cursor.execute(CHECK_USER_EXISTS, (username,))
            user_id = cursor.fetchone() # type: ignore
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not exist"
                )

            return user_json

    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )