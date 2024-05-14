FROM python:3.9-alpine


COPY ./ /ChatGPT-Line-Bot
WORKDIR /ChatGPT-Line-Bot

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python3", "main.py"]