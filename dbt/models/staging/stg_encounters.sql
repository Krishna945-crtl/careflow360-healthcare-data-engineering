with ranked as (
 select encounter_id, appointment_id, encountered_on, updated_at,
 row_number() over(partition by encounter_id order by updated_at desc, ingested_at desc) as rn
 from {{ source('raw', 'encounters') }}
)
select encounter_id, appointment_id, encountered_on from ranked where rn=1
