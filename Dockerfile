FROM python:3.9-alpine


COPY ./ /AI-TRAVEL-LINEBOT
WORKDIR /AI-TRAVEL-LINEBOT

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python3", "main.py"]