from fastapi import FastAPI, Body, File, UploadFile, Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import datetime as dt
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.responses import Response
from starlette.requests import Request
from starlette.middleware.cors import CORSMiddleware
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from typing import List, Optional
import json
import pandas as pd
import logging
import time
from io import BytesIO
from jose import JWTError, jwt
from passlib.context import CryptContext
from pyppeteer import launch
import pytz
from os import listdir
from os.path import isfile, join
import glob
import os
from urllib.parse import quote_plus
from webdav3.client import Client

SECRET_KEY = "cd492135aa1dbb8cbc7caa5353be6a37fa4f12ab4a1f6be15f278e2bb419ac98"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


fake_users_db = {
    "user": {
        "username": "user",
        "full_name": "Normal User",
        "hashed_password": "$2b$12$M.OFe2GqlWWX4jVnPaiOne8aRsdB01wHcXTbGxSx4YVhW7Ys/iH5a",
        "disabled": False,
    },
    "admin": {
        "username": "admin",
        "full_name": "Admin User",
        "hashed_password": "$2b$12$hjWq/IPeMOtL3zj1lZL0GOhUUC6lsCuN/BxYxM2B7WMouQkip0jPm",
        "disabled": False,
        "is_admin": True
    },
}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    password: Optional[str] = None
    job_title: Optional[str] = None
    display_in_select: Optional[str] = None
    disabled: Optional[bool] = False
    is_admin: Optional[bool] = False
    in_select_ana: Optional[bool] = False
    in_select_nurse: Optional[bool] = False

class UserIn(User):
    id: Optional[str] = None
    

class UserOut(User):
    id: Optional[str] = None
    

class UserInDB(User):
    hashed_password: str

class UserSelect(BaseModel):
    username: str = Field(None, alias='value')
    display_in_select: Optional[str] = Field(None, alias='text')

    class Config:
        allow_population_by_field_name = True


# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

async def get_user_db(username: str):
    user_db_dict = await db.users.find_one({'username': username})
    user_db = UserInDB(**user_db_dict)
    return user_db


def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

async def authenticate_user_db(username: str, password: str):
    user = await get_user_db(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[dt.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = dt.datetime.utcnow() + expires_delta
    else:
        expire = dt.datetime.utcnow() + dt.timedelta(minutes=240)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Baerer"}
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except (JWTError):
        raise credentials_exception
    #user = get_user(fake_users_db, username=token_data.username)
    user = await get_user_db(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return current_user



# FastAPI
app = FastAPI()
logger = logging.getLogger("gunicorn.error")

# Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Middleware
# Korrektur
# origins = ["http://localhost:8080"]
origins = ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Browser location for pdf generation
browser_path = os.environ.get('BROWSER_PATH')
logger.info(f'Browser path: {browser_path}')

# MongoDB
#client = AsyncIOMotorClient('mongodb://mad-database-service')
#client = AsyncIOMotorClient('mongodb://localhost:27017')
#client = AsyncIOMotorClient("mongodb+srv://m001-student:veoDg30XNh0owoPa@sandbox-ealv9.mongodb.net/madDB?retryWrites=true&w=majority")

db_user = os.environ.get('DB_USER')
db_password = os.environ.get('DB_PASSWORD')
db_protocol = os.environ.get('DB_PROTOCOL')
db_service = os.environ.get('DB_SERVICE')

uri = "%s://%s:%s@%s" % (
    db_protocol, quote_plus(db_user), quote_plus(db_password), db_service)

logger.info(f'MongoDB: {uri}')

client = AsyncIOMotorClient(uri)

db = client['madDB']

# WebDAV
webdav_options = {
 'webdav_hostname': 'http://localhost:7000',
 'webdav_login': os.environ.get('DAV_USER'),
 'webdav_password': os.environ.get('DAV_PASSWORD')
}

webdav_client = Client(webdav_options)
webdav_client.verify = False # To not check SSL certificates (Default = True)

# Models

# Patient Model


class Patient(BaseModel):
    id: str = None
    aesqulap_pid: str = None
    last_name: str
    first_name: str
    date_of_birth: dt.datetime
    health_insurance: str = None
    asa_class: int = None

class MDIntervention(BaseModel):
    id: str = None
    name: str = None


# Examination Model
class Vital(BaseModel):
    time_stamp: dt.datetime = None
    vital_type: str
    value: float
    unit: str

class PatientHeight(BaseModel):
    value: int = None
    unit: str = None

class PatientWeight(BaseModel):
    value: int = None
    unit: str = None

class DocItem(BaseModel):
    time_stamp: dt.datetime = None
    text: str = None

    # class Config:
    #      json_encoders = {
    #          dt.datetime: lambda v: v.replace(tzinfo=pytz.UTC),
    #      }


class Premedication(BaseModel):
    patient_height: PatientHeight = PatientHeight()
    patient_weight: PatientWeight = PatientWeight()
    patient_bmi: float = None
    has_allergies: bool = None
    allergies: List[str] = []
    has_empty_stomach: bool = None
    asa_class: int = None
    medication: List[str] = []
    cardio_diseases: List[str] = []
    respiratory_diseases: List[str] = []
    visceral_diseases: List[str] = []
    neuro_diseases: List[str] = []
    comment: str = None


class Anesthesia(BaseModel):
    md_name: str = None
    nurse_name: str = None
    start_anesthesia_ts: dt.datetime = None
    stop_anesthesia_ts: dt.datetime = None
    anesthesia_duration: str = None
    start_intervention_ts: dt.datetime = None
    stop_intervention_ts: dt.datetime = None
    intervention_duration: str = None
    comment: str = None
    vitals: List[Vital] = []
    doc_items: List[DocItem] = []


class Postmedication(BaseModel):
    drink: bool = None
    accompanied: bool = None
    walking: bool = None
    informed: bool = None
    contact_info: bool = None
    service_recording: str = None
    special_med: List[str] = []


class Examination(BaseModel):
    id: str = None
    patient_id: str
    aesqulap_pid: str
    last_name: str
    first_name: str
    date_of_birth: dt.datetime
    state: str = None
    planned_examination_date: dt.datetime
    examination_date: dt.datetime = None
    tz_info: str
    examination_types: List[str] = []
    md_intervention: str
    health_insurance: str = None
    premedication: Premedication = Premedication()
    anesthesia: Anesthesia = Anesthesia()
    postmedication: Postmedication = Postmedication()
    



    



# Routes

@app.get("/")
def read_root():
    return {"Hello": "MAD"}

# @app.post("/token", response_model=Token) #Damit kann ich die response einschränken, damit nur das Token-Objekt zurückgeliefert wird.
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    #user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    user = await authenticate_user_db(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User is disabled", headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = dt.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token( data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer", "user": user}


@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.get("/users/me/items/")
async def read_own_items(current_user: User = Security(get_current_active_user, scopes=['items'])):
    return [{"item_id": "Foo", "owner": current_user.username}]

@app.get("/users", status_code=status.HTTP_200_OK, response_model=List[UserOut])
async def get_users():
    users: List[UserOut] = []
    users_list = db.users.find({})
    async for row in users_list:
        user = UserOut(**row)
        user.id = str(row["_id"])
        users.append(user)
    return users

@app.get("/users/{id}")
async def get_user_from_db(id: str, status_code=status.HTTP_200_OK, response_model=UserOut):
    try:
        object_id = ObjectId(id)
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object ID not valid")
    user_db_dict = await db.users.find_one({'_id': object_id})
    try:
        user_out = UserOut(**user_db_dict)
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
    user_out.id = id
    return user_out

@app.get("/users/byname/{username}")
async def get_user_byname(username: str, status_code=status.HTTP_200_OK, response_model=UserOut):
    user_db_dict = await db.users.find_one({'username': username})
    try:
        user_out = UserOut(**user_db_dict)
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
    user_out.id = str(user_db_dict['_id'])
    return user_out

@app.get("/users/isunique/{username}")
async def check_username_unique(username: str, status_code=status.HTTP_200_OK):
    user_db_dict = await db.users.find_one({'username': username})
    return (user_db_dict == None)

@app.get("/users/notme/{username}")
async def check_username_isnotme(username: str, status_code=status.HTTP_200_OK):
    logger.info(username)
    return (username != "matuk")
    

async def upsert_user(query: dict, user_doc: dict):
    result = await db.users.find_one_and_update(
        filter=query,
        update={'$set': user_doc},
        upsert=True,
        return_document=ReturnDocument.AFTER)
    return result

@app.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def create_user(user_in: UserIn, response: Response, request: Request):
    user_in_dict = user_in.dict()
    _ = user_in_dict.pop('id', None)
    #user_doc['hashed_password'] = get_password_hash(user_in.password)
    user_db = UserInDB(**user_in_dict, hashed_password = get_password_hash(user_in.password))
    user_identifier = user_in.dict(include={'username'})
    user_updated = await upsert_user(user_identifier, user_db.dict())
    user_updated['id'] = str(user_updated['_id'])
    response.headers.update({"location": str(request.url) + str(user_updated['_id'])})
    return user_updated

@app.post("/useradmin", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def create_admin(response: Response, request: Request):
    user_dict = {'username': 'admin', 'password': 'admin', 'is_admin': True}
    user_db = UserInDB(**user_dict, hashed_password = get_password_hash(user_dict['password']))
    user_identifier = {'username': 'admin'}
    user_updated = await upsert_user(user_identifier, user_db.dict())
    user_updated['id'] = str(user_updated['_id'])
    response.headers.update({"location": str(request.url) + str(user_updated['_id'])})
    return user_updated

@app.put("/users/{id}", status_code=status.HTTP_200_OK, response_model=UserOut  )
async def update_user(id: str, user_in: UserIn, response: Response, request: Request):
    user_in_dict = user_in.dict()
    _ = user_in_dict.pop('id', None)
    user_db = UserInDB(**user_in_dict, hashed_password = get_password_hash(user_in.password)) 
    user_identifier = user_in.dict(include={'username'})
    user_updated = await upsert_user(user_identifier, user_db.dict())
    user_updated['id'] = str(user_updated['_id'])
    response.headers.update({"location": str(request.url) + str(user_updated['_id'])})
    return user_updated


@app.delete("/users/{id}")
async def deleate_user(id: str, status_code=status.HTTP_200_OK):
    _ = await db.users.delete_one({'_id': ObjectId(id)})
    return None


@app.get("/optionsnurse", status_code=status.HTTP_200_OK, response_model=List[UserSelect])
async def get_users_select_nurse():
    users: List[UserSelect] = []
    users_list = db.users.find({'job_title': 'nurse'})
    async for row in users_list:
        user = UserSelect(**row)
        if user.display_in_select:
            users.append(user)
    return users

@app.get("/optionsana", status_code=status.HTTP_200_OK, response_model=List[UserSelect])
async def get_users_select_ana():
    users: List[UserSelect] = []
    users_list = db.users.find({'job_title': 'md'})
    async for row in users_list:
        user = UserSelect(**row)
        if user.display_in_select:
            users.append(user)
    return users


def get_mad_report_filename(examination):
    file_name = "Anaesthesieprotokoll_"
    file_name = file_name.strip() + examination.examination_date.strftime('%Y%m%d_%H%M')
    file_name = file_name.strip() + '_' + examination.aesqulap_pid.strip() + '_' + examination.last_name.strip() + '_' + examination.first_name.strip() + '_' + examination.date_of_birth.strftime("%d-%m-%Y") + '.pdf'
    return file_name

# def get_template(template_name: str):
#     root = os.path.dirname(os.path.abspath(__file__))
#     templates_dir = os.path.join(root, 'templates')
#     env = Environment( loader=FileSystemLoader(templates_dir) )
#     return env.get_template(template_name)

@app.get("/examination_report/{id}")
async def generate_examination_report(request: Request, id: str):
    try:
        object_id = ObjectId(id)
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object ID not valid")
    examination_doc = await db.examinations.find_one({'_id': object_id})
    utc_tz = pytz.timezone('UTC')
    local_tz = pytz.timezone(examination_doc['tz_info'])
    items = [ {'time_stamp': utc_tz.localize(item['time_stamp']).astimezone(local_tz), 'text': item['text']} for item in examination_doc['anesthesia']['doc_items'] ]
    examination_doc['anesthesia']['doc_items'] = items
    examination = Examination(**examination_doc)
    examination.id = id
    return templates.TemplateResponse("index.html", {"request": request, "examination": examination})
    
    
    
    
@app.put("/examinations/generate_pdf/{id}")
async def generate_pdf_api(request: Request, id: str):
    try:
        object_id = ObjectId(id)
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object ID not valid")
    examination_doc = await db.examinations.find_one({'_id': object_id})
    examination = Examination(**examination_doc)
    examination.id = id
    _ = await generate_pdf_report(examination)
    return "Success"
 
async def generate_pdf_report(examination):
    if browser_path == None: # Local dev environment on mac
        url = 'http://127.0.0.1:8000/examination_report/' + examination.id
        browser = await launch()
    else: # all docker environments with env variable BROWSER_PATH
        url = 'http://127.0.0.1/examination_report/' + examination.id
        browser = await launch(executablePath=browser_path, headless=True, args=['--no-sandbox'])
    page = await browser.newPage()
    logger.info('MK: Browser bereit, jetzt url aufrufen')
    await page.goto(url, {'waitUntil': 'networkidle0'})
    logger.info('MK: Seite aufgerufen')
    file_name = get_mad_report_filename(examination)
    file_path = "../pdf_archive/" + file_name
    await page.pdf({'format': 'A4', 'path': file_path})
    logger.info('MK: Seiter gespeichert unter:')
    logger.info(file_path)
    await browser.close()
    #webdav
    # dir_name = examination.examination_date.strftime('%Y%m%d')
    # webdav_client.mkdir(f"/{dir_name}")
    # webdav_client.upload_sync(remote_path=f"/{dir_name}/{file_name}", local_path=f"{file_path}")
    return url




@app.get("/mdintervention")
async def read_mds_intervention():
    mds: List[MDIntervention] = []
    mds_docs = db.mdintervention.find({})
    async for row in mds_docs:
        mds.append(row['name'])
    return mds



@app.get("/patients", status_code=status.HTTP_200_OK)
async def read_patients(skip: int = 0, limit: int = 10):
    patients: List[Patient] = []
    patient_docs = db.patients.find({})
    async for row in patient_docs:
        patient = Patient(**row)
        patient.id = str(row["_id"])
        patients.append(patient)
    return patients


@app.get("/patients/{id}", status_code=status.HTTP_200_OK)
async def read_patient(id: str):
    patient_doc = await db.patients.find_one({'_id': ObjectId(id)})
    patient = Patient(**patient_doc)
    patient.id = id
    return patient


@app.post("/patients", status_code=status.HTTP_201_CREATED)
async def create_patient(patient: Patient, response: Response, request: Request):
    patient_doc = patient.dict()
    _ = patient_doc.pop('id', None)
    patient_doc['date_of_birth'] = dt.datetime.combine(
        patient_doc['date_of_birth'], dt.time.min)
    result = await db.patients.insert_one(patient_doc)
    patient.id = str(result.inserted_id)
    response.headers.update(
        {"location": str(request.url) + str(result.inserted_id)})
    return patient


@app.put("/patients/{id}", status_code=status.HTTP_200_OK)
async def update_patient(id: str, patient: Patient, response: Response, request: Request):
    patient_doc = patient.dict()
    _ = patient_doc.pop('id', None)
    # date to datetime conversion, because pymongo does not support date
    patient_doc['date_of_birth'] = dt.datetime.combine(
        patient_doc['date_of_birth'], dt.time.min)
    await db.patients.replace_one({"_id": ObjectId(id)}, patient_doc)
    response.headers.update({"location": str(request.url)})
    patient.id = id
    return patient


@app.delete("/patients/{id}")
async def deleate_patient(id: str, status_code=status.HTTP_200_OK):
    _ = await db.patients.delete_one({'_id': ObjectId(id)})
    return None


@app.post("/examinations", status_code=status.HTTP_201_CREATED)
async def create_examination(examination: Examination, response: Response, request: Request):
    examination_doc = examination.dict()
    _ = examination_doc.pop('id', None)
    print("Examination Doc vor dem Aufruf von mongodb:")
    print(examination_doc)
    #examination_doc['examination_date'] = dt.datetime.combine(examination_doc['examination_date'], dt.time.min)
    result = await db.examinations.insert_one(examination_doc)
    examination.id = str(result.inserted_id)
    # astimezone(pytz.timezone("Europe/Zurich")) --- damit kann man UTC nach Local konvertieren
    response.headers.update(
        {"location": str(request.url) + str(result.inserted_id)})
    print("Examination Doc nach dem Aufruf von mongodb:")
    print(examination)
    return examination


@app.put("/examinations/{id}", status_code=status.HTTP_200_OK)
async def update_examination(id: str, examination: Examination, response: Response, request: Request):
    examination_doc = examination.dict()
    _ = examination_doc.pop('id', None)
    #examination_doc['examination_date'] = dt.datetime.combine(examination_doc['examination_date'], dt.time.min)
    await db.examinations.replace_one({"_id": ObjectId(id)}, examination_doc)
    response.headers.update({"location": str(request.url)})
    examination.id = id
    examination.examination_date = examination.examination_date.replace(tzinfo=pytz.UTC)
    for item in examination.anesthesia.doc_items:
        item.time_stamp = item.time_stamp.replace(tzinfo=pytz.UTC)
    return examination

@app.put("/examinations/{id}/start", status_code=status.HTTP_200_OK)
async def start_examination(id: str, response: Response, request: Request):
    message = {}
    # read examination from MongoDB
    try:
        object_id = ObjectId(id)
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object ID not valid")
    examination_doc = await db.examinations.find_one({'_id': object_id})
    examination = Examination(**examination_doc)
    examination.id = id
    # set default values for newly started examination
    if examination.state == "planned":
        examination.state = "started"
        examination.examination_date = dt.datetime.now(dt.timezone.utc)  # Jetzt inkl. Zeit
        #examination.patient_age = int((dt.datetime.combine(dt.datetime.now(), dt.time.min) - examination.date_of_birth).days // 365.2425)
        examination.postmedication.drink = True
        examination.postmedication.accompanied = True
        examination.postmedication.walking = True
        examination.postmedication.informed = True
        examination.postmedication.contact_info = True
        # try to find the last completed examination for same patient
        last_examination = None
        last_examination_cursor = db.examinations.find({
                'aesqulap_pid': examination_doc['aesqulap_pid'],
                'state': 'completed'
                }).sort([('examination_date', -1)]).limit(1)
        async for doc in last_examination_cursor:
            last_examination = Examination(**doc)
        if last_examination:
            logger.info(last_examination)
            # Hier alle Informationen kopieren
            examination.premedication.patient_height = last_examination.premedication.patient_height
            examination.premedication.patient_weight = last_examination.premedication.patient_weight
            examination.premedication.has_allergies = last_examination.premedication.has_allergies
            examination.premedication.allergies = last_examination.premedication.allergies
            examination.premedication.asa_class = last_examination.premedication.asa_class
            examination.premedication.medication = last_examination.premedication.medication
            examination.premedication.cardio_diseases = last_examination.premedication.cardio_diseases
            examination.premedication.respiratory_diseases = last_examination.premedication.respiratory_diseases
            examination.premedication.visceral_diseases = last_examination.premedication.visceral_diseases
            examination.premedication.neuro_diseases = last_examination.premedication.neuro_diseases
            examination.premedication.comment = last_examination.premedication.comment
            message['code'] = 'premed_copied'
            date_loc = pytz.utc.localize(last_examination.examination_date).astimezone(pytz.timezone(last_examination.tz_info))
            message['text'] = f"Prämedikationsdaten kopiert von der Untersuchung vom {date_loc.strftime('%d.%m.%Y %H:%M')} für {examination.first_name} {examination.last_name}."
        else:
            logger.info('MKLog: Keine bestehende Examination gefunden.')
            message['code'] = 'premed_not_copied'
            message['text'] = ''
        # Update of examination in MongoDB
        updated_examination_doc = examination.dict()
        await db.examinations.replace_one({"_id": ObjectId(id)}, updated_examination_doc)
    
    if examination.examination_date is not None: 
        examination.examination_date = examination.examination_date.replace(tzinfo=pytz.UTC)
    response.headers.update({"location": str(request.url)})
   
    return { 'examination': examination, 'message': message }


@app.get("/examinations", status_code=status.HTTP_200_OK)
async def read_examinations(skip: int = 0, limit: int = 10):
    examinations: List[Examination] = []
    examination_docs = db.examinations.find({})
    async for row in examination_docs:
        examination = Examination(**row)  # hier Fehlerbehebung einbauen
        examination.id = str(row["_id"])
        examinations.append(examination)
    return examinations


@app.get("/examinations_filter", status_code=status.HTTP_200_OK)
async def read_examinations_with_filter(
        state: str = None,
        planned_date: dt.datetime = None,
        mandant: str = None):
    query = {}
    if state:
        query.update({'state': state})
    else:
        query.update({'state': {'$in': ['planned', 'started']}})
    if planned_date:
        planned_date = dt.datetime.combine(planned_date, dt.time.min)
        query.update({'planned_examination_date': planned_date})
    if mandant:
        query.update({'md_mandant': mandant})
    logger.info("Planned date: %s", query['planned_examination_date'])
    examinations: List[Examination] = []
    examination_docs = db.examinations.find(query)
    async for row in examination_docs:
        try:
            examination = Examination(**row)  
            examination.id = str(row["_id"])
            examinations.append(examination)
        except:
            logger.warning(f"Examination for patient {row.get('aesqulap_pid')} cannot be validated.")
    return examinations

@app.get("/planned_examinations", status_code=status.HTTP_200_OK)
async def read_planned_examinations(planned_date: str = None):
    query = {}
    query.update({'state': 'planned'})
    if planned_date:
        try:
            planned_date_dt = dt.datetime.strptime(planned_date, '%Y-%m-%d')
        except:
            planned_date_dt = dt.datetime.combine(dt.datetime.now(), dt.time.min) # today as default
    else:
        planned_date_dt = dt.datetime.combine(dt.datetime.now(), dt.time.min) # today as default
    query.update({'planned_examination_date': planned_date_dt})
    examinations: List[Examination] = []
    examination_docs = db.examinations.find(query)
    async for row in examination_docs:
        try:
            examination = Examination(**row)  
            examination.id = str(row["_id"])
            examinations.append(examination)
        except:
            logger.warning(f"Examination for patient {row.get('aesqulap_pid')} cannot be validated.")
    return examinations

@app.get("/examinations/{id}")
async def read_examination(id: str, status_code=status.HTTP_200_OK):
    try:
        object_id = ObjectId(id)
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object ID not valid")
    examination_doc = await db.examinations.find_one({'_id': object_id})
    examination = Examination(**examination_doc)
    examination.id = id
    if examination.examination_date is not None: 
        examination.examination_date = examination.examination_date.replace(tzinfo=pytz.UTC)
    for item in examination.anesthesia.doc_items:
        item.time_stamp = item.time_stamp.replace(tzinfo=pytz.UTC)
    return examination


@app.delete("/examinations/{id}")
async def deleate_examination(id: str, status_code=status.HTTP_200_OK):
    _ = await db.examinations.delete_one({'_id': ObjectId(id)})
    return None


# Combined
@app.get("/patients/{pid}/examinations")
async def read_examinations_for_patient(pid: str, skip: int = 0, limit: int = 10):
    examinations: List[Examination] = []
    examination_docs = db.examinations.find({'patient_id': pid})
    async for row in examination_docs:
        examination = Examination(**row)  # hier Fehlerbehebung einbauen
        examination.id = str(row["_id"])
        examinations.append(examination)
    return examinations

# Upload of CSV-File with planned examinations

# Patient Model


class PatientCSV(BaseModel):
    id: str = None
    aesqulap_pid: str
    last_name: str
    first_name: str
    date_of_birth_str: str
    date_of_birth: dt.date = None
    health_insurance: str = None
    asa_class: int = None

    class Config():
        fields = {
            'aesqulap_pid': 'Patientennummer',
            'last_name': 'Name',
            'first_name': 'Vorname',
            'date_of_birth_str': 'Geb_Datum',
            'health_insurance': 'Krankenkasse'
        }


def create_examination_from_csv(patient_id, ex: dict):
    new_ex = {}
    new_ex['patient_id'] = patient_id
    new_ex.update({'aesqulap_pid': ex['Patientennummer']})
    new_ex['last_name'] = ex['Name']
    new_ex['first_name'] = ex['Vorname']
    new_ex['date_of_birth'] = dt.datetime.strptime(ex['Geb_Datum'], '%d.%m.%Y')
    #new_ex['encounter_id'] = ex['FID']
    new_ex['state'] = 'planned'
    new_ex['planned_examination_date'] = dt.datetime.strptime(
        ex['Untersuchungsdatum'], '%d.%m.%Y')
    new_ex['tz_info'] = 'Europe/Zurich'
    new_ex['md_intervention'] = ex['Mandant']
    # new_ex['postmedication']['drink'] = True
    # new_ex['postmedication']['accompanied'] = True
    # new_ex['postmedication']['walking'] = True
    # new_ex['postmedication']['informed'] = True
    # new_ex['postmedication']['contact_info'] = True
    ex_types = []
    if (ex['Terminvorgaben'] == 'Gastro'):
        ex_types.append('Gastroskopie')
    elif (ex['Terminvorgaben'] == 'Kolo'):
        ex_types.append('Kolonoskopie')
    elif (ex['Terminvorgaben'] == 'Doppeldecker'):
        ex_types.extend(['Gastroskopie', 'Kolonoskopie'])
    elif (ex['Terminvorgaben'] == 'Rekto'):
        ex_types.append('Rektoskopie')
    new_ex['examination_types'] = ex_types
    new_ex.update({'health_insurance': ex['Krankenkasse']})
    return new_ex


async def find_one_patient_by_aesqulap_pid(aesqulap_pid: str):
    patient_doc = await db.patients.find_one({'aesqulap_id': aesqulap_pid})
    return patient_doc


async def upsert_patient(query: dict, patient_doc: dict):
    result = await db.patients.find_one_and_update(
        filter=query,
        update={'$set': patient_doc},
        upsert=True,
        return_document=ReturnDocument.AFTER)
    return result

async def upsert_md_intervention(query: dict, md_intervention_doc: dict):
    result = await db.mdintervention.find_one_and_update(
        filter=query,
        update={'$set': md_intervention_doc},
        upsert=True,
        return_document=ReturnDocument.AFTER)
    return result

async def upsert_examination(query: dict, examination_doc: dict):
    result = await db.examinations.find_one_and_update(
        filter=query,
        update={'$set': examination_doc},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return result


def get_date_frequency_from_count(count):
    sorted_count_dict = dict(sorted(count.items()))
    total_count = sum(sorted_count_dict.values())
    return ([{'date': key.strftime('%d.%m.%Y'), 'count': value} for key, value in sorted_count_dict.items()], total_count)


@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    data = await file.read()
    data_decoded = data.decode('iso-8859-1')
    try:
        df = pd.read_csv(
            BytesIO(bytes(data_decoded, encoding='utf-8')), sep=';')
        count = {}
        # delete leading and trailing white space in column names
        for c in df.columns:
            df = df.rename(columns={c: c.strip()})
        for _, ex in df.iterrows():
            if (ex.Terminvorgaben in ['Kolo', 'Gastro', 'Doppeldecker', 'Rekto']):
                patient = PatientCSV(**ex.to_dict())
                patient.date_of_birth = dt.datetime.strptime(
                    patient.date_of_birth_str, '%d.%m.%Y')
                patient_identifier = patient.dict(include={'aesqulap_pid'})
                patient_data = patient.dict(
                    exclude={'id', 'date_of_birth_str', 'asa_class'})
                logger.info('Patient update: %s', patient_data)
                patient_after = await upsert_patient(patient_identifier, patient_data)
                res = await upsert_md_intervention({'name': ex.Mandant}, {'name': ex.Mandant})
                logger.info('MKLog: Update der MDs')
                logger.info(res)
                ex_data = create_examination_from_csv(
                    str(patient_after['_id']), ex.to_dict())
                examination = Examination(**ex_data)
                examination_identifier = examination.dict(
                    include={'patient_id', 'planned_examination_date'})
                examination_data = examination.dict(exclude={'id'})
                logger.info('Examination update: %s', examination_data)
                _ = await upsert_examination(examination_identifier, examination_data)
                count.setdefault(
                    examination_data['planned_examination_date'], 0)
                count[examination_data['planned_examination_date']] += 1
        date_frequency, total_count = get_date_frequency_from_count(count)
        return {'Planned examinations': date_frequency, 'Total count': total_count}
    except:
        raise HTTPException(
            status_code=422, detail="csv file cannot be imported")

@app.post("/upload_users")
async def upload_users(file: UploadFile = File(...)):
    data = await file.read()
    data_decoded = data.decode('iso-8859-1')
    try:
        df = pd.read_csv(
            BytesIO(bytes(data_decoded, encoding='utf-8')), sep=',')
        # delete leading and trailing white space in column names
        for c in df.columns:
            df = df.rename(columns={c: c.strip()})
        for _, user_dict in df.iterrows():
            user_db = UserInDB(**user_dict, hashed_password = get_password_hash(user_dict['password']))
            user_identifier = {'username': user_dict['username']}
            _ = await upsert_user(user_identifier, user_db.dict())
        return 'Users created'
    except:
        raise HTTPException(
            status_code=422, detail="csv file cannot be imported")


class MKDateTest(BaseModel):
    id: str = None
    ts: dt.datetime
    comment: str = None

    class Config:
        json_encoders = {
            dt.datetime: lambda v: v.isoformat()[:-3]+'Z'
        }

@app.post("/datetest")
async def set_date(mk_datetest: MKDateTest, response: Response, request: Request):
    logger.info('Test Date: %s', mk_datetest)
    datetest = mk_datetest.dict()
    logger.info('Test Date: %s', datetest)
    result = await db.datetest.replace_one({"id": mk_datetest.id}, datetest, upsert=True)
    # astimezone(pytz.timezone("Europe/Zurich")) --- damit kann man UTC nach Local konvertieren
    response.headers.update({"location": str(request.url) + str(result.upserted_id)})
    logger.info('Result: %s', result)
    logger.info('Raw_Result: %s', result.raw_result)
    result = await db.datetest.find_one({"id": mk_datetest.id})
    datetest_check = MKDateTest(**result)
    logger.info('datatest check: %s', datetest_check)
    return datetest_check

@app.get("/datetest/{id}")
async def get_date(response: Response, request: Request, id: str):
    logger.info('ID: %s', id)
    result = await db.datetest.find_one({"id": id})
    datetest = MKDateTest(**result)
    # astimezone(pytz.timezone("Europe/Zurich")) --- damit kann man UTC nach Local konvertieren
    logger.info('Result: %s', result)
    logger.info('MKDateTest: %s', datetest)
    # logger.info(datetest.ts.isoformat()[:-3]+'Z')
    # datetest.ts = datetest.ts.isoformat()[:-3]+'Z'
    return datetest


@app.post("/datesimulation")
async def set_dates(response: Response, request: Request):
    d1 = {
        'id': '101',
        'ts': dt.datetime.utcnow(),
        'comment': 'utcnow'
    }
    _ = await db.datetest.replace_one({"id": d1['id']}, d1, upsert=True)
    d2 = {
        'id': '102',
        'ts': dt.datetime.now(),
        'comment': 'now()'
    }
    _ = await db.datetest.replace_one({"id": d2['id']}, d2, upsert=True)
    # astimezone(pytz.timezone("Europe/Zurich")) --- damit kann man UTC nach Local konvertieren
    zurich = pytz.timezone('Europe/Zurich')
    aware_datetime = zurich.localize(dt.datetime.now())
    d3 = {
        'id': '103',
        'ts': aware_datetime,
        'comment': 'tz aware zurich / now()'
    }
    _ = await db.datetest.replace_one({"id": d3['id']}, d3, upsert=True)
    aware_datetime = zurich.localize(dt.datetime.utcnow())
    d4 = {
        'id': '104',
        'ts': aware_datetime,
        'comment': 'tz aware zurich / utcnow()'
    }
    _ = await db.datetest.replace_one({"id": d4['id']}, d4, upsert=True)

    return "success"

@app.get("/sleep", status_code=status.HTTP_200_OK)
def sleep(delta: int, response: Response, request: Request):
    time.sleep(delta)
    t1 = dt.datetime.now(dt.timezone.utc)
    return {'delta': delta, 'message': {'code': 'code1', 'text': f'{delta} Sekunden geschlafen'}, 'utc_time': t1}


#app.mount("/archive", StaticFiles(directory="archive"), name="archive")

# @app.get("/archive_old")
# async def archive_old():
#     path = './archive/'
#     files = [f for f in listdir(path) if isfile(join(path, f))]
#     logger.info(files)
#     return files

@app.get("/get_archived_reports")
async def get_archived_reports():
    pattern = '../pdf_archive/*.pdf'
    files = glob.glob(pattern)
    #files = [os.path.basename(x) for x in glob.glob(pattern)]
    logger.info(files)
    files_list = [{'filename': os.path.basename(file)} for file in files]
    logger.info(files_list)
    return files_list

@app.get("/get_archived_report/{filename}")
async def get_archived_report(filename: str):
    logger.info(filename)
    filepath = os.path.join('../pdf_archive/', filename)
    logger.info(filepath)
    return FileResponse(filepath)

@app.get("/testfile")
async def testfile():
    return FileResponse('../pdf_archive/test_file.txt')