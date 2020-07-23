FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7

RUN pip install motor pymongo[srv]
RUN pip install pandas
RUN pip install python-multipart

COPY ./app /app
