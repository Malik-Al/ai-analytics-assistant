with source as (
    select * from {{ source('olist', 'products') }}
)

select
    product_id,
    product_category_name                         as category_name,
    product_name_lenght::numeric::int             as name_length,
    product_description_lenght::numeric::int      as description_length,
    product_photos_qty::numeric::int              as photos_qty,
    product_weight_g::numeric::int                as weight_g,
    product_length_cm::numeric::int               as length_cm,
    product_height_cm::numeric::int               as height_cm,
    product_width_cm::numeric::int                as width_cm
from source