with sellers as (
    select * from {{ ref('stg_sellers') }}
),

geo as (
    select * from {{ ref('stg_geolocation') }}
)

select
    s.seller_id,
    s.zip_code_prefix,
    s.city,
    s.state,
    g.latitude,
    g.longitude
from sellers s
left join geo g using (zip_code_prefix)