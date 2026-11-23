# Business metrics

Definitions used in the Olist warehouse (`marts` schema) and in the Power BI report.
All money values are in Brazilian reais (BRL, R$).

## Revenue

Revenue is the sum of item prices: `sum(fct_order_items.price)`, or `sum(fct_orders.items_amount)` at order level.
Freight (shipping cost paid by the customer) is NOT part of revenue; it is reported separately as `freight_value` / `freight_amount`.
Payment amount (`fct_orders.payment_amount`) includes freight and may be split across several payment methods (credit card, boleto, vouchers), so it is not used as revenue.
Use `fct_order_items` for revenue by product, category or seller, and `fct_orders` for revenue by customer or date.

## Orders and customers

An order is one row in `fct_orders` (grain: order). Count orders with `count(*)` on `fct_orders` or `count(distinct order_id)` on `fct_order_items`.
A customer is a real person identified by `customer_unique_id`. Olist creates a new `customer_id` for every order, so never count customers by `customer_id`.
Repeat customers are customers with `dim_customers.orders_count > 1`.

## Average order value (AOV)

AOV = revenue / number of orders. Compute it from item revenue: `sum(price) / count(distinct order_id)` on `fct_order_items`.
Only orders that have items are included; about 775 orders (mostly canceled or unavailable) have no items.

## Delivery time

Delivery days (`fct_orders.delivery_days`) is the time from purchase (`ordered_at`) to delivery to the customer (`delivered_at`), in days with one decimal.
It is null for orders that were not delivered. Average delivery time = `avg(delivery_days)` over delivered orders.

## Late delivery

An order is late (`fct_orders.is_late = true`) when the customer received it after the estimated delivery date promised at purchase (`delivered_at::date > estimated_delivery_at::date`).
`is_late` is null for orders that were not delivered.
Late delivery % = late orders / delivered orders: `avg(is_late::int)` over rows where `is_late is not null`.

## Review score

Customers rate orders from 1 (worst) to 5 (best). `fct_orders.review_score` is the average score of the order's reviews; null if the order has no review.
Average review score = `avg(review_score)`. Low scores are strongly associated with late deliveries.