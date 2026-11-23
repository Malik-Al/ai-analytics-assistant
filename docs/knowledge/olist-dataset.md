# Olist dataset notes

Olist is a Brazilian e-commerce marketplace: many independent sellers sell products to customers across Brazil through one platform.
The public dataset covers orders placed from September 2016 to October 2018.

## Time coverage

Data before January 2017 is very sparse (a few hundred orders), so monthly metrics for 2016 are unreliable.
The last full month is August 2018; September and October 2018 contain only a handful of orders and should be excluded from trends.

## Order status

`order_status` values: delivered, shipped, canceled, unavailable, invoiced, processing, created, approved.
About 97% of orders are delivered. For revenue and delivery metrics, most analyses filter to `order_status = 'delivered'`.

## Geography

Customer and seller locations are Brazilian states (two-letter codes such as SP, RJ, MG) and cities.
São Paulo (SP) has the most customers and sellers. Remote northern and northeastern states have longer delivery times and more late deliveries.

## Product categories

Category names come from the product catalog in Portuguese and are translated to English (`dim_products.category`).
Products without a category are labeled `unknown`. The top categories by revenue are health_beauty, watches_gifts and bed_bath_table.