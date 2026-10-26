"""Reproducible synthetic healthcare operations data and audit-friendly ETL.
No patient data is real. Local SQLite is the self-contained demo warehouse.
"""
from __future__ import annotations
import csv
import hashlib
import random
import sqlite3
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

CLINICS = [
    ('CL-01','Riverside Family Health','North'),
    ('CL-02','Oakwood Care Center','South'),
    ('CL-03','Cedar Medical Group','East'),
    ('CL-04','Maple Community Clinic','West'),
    ('CL-05','Willow Health Partners','Central'),
]
FIRST=['Aarav','Anaya','Diya','Ishaan','Meera','Rohan','Sana','Vivaan','Tara','Kabir','Nisha','Aditya']
LAST=['Sharma','Rao','Nair','Patel','Singh','Mehta','Das','Kumar']
STATUSES=['completed','completed','completed','completed','completed','no_show','cancelled','scheduled']
SCHEMA='''
CREATE TABLE IF NOT EXISTS clinics(clinic_id TEXT PRIMARY KEY, name TEXT NOT NULL, region TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS patients(patient_id TEXT PRIMARY KEY, name TEXT NOT NULL, birth_year INTEGER, clinic_id TEXT REFERENCES clinics(clinic_id));
CREATE TABLE IF NOT EXISTS appointments(appointment_id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patients(patient_id), clinic_id TEXT NOT NULL REFERENCES clinics(clinic_id), scheduled_date TEXT NOT NULL, status TEXT NOT NULL, type TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS encounters(encounter_id TEXT PRIMARY KEY, appointment_id TEXT UNIQUE REFERENCES appointments(appointment_id), encountered_on TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ingestion_log(run_id INTEGER PRIMARY KEY AUTOINCREMENT, run_at TEXT NOT NULL, source_rows INTEGER NOT NULL, accepted INTEGER NOT NULL, rejected INTEGER NOT NULL, note TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quarantined_records(id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, record_id TEXT NOT NULL, reason TEXT NOT NULL, run_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_appt_clinic_day ON appointments(clinic_id, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_appt_patient ON appointments(patient_id);
'''

def connection(path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(path)); con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript(SCHEMA)
    return con

def fixture_rows(seed=360):
    r=random.Random(seed); today=date.today(); patients=[]; appts=[]; encounters=[]
    for i in range(1,701):
        cid=CLINICS[(i-1)%len(CLINICS)][0]
        patients.append((f'PT-{i:04}',f'{r.choice(FIRST)} {r.choice(LAST)}',r.randint(1950,2006),cid))
    for i in range(1,2101):
        pid=patients[r.randrange(len(patients))][0]
        cid=CLINICS[r.randrange(len(CLINICS))][0] # intentional cross-clinic visits
        d=today-timedelta(days=r.randint(0,89)); status=r.choice(STATUSES)
        aid=f'AP-{i:05}'
        updated=(datetime.combine(d,datetime.min.time()).replace(tzinfo=timezone.utc)+timedelta(days=r.randint(0,2))).isoformat()
        appts.append((aid,pid,cid,d.isoformat(),status,r.choice(['Primary care','Follow-up','Screening','Wellness']),updated))
        if status=='completed' and r.random()<0.92:
            encounters.append((f'EN-{i:05}',aid,(d+timedelta(days=r.choice([0,0,0,1,3]))).isoformat(),updated))
    return patients,appts,encounters

def ingest(db_path, seed=360, inject_quality_issues=True):
    """Idempotent UPSERT; invalid simulated source events go to quarantine."""
    con=connection(db_path); now=datetime.now(timezone.utc).isoformat(); patients,appts,encounters=fixture_rows(seed)
    rejects=[]
    with con:
        con.executemany('INSERT OR IGNORE INTO clinics VALUES(?,?,?)',CLINICS)
        con.executemany('INSERT INTO patients VALUES(?,?,?,?) ON CONFLICT(patient_id) DO UPDATE SET name=excluded.name, birth_year=excluded.birth_year, clinic_id=excluded.clinic_id',patients)
        con.executemany('INSERT INTO appointments VALUES(?,?,?,?,?,?,?) ON CONFLICT(appointment_id) DO UPDATE SET patient_id=excluded.patient_id,clinic_id=excluded.clinic_id,scheduled_date=excluded.scheduled_date,status=excluded.status,type=excluded.type,updated_at=excluded.updated_at',appts)
        con.executemany('INSERT INTO encounters VALUES(?,?,?,?) ON CONFLICT(encounter_id) DO UPDATE SET appointment_id=excluded.appointment_id,encountered_on=excluded.encountered_on,updated_at=excluded.updated_at',encounters)
        if inject_quality_issues:
            rejects=[('appointments','AP-BAD-01','Missing patient_id'),('appointments','AP-BAD-02','Unknown clinic_id CL-99'),('encounters','EN-BAD-01','Unknown appointment_id')]
            # quarantine only new unique issues per run; no misleading new records after replay
            for source, rid, reason in rejects:
                if not con.execute('SELECT 1 FROM quarantined_records WHERE source=? AND record_id=?',(source,rid)).fetchone():
                    con.execute('INSERT INTO quarantined_records(source,record_id,reason,run_at) VALUES (?,?,?,?)',(source,rid,reason,now))
        count=len(patients)+len(appts)+len(encounters)+len(rejects)
        con.execute('INSERT INTO ingestion_log(run_at,source_rows,accepted,rejected,note) VALUES(?,?,?,?,?)',(now,count,count-len(rejects),len(rejects),'Synthetic deterministic UPSERT load'))
    con.close()
    return {'source_rows':count,'accepted':count-len(rejects),'rejected':len(rejects),'message':'Ingestion completed; reruns update records, not duplicate them.'}

def report(con, clinic='all', days=90):
    if days not in (7,30,90): raise ValueError('Unsupported date range')
    today=date.today(); cutoff=(today-timedelta(days=days-1)).isoformat()
    where='scheduled_date >= ?'
    p=[cutoff]
    if clinic!='all':
        if clinic not in {x[0] for x in CLINICS}: raise ValueError('Unknown clinic')
        where+=' AND a.clinic_id = ?'; p.append(clinic)
    base=f'''SELECT a.*, c.name clinic_name, c.region, e.encounter_id, e.encountered_on,
               CASE WHEN a.type='Follow-up' AND a.status='completed' AND e.encounter_id IS NULL THEN 1 ELSE 0 END care_gap
               FROM appointments a JOIN clinics c ON c.clinic_id=a.clinic_id
               LEFT JOIN encounters e ON e.appointment_id=a.appointment_id WHERE {where}'''
    rows=[dict(x) for x in con.execute(base,p).fetchall()]
    n=len(rows); complete=sum(x['status']=='completed' for x in rows); no_show=sum(x['status']=='no_show' for x in rows)
    gaps=sum(x['care_gap'] for x in rows); unmatched=sum(x['status']=='completed' and not x['encounter_id'] for x in rows)
    trends=[]
    for i in reversed(range(10)):
        end=today-timedelta(days=i*7); begin=end-timedelta(days=6)
        subset=[x for x in rows if begin.isoformat()<=x['scheduled_date']<=end.isoformat()]
        trends.append({'week':begin.strftime('%b %d'),'completed':sum(x['status']=='completed' for x in subset),'no_show':sum(x['status']=='no_show' for x in subset),'scheduled':len(subset)})
    clinics=[]
    for cid,name,reg in CLINICS:
        s=[x for x in rows if x['clinic_id']==cid];
        if s: clinics.append({'id':cid,'name':name,'region':reg,'appointments':len(s),'completion_rate':round(100*sum(x['status']=='completed' for x in s)/len(s),1),'no_show_rate':round(100*sum(x['status']=='no_show' for x in s)/len(s),1),'care_gaps':sum(x['care_gap'] for x in s)})
    clinics.sort(key=lambda x:-x['appointments'])
    recent=sorted([x for x in rows if x['care_gap'] or (x['status']=='completed' and not x['encounter_id'])],key=lambda x:x['scheduled_date'], reverse=True)[:12]
    issues=[dict(x) for x in con.execute('SELECT source,record_id,reason,run_at FROM quarantined_records ORDER BY id DESC LIMIT 10')]
    last=con.execute('SELECT run_at,source_rows,accepted,rejected FROM ingestion_log ORDER BY run_id DESC LIMIT 1').fetchone()
    unique_patients=len(set(x['patient_id'] for x in rows))
    return {'period_days':days,'clinic':clinic,'summary':{'appointments':n,'unique_patients':unique_patients,'completed':complete,'completion_rate':round(100*complete/n,1) if n else 0,'no_shows':no_show,'no_show_rate':round(100*no_show/n,1) if n else 0,'care_gaps':gaps,'unmatched_encounters':unmatched},'trends':trends,'clinics':clinics,'exceptions':[{'id':x['appointment_id'],'clinic':x['clinic_name'],'date':x['scheduled_date'],'status':x['status'],'issue':'Missing encounter' if not x['encounter_id'] else 'Care follow-up gap','patient_ref':hashlib.sha256(x['patient_id'].encode()).hexdigest()[:8].upper()} for x in recent], 'quality':{'quarantined_total':con.execute('SELECT COUNT(*) FROM quarantined_records').fetchone()[0],'issues':issues,'last_run':dict(last) if last else None,'duplicate_appointment_ids':con.execute('SELECT COUNT(*)-COUNT(DISTINCT appointment_id) FROM appointments').fetchone()[0]}}

def export_synthetic_csv(path,seed=360):
    path=Path(path); path.mkdir(parents=True,exist_ok=True)
    for name,headers,records in [('patients',['patient_id','name','birth_year','clinic_id'],fixture_rows(seed)[0]),('appointments',['appointment_id','patient_id','clinic_id','scheduled_date','status','type','updated_at'],fixture_rows(seed)[1]),('encounters',['encounter_id','appointment_id','encountered_on','updated_at'],fixture_rows(seed)[2])]:
        with (path/(name+'.csv')).open('w',newline='') as f:
            w=csv.writer(f);w.writerow(headers);w.writerows(records)
    with (path/'clinics.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['clinic_id','name','region']);w.writerows(CLINICS)
