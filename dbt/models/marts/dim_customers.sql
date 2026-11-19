with customers as (
    select * from {{ ref('stg_customers') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

geo as (
    select * from {{ ref('stg_geolocation') }}
),

customer_orders as (
    select
        c.customer_unique_id,
        c.zip_code_prefix,
        c.city,
        c.state,
        o.ordered_at
    from customers c
    join orders o on o.customer_id = c.customer_id
),

latest_address as (
    select distinct on (customer_unique_id)
        customer_unique_id,
        zip_code_prefix,
        city,
        state
    from customer_orders
    order by customer_unique_id, ordered_at desc
),

order_stats as (
    select
        customer_unique_id,
        min(ordered_at) as first_order_at,
        max(ordered_at) as last_order_at,
        count(*)        as orders_count
    from customer_orders
    group by 1
)

select
    a.customer_unique_id,
    a.zip_code_prefix,
    a.city,
    a.state,
    g.latitude,
    g.longitude,
    s.first_order_at,
    s.last_order_at,
    s.orders_count
from latest_address a
join order_stats s using (customer_unique_id)
left join geo g using (zip_code_prefix)