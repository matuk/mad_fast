import logging
from fastapi import FastAPI, Body
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
from typing import List
import json

# FastAPI
app = FastAPI()

# Middleware
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
collection = db.patients

### Patient Model
class Patient(BaseModel):
    id: str = None
    aesqulap_id: str = None
    last_name: str
    first_name: str
    date_of_birth: dt.date
    health_insurance: str = None
    asa_class: int = None


### Examination Model
class Vital(BaseModel):
    time_stamp: str
    vital_type: str
    value: float
    unit: str

class Premedication(BaseModel):
    encounter_id: str = None
    examination_types: List[str] = []
    md_name: str = None
    health_insurance: str = None
    patient_weight: int = None
    patient_height: int = None
    has_allergies: bool = None
    allergies: List[str] = []
    has_empty_stomach: bool = None
    asa_class: int = None
    medication: List[str] = []
    cardio_diseases: List[str] = []
    respiratory_diseases: List[str] = []
    visceral_diseases: List[str] = []
    neuro_diseases: List[str] = []

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
    examination_date: dt.datetime
    tz_info: str
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


@app.get("/patients/{id}")
async def read_patient(id: str, status_code=HTTP_200_OK):
    patient_doc = await db.patients.find_one({'_id': ObjectId(id)})
    patient = Patient(**patient_doc)
    patient.id = id
    return patient

@app.post("/patients", status_code=HTTP_201_CREATED)
async def create_patient(patient: Patient, response: Response, request: Request):
    patient_doc = patient.dict()
    _ = patient_doc.pop('id', None)
    patient_doc['date_of_birth'] = dt.datetime.combine(patient_doc['date_of_birth'], dt.time.min)
    result = await db.patients.insert_one(patient_doc)
    patient.id = str(result.inserted_id)
    response.headers.update({"location": str(request.url) + str(result.inserted_id) })
    return patient

@app.put("/patients/{id}", status_code=HTTP_200_OK)
async def update_patient(id: str, patient: Patient, response: Response, request: Request):
    patient_doc = patient.dict()
    _ = patient_doc.pop('id', None)
    patient_doc['date_of_birth'] = dt.datetime.combine(patient_doc['date_of_birth'], dt.time.min)  # date to datetime conversion, because pymongo does not support date
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
    #astimezone(pytz.timezone("Europe/Zurich")) --- damit kann man UTC nach Local konvertieren
    response.headers.update({"location": str(request.url) + str(result.inserted_id) })
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
    

## Combined
@app.get("/patients/{pid}/examinations")
async def read_examinations_for_patient(pid: str, skip: int = 0, limit: int = 10):
    examinations: List[Examination] = []
    examination_docs = db.examinations.find({'patient_id': pid})
    async for row in examination_docs:
        examination = Examination(**row)  # hier Fehlerbehebung einbauen
        examination.id = str(row["_id"])
        examinations.append(examination)
    return examinations