from dotenv import load_dotenv
import requests
import os


load_dotenv()

API_TOKEN = os.getenv("VULTR_SERVERLESS_API_KEY")
MODEL = "zephyr-7b-beta-Q5_K_M"
api_base_url = "https://api.vultrinference.com"
headers = {"Authorization": f"Bearer {API_TOKEN}"}

def categorize_naration(input_prompt: str) -> str | None:
    data = {
        "model": MODEL,
        "max_tokens": 10,
        "messages": [
            {
                "role": "user",
                "content": f'''Categorize the payment narration based on the following rules:
                
                1. If the narration contains the name of a food or food-related establishment (e.g., restaurant, cafe, bakery, etc.), categorize it as FOOD.
                2. If the narration does not contain a food or food-related establishment name, categorize it based on the following categories:
                   - ENTERTAINMENT
                   - FOOD
                   - LIFESTYLE
                   - EDUCATION
                   - SHOPPING
                   - ECOMMERCE
                   - TRAVEL
                   - UTILITIES
                   - SERVICES
                   - GENERAL
                3. If the narration cannot be categorized into any of the above, return UNCATEGORIZED.
                
                The payment narration is provided as a single string within double quotes. Do not include any explanation or additional text, just return the category.
                
                Narration: "{input_prompt}"''',
            }
        ],
    }

    response = requests.post(
        f"{api_base_url}/v1/chat/completions", headers=headers, json=data
    ).json()

    if response and 'choices' in response and response['choices']:
        category = response['choices'][0]['message']['content'].strip()
        print(input_prompt)
        print(category)
        
        # Check if the output contains any of the expected keywords
        if any(keyword in category for keyword in ['ENTERTAINMENT', 'LIFESTYLE', 'EDUCATION', 'SHOPPING', 'ECOMMERCE', 'TRAVEL', 'UTILITIES', 'SERVICES', 'GENERAL' , 'FOOD']):
            for keyword in ['ENTERTAINMENT', 'LIFESTYLE', 'EDUCATION', 'SHOPPING', 'ECOMMERCE', 'TRAVEL', 'UTILITIES', 'SERVICES', 'GENERAL' , 'FOOD']:
                if keyword in category:
                    print(keyword)
                    return keyword
        else:
            return 'UNCATEGORIZED'
    else:
        return 'UNCATEGORIZED'


def fetch_financial_tips():
   data = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": "give 10 financial tips for saving money. Do not include any explanation or additional text, just return the finacial tips for saving money"
            }
        ],
        "temperature": 1.0
    } 
   response = requests.post(f"{api_base_url}/v1/chat/completions", headers=headers, json=data).json()
   category = response['choices'][0]['message']['content'].strip()
   return category


def chatbot_test(arr):
    MODEL = 'llama2-13b-chat-Q5_K_M' 
    history_context = ''.join(arr[:-1])
    current_context = arr[-1]
    
    data = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": f'This is users chat history with finacial chatbot: {history_context}. Answer his new financial question on basis of domain of previous conversations. You are a finance chatbot now and will respond like one.  Never ever response anything that is not related to finance. If current question is not related to finance please just response with I cannot help you with that. Please dont response with Based on your previous interactions just reply the question asked. Question is: {current_context}'
            }],
    }
    response = requests.post(f"{api_base_url}/v1/chat/completions", headers=headers, json=data).json()
    category = response['choices'][0]['message']['content'].strip()
    return category

if __name__ == '__main__':
    input_conversations = ["what are stocks in finance", "ok so in which stock should i apply for" , "tell some famous stocks of india"]
    print(chatbot_test(input_conversations))