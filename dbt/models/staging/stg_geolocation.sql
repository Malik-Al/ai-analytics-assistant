with source as (
    select * from {{ source('olist', 'geolocation') }}
)

select
    geolocation_zip_code_prefix                                  as zip_code_prefix,
    avg(geolocation_lat::numeric)::numeric(9, 6)                 as latitude,
    avg(geolocation_lng::numeric)::numeric(9, 6)                 as longitude,
    mode() within group (order by lower(geolocation_city))       as city,
    mode() within group (order by upper(geolocation_state))      as state
from source
group by 1