select clinic_id, date_trunc('week', scheduled_date)::date as week_start,
 count(*) as appointments,
 sum(iff(status='completed',1,0)) as completed,
 sum(iff(status='no_show',1,0)) as no_shows,
 sum(care_gap_flag) as care_gaps,
 round(100.0 * sum(iff(status='completed',1,0)) / nullif(count(*),0),1) as completion_rate
from {{ ref('fct_care_continuity') }} group by 1,2
