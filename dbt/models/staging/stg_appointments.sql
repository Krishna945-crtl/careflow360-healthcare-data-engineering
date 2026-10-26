with deduped as (
 select appointment_id, patient_id, clinic_id, scheduled_date, lower(status) as status,
        type as appointment_type, updated_at,
        row_number() over (partition by appointment_id order by updated_at desc, ingested_at desc) as rn
 from {{ source('raw', 'appointments') }}
)
select appointment_id, patient_id, clinic_id, scheduled_date, status, appointment_type, updated_at
from deduped where rn=1
