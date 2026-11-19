with source as (
    select * from {{ source('olist', 'order_reviews') }}
),

typed as (
    select
        md5(review_id || '-' || order_id)          as review_key,
        review_id,
        order_id,
        review_score::int                          as review_score,
        nullif(trim(review_comment_title), '')     as comment_title,
        nullif(trim(review_comment_message), '')   as comment_message,
        review_creation_date::timestamp            as created_at,
        review_answer_timestamp::timestamp         as answered_at
    from source
),

deduplicated as (
    select
        *,
        row_number() over (
            partition by review_key
            order by answered_at desc
        ) as rn
    from typed
)

select
    review_key, review_id, order_id, review_score,
    comment_title, comment_message, created_at, answered_at
from deduplicated
where rn = 1