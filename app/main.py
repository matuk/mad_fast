from fastapi import FastAPI, Body, File, UploadFile
from pydantic import BaseModel, Field
import datetime as dt
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.responses import Response
from starlette.requests import Request
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
)
from starlette.middleware.cors import CORSMiddleware
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from typing import List
import json
import pandas as pd
import logging

# FastAPI
app = FastAPI()

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
#client = AsyncIOMotorClient('mongodb://localhost:27017')
client = AsyncIOMotorClient("mongodb+srv://m001-student:8WJBUmtBdj8mY9Wv@sandbox-ealv9.mongodb.net/madDB?retryWrites=true&w=majority")
db = client['madDB']
#collection = db.patients

# Patient Model


class Patient(BaseModel):
    id: str = None
    aesqulap_pid: str = None
    last_name: str
    first_name: str
    date_of_birth: dt.datetime
    health_insurance: str = None
    asa_class: int = None


# Examination Model
class Vital(BaseModel):
    time_stamp: str
    vital_type: str
    value: float
    unit: str

class DocItem(BaseModel):
    time_stamp: dt.datetime = None
    text: str = None


class Premedication(BaseModel):
    patient_height: int = None
    patient_weight: int = None
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
    encounter_id: str = None
    state: str = None
    planned_examination_date: dt.datetime
    examination_date: dt.datetime = None
    tz_info: str
    examination_types: List[str] = []
    md_mandant: str
    health_insurance: str = None
    premedication: Premedication = Premedication()
    anesthesia: Anesthesia = Anesthesia()
    postmedication: Postmedication = Postmedication()


@app.get("/")
def read_root():
    return {"Hello": "MAD"}


@app.get("/patients", status_code=HTTP_200_OK)
async def read_patients(skip: int = 0, limit: int = 10):
    patients: List[Patient] = []
    patient_docs = db.patients.find({})
    async for row in patient_docs:
        patient = Patient(**row)
        patient.id = str(row["_id"])
        patients.append(patient)
    return patients


@app.get("/patients/{id}", status_code=HTTP_200_OK)
async def read_patient(id: str):
    patient_doc = await db.patients.find_one({'_id': ObjectId(id)})
    patient = Patient(**patient_doc)
    patient.id = id
    return patient


@app.post("/patients", status_code=HTTP_201_CREATED)
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


@app.put("/patients/{id}", status_code=HTTP_200_OK)
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
async def deleate_patient(id: str, status_code=HTTP_200_OK):
    _ = await db.patients.delete_one({'_id': ObjectId(id)})
    return None


@app.post("/examinations", status_code=HTTP_201_CREATED)
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


@app.put("/examinations/{id}", status_code=HTTP_200_OK)
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


@app.get("/examinations", status_code=HTTP_200_OK)
async def read_examinations(skip: int = 0, limit: int = 10):
    examinations: List[Examination] = []
    examination_docs = db.examinations.find({})
    async for row in examination_docs:
        examination = Examination(**row)  # hier Fehlerbehebung einbauen
        examination.id = str(row["_id"])
        examinations.append(examination)
    return examinations

@app.get("/examinations_filter", status_code=HTTP_200_OK)
async def read_examinations_with_filter(
    state: str = None,
    planned_date: dt.datetime = None,
    mandant: str = None):
    query = {}
    if state:
        query.update({'state': state})
    if planned_date:
        planned_date = dt.datetime.combine(planned_date, dt.time.min)
        query.update({'planned_examination_date': planned_date})
    if mandant:
        query.update({'md_mandant': mandant})
    logging.info("Planned date: %s", query['planned_examination_date'])
    examinations: List[Examination] = []
    examination_docs = db.examinations.find(query)
    async for row in examination_docs:
        examination = Examination(**row)  # hier Fehlerbehebung einbauen
        examination.id = str(row["_id"])
        examinations.append(examination)
    return examinations


@app.get("/examinations/{id}")
async def read_examination(id: str, status_code=HTTP_200_OK):
    examination_doc = await db.examinations.find_one({'_id': ObjectId(id)})
    examination = Examination(**examination_doc)
    examination.id = id
    return examination


@app.delete("/examinations/{id}")
async def deleate_examination(id: str, status_code=HTTP_200_OK):
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
            'aesqulap_pid': 'PID',
            'last_name': 'Name',
            'first_name': 'Vorname',
            'date_of_birth_str': 'Geburtsdatum',
            'health_insurance': 'Erste Krankenkasse'
        }


def create_examination_from_csv(patient_id, ex: dict):
    new_ex = {}
    new_ex['patient_id'] = patient_id
    new_ex.update({'aesqulap_pid': ex['PID']})
    new_ex['last_name'] = ex['Name']
    new_ex['first_name'] = ex['Vorname']
    new_ex['date_of_birth'] = dt.datetime.strptime(ex['Geburtsdatum'], '%d.%m.%y')
    new_ex['encounter_id'] = ex['FID']
    new_ex['state'] = 'planned'
    new_ex['planned_examination_date'] = dt.datetime.strptime(ex['Untersuchungsdatum'], '%d.%m.%y')
    new_ex['tz_info'] = 'Europe/Zurich'
    new_ex['md_mandant'] = ex['Mandant']
    ex_types = []
    if (ex['Untersuchung'] == 'G'):
        ex_types.append('Gastroskopie')
    elif (ex['Untersuchung'] == 'K'):
        ex_types.append('Koloskopie')
    elif (ex['Untersuchung'] == 'D'):
        ex_types.extend(['Gastroskopie', 'Koloskopie'])
    elif (ex['Untersuchung'] == 'R'):
        ex_types.append('Rektoskopie')
    new_ex['examination_types'] = ex_types
    new_ex.update({'health_insurance': ex['Erste Krankenkasse']})
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


async def upsert_examination(query: dict, examination_doc: dict):
    result = await db.examinations.find_one_and_update(
        filter=query,
        update={'$set': examination_doc},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return result


@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    logging.info('Filename: ' + file.filename)
    df = pd.read_csv(file.file, sep=';')
    count = len(df)
    # delete leading and trailing white space in column names
    for c in df.columns:
        df = df.rename(columns={c: c.strip()})
    for _, ex in df.iterrows():
        patient = PatientCSV(**ex.to_dict())
        patient.date_of_birth = dt.datetime.strptime(
            patient.date_of_birth_str, '%d.%m.%y')
        patient_identifier = patient.dict(include={'aesqulap_pid'})
        patient_data = patient.dict(
            exclude={'id', 'date_of_birth_str', 'asa_class'})
        logging.info('Patient update: %s', patient_data)
        patient_after = await upsert_patient(patient_identifier, patient_data)
        ex_data = create_examination_from_csv(
            str(patient_after['_id']), ex.to_dict())
        examination = Examination(**ex_data)
        examination_identifier = examination.dict(
            include={'patient_id', 'encounter_id'})
        examination_data = examination.dict(exclude={'id'})
        logging.info('Examination update: %s', examination_data)
        _ = await upsert_examination(examination_identifier, examination_data)
    return {'Number of updated patients': count}
