import pytest
from pipeline.core import connection, ingest, report

def test_idempotent_ingestion(tmp_path):
    path=tmp_path/'test.db'
    ingest(path)
    with connection(path) as con:
        a=con.execute('SELECT COUNT(*) FROM appointments').fetchone()[0]
        q=con.execute('SELECT COUNT(*) FROM quarantined_records').fetchone()[0]
    ingest(path)
    with connection(path) as con:
        assert con.execute('SELECT COUNT(*) FROM appointments').fetchone()[0]==a==2100
        assert con.execute('SELECT COUNT(*) FROM quarantined_records').fetchone()[0]==q==3
        assert con.execute('SELECT COUNT(*) FROM ingestion_log').fetchone()[0]==2

def test_dashboard_consistency(tmp_path):
    p=tmp_path/'test.db';ingest(p)
    with connection(p) as con:
        r=report(con,'all',90)
        assert r['summary']['appointments']==2100
        assert sum(x['appointments'] for x in r['clinics'])==2100
        assert r['summary']['completed']<=2100
        assert r['quality']['duplicate_appointment_ids']==0
        sub=report(con,'CL-01',7)
        assert sub['summary']['appointments']<=r['summary']['appointments']

def test_filter_validation(tmp_path):
    p=tmp_path/'test.db';ingest(p)
    with connection(p) as con:
        with pytest.raises(ValueError):report(con,'wrong',90)
        with pytest.raises(ValueError):report(con,'all',500)
