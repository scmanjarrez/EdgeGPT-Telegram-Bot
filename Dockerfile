FROM python:3.8.10-alpine

COPY . /edgegpt
WORKDIR /edgegpt
RUN apk add --no-cache build-base
RUN pip install --no-cache-dir wheel
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "src/edge.py"]
