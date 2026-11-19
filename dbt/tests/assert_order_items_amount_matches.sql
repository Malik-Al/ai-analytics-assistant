-- fct_orders.items_amount must equal the sum of item prices in fct_order_items
select o.order_id
from {{ ref('fct_orders') }} o
left join (
    select order_id, sum(price) as items_sum
    from {{ ref('fct_order_items') }}
    group by 1
) i on i.order_id = o.order_id
where o.items_amount <> coalesce(i.items_sum, 0)