with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select customer_id, customer_unique_id from {{ ref('stg_customers') }}
),

items as (
    select
        order_id,
        count(*)            as item_count,
        sum(price)          as items_amount,
        sum(freight_value)  as freight_amount
    from {{ ref('stg_order_items') }}
    group by 1
),

payments as (
    select
        order_id,
        sum(payment_value)          as payment_amount,
        max(payment_installments)   as max_installments
    from {{ ref('stg_order_payments') }}
    group by 1
),

reviews as (
    select
        order_id,
        avg(review_score)::numeric(3, 2) as review_score
    from {{ ref('stg_order_reviews') }}
    group by 1
)

select
    o.order_id,
    c.customer_unique_id,
    o.ordered_at::date                                  as order_date,
    o.order_status,
    o.ordered_at,
    o.approved_at,
    o.shipped_at,
    o.delivered_at,
    o.estimated_delivery_at,
    coalesce(i.item_count, 0)                           as item_count,
    coalesce(i.items_amount, 0)                         as items_amount,
    coalesce(i.freight_amount, 0)                       as freight_amount,
    coalesce(p.payment_amount, 0)                       as payment_amount,
    p.max_installments,
    r.review_score,
    round((extract(epoch from (o.delivered_at - o.ordered_at)) / 86400)::numeric, 1)
                                                        as delivery_days,
    case
        when o.delivered_at is null then null
        else o.delivered_at::date > o.estimated_delivery_at::date
    end                                                 as is_late
from orders o
join customers c      on c.customer_id = o.customer_id
left join items i     on i.order_id = o.order_id
left join payments p  on p.order_id = o.order_id
left join reviews r   on r.order_id = o.order_id