with products as (
    select * from {{ ref('stg_products') }}
),

translation as (
    select * from {{ ref('stg_product_category_translation') }}
)

select
    p.product_id,
    coalesce(p.category_name, 'unknown')                         as category_name_pt,
    coalesce(t.category_name_en, p.category_name, 'unknown')     as category,
    p.name_length,
    p.description_length,
    p.photos_qty,
    p.weight_g,
    p.length_cm,
    p.height_cm,
    p.width_cm
from products p
left join translation t using (category_name)