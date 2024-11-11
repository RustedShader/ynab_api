from dotenv import load_dotenv
import requests
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import SecretStr
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph

load_dotenv()

API_TOKEN = os.getenv("VULTR_SERVERLESS_API_KEY")
MODEL = "zephyr-7b-beta-Q5_K_M"
api_base_url = "https://api.vultrinference.com"
headers = {"Authorization": f"Bearer {API_TOKEN}"}


# prompt = ChatPromptTemplate.from_messages(
#     [
#         (
#             "system",
#             "You talk like a financial chatbot. Answer all questions to the best of your ability.",
#         ),
#         MessagesPlaceholder(variable_name="messages"),
#     ]
# )


# Define a new graph
workflow = StateGraph(state_schema=MessagesState)

import requests

def categorize_naration(input_prompt: str) -> str:
    # First, try to categorize using the rule-based approach
    category = categorize_naration_rule_based(input_prompt)
    if category != "UNCATEGORIZED":
        return category

    # If the rule-based approach fails, use the LLM-based categorization
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
        
        # Check if the output contains any of the expected keywords
        if any(keyword in category for keyword in ['ENTERTAINMENT', 'LIFESTYLE', 'EDUCATION', 'SHOPPING', 'ECOMMERCE', 'TRAVEL', 'UTILITIES', 'SERVICES', 'GENERAL' , 'FOOD']):
            for keyword in ['ENTERTAINMENT', 'LIFESTYLE', 'EDUCATION', 'SHOPPING', 'ECOMMERCE', 'TRAVEL', 'UTILITIES', 'SERVICES', 'GENERAL' , 'FOOD']:
                if keyword in category:
                    return keyword
        else:
            return 'UNCATEGORIZED'
    
    return 'UNCATEGORIZED'

def categorize_naration_rule_based(input_prompt: str) -> str:
    category_keywords = {
        "FOOD": ["restaurant", "cafe", "bakery", "food"],
        "ENTERTAINMENT": ["movie", "concert", "theater", "entertainment"],
        "LIFESTYLE": ["gym", "salon", "spa", "lifestyle"],
        "EDUCATION": ["school", "university", "education"],
        "SHOPPING": ["retail", "shopping", "apparel"],
        "ECOMMERCE": ["online", "website", "ecommerce"],
        "TRAVEL": ["hotel", "airline", "travel"],
        "UTILITIES": ["electricity", "water", "utilities"],
        "SERVICES": ["service", "professional", "consultant"],
        "GENERAL": ["general", "miscellaneous"]
    }

    # First, check if the narration contains any food-related keywords
    if any(keyword in input_prompt.lower() for keyword in category_keywords["FOOD"]):
        return "FOOD"

    # Then, check the narration against the other categories
    for category, keywords in category_keywords.items():
        if category != "FOOD" and any(keyword in input_prompt.lower() for keyword in keywords):
            return category

    return "UNCATEGORIZED"


def test():
    MODEL2 = 'llama2-13b-chat-Q5_K_M' 
    messages = [
    HumanMessage(content="What is the capital of India?"),
]
    client = ChatOpenAI(api_key=SecretStr(str(API_TOKEN)), base_url='https://api.vultrinference.com/v1' ,model=MODEL2)
    llm_response = client.invoke(messages)
    print(llm_response.content)
    
    
    
    

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
    messages = [
    HumanMessage(content=f'You are a finace chatbot now and will respond like one. You have to reply to question that user asked. This is chat history of user with a finace chatbot: {history_context}.   Answer financial question that user asked with help of chat history if needed for the response of question that user asked.   Never ever response anything that is not related to finance. If current question is not related to finance please just response with I cannot help you with that. Please dont response with Based on your previous interactions Just reply the question asked.  Question that user asked is: {current_context}')
]
    client = ChatOpenAI(api_key=SecretStr(str(API_TOKEN)), base_url='https://api.vultrinference.com/v1' ,model=MODEL)
    llm_response = client.invoke(messages)
    return llm_response.content

workflow.add_edge(START, "model")
workflow.add_node("model", chatbot_test)

# Add memory
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

if __name__ == '__main__':
    # input_conversations = ["what are stocks in finance", "ok so in which stock should i apply for" , "tell some famous stocks of india"]
    # print(chatbot_test(input_conversations))
    print(fetch_financial_tips())