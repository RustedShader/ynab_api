from dotenv import load_dotenv
import requests
import os

load_dotenv()

API_KEY = os.getenv("NEWS_API_KEY")

def get_latest_finance_news():
    url = f"https://api.marketaux.com/v1/news/all?language=en&api_token={API_KEY}&countries=in"
    response = requests.request("GET", url).json()
    if response:
        return response

if __name__ == "__main__":
    print(get_latest_finance_news())
