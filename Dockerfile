FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7

RUN pip install motor pymongo[srv]

COPY ./app /app
