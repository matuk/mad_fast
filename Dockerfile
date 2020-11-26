FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7

RUN pip install motor pymongo[srv]
RUN pip install pandas
RUN pip install python-multipart
RUN pip install python-jose[cryptography]
RUN pip install passlib[bcrypt] 
RUN pip install pyppeteer
RUN pip install pytz
RUN pip install aiofiles
RUN pip install jinja2

RUN pyppeteer-install

COPY ./app /app
