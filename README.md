# YNAB API

The YNAB (You Need A Budget) API is a backend API designed to power the YNAB finance management app. It provides a range of endpoints to manage user data, track transactions, retrieve financial news, and access a financial chatbot. Built with FastAPI, the API leverages advanced tools for data processing, security, and financial analysis.

## 📜 API Endpoints

**Base URL**: [https://api.ynab.in](https://api.ynab.in)

**GitHub Repository**: [https://github.com/RustedShader/ynab_api](https://github.com/RustedShader/ynab_api)

| Endpoint                   | Description                                        |
|----------------------------|----------------------------------------------------|
| `/Create_user`             | Creates a new user account                         |
| `/Link_bank_account`       | Links a bank account to the user's profile         |
| `/Login`                   | Authenticates a user and issues a token            |
| `/Get_latest_finance_news` | Retrieves the latest financial news                |
| `/Create_user_data`        | Adds user-specific data entries                    |
| `/Chatbot`                 | Accesses the financial chatbot for queries         |
| `/Fetch_transactions`      | Retrieves transaction history                      |
| `/Get_user_data`           | Retrieves stored user data                         |

For detailed documentation on each endpoint, please refer to the [API documentation](https://api.ynab.in/docs).

## 🛠️ Key Technologies and Libraries

The YNAB API integrates several technologies and libraries for a smooth and efficient financial management experience:

- **LLM Integration**: Uses large language models like Llama 2 (hosted on Vultr Serverless) for NLP tasks such as expense categorization and answering finance-related queries.
- **Numpy**: Employed for various financial calculations and data processing operations.
- **Faker**: Generates realistic fake data for testing and development environments.
- **Scipy Stats**: Utilized for statistical analysis, including financial scoring based on user data.
- **Statistics Module**: Specifically, `stdev` is used for calculating the standard deviation of financial metrics.
- **Hashlib and Bcrypt**: Ensures data security through password hashing and encryption.
- **ThreadPoolExecutor**: Enables efficient concurrent processing, improving response times for tasks like data aggregation.
- **Financial News API**: Fetches real-time financial news updates to keep users informed.

## 🚀 Setup Instructions

### Prerequisites

- **Python 3.9+**: Required for running the FastAPI server.
- **Dependencies**: See the `requirements.txt` file for the full list of dependencies.

### Installation

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/RustedShader/ynab_api && cd ynab_api
   ```

2. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the FastAPI Server**:

   ```bash
   fastapi dev main.py
   ```

   This command will start the FastAPI server locally, accessible by default at `http://127.0.0.1:8000`.

## 🔍 Testing and Documentation

You can explore the API endpoints and test the functionality directly via the interactive documentation available at `/docs` (Swagger UI) and `/redoc` (ReDoc) once the server is running locally. These tools provide real-time, interactive testing and help clarify the request and response formats for each endpoint.

## 🛡️ Security

The YNAB API implements several security measures to ensure user data protection:

- **Password Encryption**: User passwords are hashed using bcrypt for secure storage.
- **Token-Based Authentication**: Uses JWT tokens for secure session management.
- **Data Encryption**: Sensitive data fields are hashed with hashlib, securing information in transit and at rest.

## 🤝 Contributions

Contributions are welcome! Please follow the standard GitHub process: fork the repo, make changes, and open a pull request. For significant updates, consider discussing your idea first by opening an issue.

---

Thank you for using YNAB API!
