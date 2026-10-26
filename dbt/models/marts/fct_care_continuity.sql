with encounter_by_appt as (
 select appointment_id, min(encountered_on) as encountered_on, count(*) as encounter_count
 from {{ ref('stg_encounters') }} group by 1
)
select a.appointment_id, a.patient_id, a.clinic_id, a.scheduled_date, a.status,
 a.appointment_type, e.encountered_on, coalesce(e.encounter_count,0) as encounter_count,
 iff(a.appointment_type='Follow-up' and a.status='completed' and e.encountered_on is null,1,0) as care_gap_flag,
 iff(a.status='completed' and e.encountered_on is null,1,0) as missing_encounter_flag
from {{ ref('stg_appointments') }} a left join encounter_by_appt e using (appointment_id)
