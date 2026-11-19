with items as (
    select * from {{ ref('stg_order_items') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select customer_id, customer_unique_id from {{ ref('stg_customers') }}
)

select
    md5(i.order_id || '-' || i.order_item_id)    as order_item_key,
    i.order_id,
    i.order_item_id,
    c.customer_unique_id,
    i.product_id,
    i.seller_id,
    o.ordered_at::date                           as order_date,
    o.order_status,
    i.price,
    i.freight_value,
    i.price + i.freight_value                    as total_amount
from items i
join orders o    on o.order_id = i.order_id
join customers c on c.customer_id = o.customer_id