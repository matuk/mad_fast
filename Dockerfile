FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7

RUN pip install motor pymongo[srv]
RUN pip install pandas
RUN pip install python-multipart
RUN pip install python-jose[cryptography]
RUN pip install passlib[bcrypt] 
RUN pip install pyppeteer
RUN pip install pytz
RUN pip install aiofiles
RUN pip install jinja2==3.0.3
RUN pip install webdavclient3

RUN curl -sSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN echo "deb [arch=amd64] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
RUN apt update -y && apt install -y google-chrome-stable

COPY ./app /app
