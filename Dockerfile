FROM python:3.11

WORKDIR /GoogleChatHTMX

COPY chats .
COPY static .
COPY templates .
COPY .env .
COPY GoogleGPT.py .
COPY requirements.txt .

RUN pip install -r requirements.txt
