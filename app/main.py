from pathlib import Path
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pipeline.core import connection, ingest, report, CLINICS
import csv, io
ROOT=Path(__file__).resolve().parents[1]
DB=Path(os.getenv('CAREFLOW_DB',str(ROOT/'data'/'careflow.db')))
app=FastAPI(title='CareFlow 360',description='Synthetic healthcare operations analytics',version='1.0.0')
app.mount('/static',StaticFiles(directory=str(ROOT/'app'/'static')),name='static')

def ensure():
    with connection(DB) as con:
        if con.execute('SELECT COUNT(*) FROM appointments').fetchone()[0]==0: ingest(DB)

@app.on_event('startup')
def boot(): ensure()
@app.get('/')
def home(): return FileResponse(ROOT/'app'/'static'/'index.html')
@app.get('/api/health')
def health(): return {'status':'ok','dataset':'synthetic','version':'1.0.0'}
@app.get('/api/clinics')
def clinics(): return [{'id':c[0],'name':c[1],'region':c[2]} for c in CLINICS]
@app.get('/api/dashboard')
def dashboard(clinic:str='all',days:int=Query(90)):
    try:
        with connection(DB) as con: return report(con,clinic,days)
    except ValueError as e: raise HTTPException(400,str(e)) from e
@app.post('/api/pipeline/run')
def run_pipeline():
    # Demonstration only: do not deploy this admin endpoint publicly without authentication.
    return ingest(DB)
@app.get('/api/exceptions.csv')
def exceptions_csv(clinic:str='all',days:int=90):
    try:
        with connection(DB) as con: rows=report(con,clinic,days)['exceptions']
    except ValueError as e: raise HTTPException(400,str(e)) from e
    s=io.StringIO(); w=csv.DictWriter(s,fieldnames=['id','clinic','date','status','issue','patient_ref']);w.writeheader();w.writerows(rows)
    return StreamingResponse(iter([s.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=careflow-exceptions.csv'})
