from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
import glob
from fastapi import FastAPI, HTTPException, UploadFile, File
import uvicorn
from pydantic import BaseModel
from uuid import uuid4
from fastapi.staticfiles import StaticFiles


from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import json

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class Chat(BaseModel):
    name: str = "Untitled chat"
    id: str
    messages: list = []
    
def getGeminiResponse(request: str) -> str:
    llm = ChatGoogleGenerativeAI(model="gemini-pro")
    result = llm.invoke(request)
    return result.content

def getConversationTitle(request: list) -> str:
    llm = ChatGoogleGenerativeAI(model="gemini-pro")
    result = llm.invoke(f"""You are a conversation title generator, respond only with a simple title.
                            Please create a title for this conversation:
                            {str(request)}
                        """)
    return result.content

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    context = {"request": request}
    return templates.TemplateResponse("index.html", context)

@app.get("/conversations", response_class=HTMLResponse)
async def load_previous_conversation():
    buttons_html = ""
    for chat_file_path in glob.glob("./chats/*.json"):
        with open(chat_file_path, "r+") as chat_file:
            chat = json.load(chat_file)
        button_html = f'<button hx-get="/load_chat/{chat["id"]}" class="chat-{chat["id"]}" hx-target="main">{chat["name"]}</button>'
        buttons_html += button_html + "\n"
    
    return buttons_html

@app.post("/new_chat")
async def create_chat():
    if not os.path.exists("chats"):
        os.makedirs("chats")

    chat_id = str(uuid4())
    chat = Chat(id=chat_id)

    with open(f"chats/{chat_id}.json", "w") as chat_file:
        json.dump(chat.model_dump(), chat_file)

    button_html = f'<button hx-get="/load_chat/{chat_id}" hx-target="main" hx-trigger="click, load" class="chat-{chat_id}">{chat.name}</button>'
    return HTMLResponse(content=button_html)

@app.get("/load_chat/{chat_id}")
async def load_chat(chat_id: str):
    chat_file_path = f"chats/{chat_id}.json"
    if os.path.exists(chat_file_path):
        with open(chat_file_path, "r") as chat_file:
            chat = json.load(chat_file)
    else:
        raise HTTPException(status_code=404, detail="Chat not found")

    div_message = "<div class=\"messages\">"

    for message in chat['messages']:
        role = message['role']
        content = message['content']
        div_message += f'<div class="{role} message">{content}</div>' 

    div_message += '</div>'

    div_message += \
    f""" 
    <form id="messageform" hx-post="/send_message" hx-target=".messages" hx-swap="beforeend">
        <input type="hidden" name="chat_id" value="{chat_id}" />
        <input type="text" name="message" />
        <button>Send</button>
    </form> 
    """
    
    return HTMLResponse(content=div_message)

@app.post("/send_message/", response_class=HTMLResponse)
async def send_message(chat_id: str = Form(...), message: str = Form(...)):
    chat_file_path = f"chats/{chat_id}.json"
    if os.path.exists(chat_file_path):
        with open(chat_file_path, "r+") as chat_file:
            chat = json.load(chat_file)
            chat["messages"].append({"role": "user", "content": message})
            chat_file.seek(0)
            json.dump(chat, chat_file)
            chat_file.truncate()
    else:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    message = [message for message in chat["messages"] if message["role"] == "user"][-1]["content"]
    message_html = f'<div class="user message" hx-trigger="load" hx-get="/get_response/{chat_id}" hx-target=".messages" hx-swap="beforeend">{message}</div>'
    return HTMLResponse(content=message_html)

@app.get("/create_title/{chat_id}")
async def create_title(chat_id: str, request: Request):
    chat_file_path = f"chats/{chat_id}.json"
    if os.path.exists(chat_file_path):
        with open(chat_file_path, "r") as chat_file:
            chat = json.load(chat_file)

        title = getConversationTitle(chat["messages"])
        
        if chat["name"] == "Untitled chat" or not chat["name"]:
            chat["name"] = title
        with open(chat_file_path, "w") as chat_file:
            json.dump(chat, chat_file)
    else:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    return title

@app.get("/get_response/{chat_id}", response_class=HTMLResponse)
async def get_response(chat_id: str):
    chat_file_path = f"chats/{chat_id}.json"
    if os.path.exists(chat_file_path):
        with open(chat_file_path, "r") as chat_file:
            chat = json.load(chat_file)

    else:
        raise HTTPException(status_code=404, detail="Chat not found")

    with open(chat_file_path, "r+") as chat_file:
        chat = json.load(chat_file)
        message = [message for message in chat["messages"] if message["role"] == "user"][-1]["content"] if chat["messages"] else None

        response = getGeminiResponse(message)

        chat["messages"].append({"role": "assistant", "content": response})
        chat_file.seek(0)
        json.dump(chat, chat_file)
        chat_file.truncate()

    create_title = ""
    if not chat["name"] or chat["name"] == "Untitled chat":
        create_title = f'hx-trigger="load" hx-get="/create_title/{chat_id}" hx-target=".chat-{chat_id}"'

    # message_html = f'<div class="assistant message" hx-get="/create_title/{chat_id}" hx-target=".chat-{chat_id}">{response}</div>'

    message_html = f'<div class="assistant message" {create_title}>{response}</div>'
    
    return HTMLResponse(message_html)

if __name__ == "__main__":
    uvicorn.run("GoogleGPT:app", host="127.0.0.1", port=8000, reload=True)