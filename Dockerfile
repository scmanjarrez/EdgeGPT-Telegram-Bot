FROM python:3.8.16-alpine

COPY . /edgebot
WORKDIR /edgebot
RUN pip install -r requirements.txt
CMD ["python", "edge.py"]
