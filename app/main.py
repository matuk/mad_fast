from fastapi import FastAPI, Body, File, UploadFile, Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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
        "isAdmin": True
    },
}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    isAdmin: Optional[bool] = None


class UserInDB(User):
    hashed_password: str


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


def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
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
        expire = dt.datetime.utcnow() + dt.timedelta(minutes=15)
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
        logger.info(payload)
        username = payload.get('sub')
        logger.info(username)
        if username is None:
            logger.info("Username is None")
            raise credentials_exception
        token_data = TokenData(username=username)
        logger.info("token_data")
        logger.info(token_data)
    except (JWTError):
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
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


# MongoDB
client = AsyncIOMotorClient('mongodb://localhost:27017')
#client = AsyncIOMotorClient("mongodb+srv://m001-student:veoDg30XNh0owoPa@sandbox-ealv9.mongodb.net/madDB?retryWrites=true&w=majority")
db = client['madDB']
#collection = db.patients

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
    time_stamp: str
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
# @app.post("/token", response_model=Token) #Damit kann ich die response einschränken, damit nur das Token-Objekt zurückgeliefert wird.
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(
        fake_users_db, form_data.username, form_data.password)
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



@app.get("/")
def read_root():
    logger.info("Hello asldkfh")
    return {"Hello": "MAD"}

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
    print("Examination Update vor dem Aufruf von mongodb:")
    print(examination_doc)
    #examination_doc['examination_date'] = dt.datetime.combine(examination_doc['examination_date'], dt.time.min)
    await db.examinations.replace_one({"_id": ObjectId(id)}, examination_doc)
    response.headers.update({"location": str(request.url)})
    examination.id = id
    return examination


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
    logger.info(examination)
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
    ex_types = []
    if (ex['Terminvorgaben'] == 'Gastro'):
        ex_types.append('Gastroskopie')
    elif (ex['Terminvorgaben'] == 'Kolo'):
        ex_types.append('Koloskopie')
    elif (ex['Terminvorgaben'] == 'Doppeldecker'):
        ex_types.extend(['Gastroskopie', 'Koloskopie'])
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
    logger.info('Filename: ' + file.filename)
    data = await file.read()
    logger.info(data)
    logger.info(type(data))
    logger.info(data.decode('iso-8859-1'))
    data_decoded = data.decode('iso-8859-1')
    logger.info(type(data_decoded))
    logger.info("---------")
    # logger.info(BytesIO(bytes(data_decoded, encoding='utf-8'))
    try:
        df = pd.read_csv(
            BytesIO(bytes(data_decoded, encoding='utf-8')), sep=';')
        count = {}
        # delete leading and trailing white space in column names
        for c in df.columns:
            df = df.rename(columns={c: c.strip()})
        for _, ex in df.iterrows():
            if (ex.Terminvorgaben in ['Kolo', 'Gastro', 'Doppeldecker', 'Rekto']):
                logger.info(ex.to_dict()['Untersuchungsdatum'])
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
