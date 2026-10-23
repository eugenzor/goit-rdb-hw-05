from pathlib import Path

import kagglehub
import pandas as pd
import pgserver
import sqlparse
from sqlalchemy import create_engine, make_url, text

BASE_DIR = Path(__file__).parent
PG_DATA_DIR = BASE_DIR / ".pg_data"

engine = None


def display(df: pd.DataFrame):
    print(df.to_string())


def header(title: str):
    line = "=" * 72
    print(f"\n{line}\n{title}\n{line}")


def run_sql(sql: str):
    with engine.begin() as conn:
        for statement in sqlparse.split(sql):
            statement = statement.strip()
            if not statement:
                continue
            result = conn.execute(text(statement))
            if result.returns_rows:
                display(pd.DataFrame(result.fetchall(), columns=result.keys()))
            else:
                print(f"OK: {result.rowcount} rows")


def show_version():
    header("PostgreSQL")
    run_sql("SELECT version() AS postgresql_version;")


def prepare_dataset():
    global DATA_MODE, csv_paths
    header("Завантаження датасету Olist")
    LOCAL_DATASET_DIR = None  # Наприклад: "/content/data/olist"

    files = {
        "olist_customers_raw": "olist_customers_dataset.csv",
        "olist_orders_raw": "olist_orders_dataset.csv",
        "olist_order_items_raw": "olist_order_items_dataset.csv",
        "olist_products_raw": "olist_products_dataset.csv",
        "olist_sellers_raw": "olist_sellers_dataset.csv",
    }

    def find_required_csv(base):
        base = Path(base)
        return {table: next(base.rglob(name), None) for table, name in files.items()}

    DATA_MODE = "stub"
    csv_paths = {}

    if LOCAL_DATASET_DIR is not None:
        dataset_dir = LOCAL_DATASET_DIR
    else:
        dataset_dir = kagglehub.dataset_download("olistbr/brazilian-ecommerce")
    csv_paths = find_required_csv(dataset_dir)
    missing = [table for table, path in csv_paths.items() if path is None]
    DATA_MODE = "olist"
    print(csv_paths)


def load_tables():
    header("Typed-схема і завантаження")
    TYPED_DDL = """
DROP TABLE IF EXISTS olist_order_items CASCADE;
DROP TABLE IF EXISTS olist_orders      CASCADE;
DROP TABLE IF EXISTS olist_customers   CASCADE;
DROP TABLE IF EXISTS olist_products    CASCADE;
DROP TABLE IF EXISTS olist_sellers     CASCADE;

CREATE TABLE olist_customers (
    customer_id              TEXT PRIMARY KEY,
    customer_unique_id       TEXT NOT NULL,
    customer_zip_code_prefix INTEGER,
    customer_city            TEXT,
    customer_state           CHAR(2) NOT NULL
);

CREATE TABLE olist_orders (
    order_id                      TEXT PRIMARY KEY,
    customer_id                   TEXT NOT NULL REFERENCES olist_customers(customer_id),
    order_status                  TEXT NOT NULL,
    order_purchase_timestamp      TIMESTAMP NOT NULL,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,
    CHECK (order_status IN (
        'created', 'approved', 'invoiced', 'processing',
        'shipped', 'delivered', 'unavailable', 'canceled'
    ))
);

CREATE TABLE olist_products (
    product_id                 TEXT PRIMARY KEY,
    product_category_name      TEXT,
    product_name_length        INTEGER CHECK (product_name_length IS NULL OR product_name_length >= 0),
    product_description_length INTEGER CHECK (product_description_length IS NULL OR product_description_length >= 0),
    product_photos_qty         INTEGER CHECK (product_photos_qty IS NULL OR product_photos_qty >= 0),
    product_weight_g           INTEGER CHECK (product_weight_g IS NULL OR product_weight_g >= 0),
    product_length_cm          INTEGER CHECK (product_length_cm IS NULL OR product_length_cm >= 0),
    product_height_cm          INTEGER CHECK (product_height_cm IS NULL OR product_height_cm >= 0),
    product_width_cm           INTEGER CHECK (product_width_cm IS NULL OR product_width_cm >= 0)
);

CREATE TABLE olist_sellers (
    seller_id              TEXT PRIMARY KEY,
    seller_zip_code_prefix INTEGER,
    seller_city            TEXT,
    seller_state           CHAR(2) NOT NULL
);

CREATE TABLE olist_order_items (
    order_id            TEXT NOT NULL REFERENCES olist_orders(order_id),
    order_item_id       INTEGER NOT NULL,
    product_id          TEXT REFERENCES olist_products(product_id),
    seller_id           TEXT REFERENCES olist_sellers(seller_id),
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(12, 2) CHECK (price IS NULL OR price >= 0),
    freight_value       NUMERIC(12, 2) CHECK (freight_value IS NULL OR freight_value >= 0),
    PRIMARY KEY (order_id, order_item_id)
);
    """

    RAW_TO_TYPED_SQL = """
INSERT INTO olist_customers
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix::INTEGER,
    customer_city,
    customer_state::CHAR(2)
FROM olist_customers_raw;

INSERT INTO olist_orders
SELECT
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp::TIMESTAMP,
    order_approved_at::TIMESTAMP,
    order_delivered_carrier_date::TIMESTAMP,
    order_delivered_customer_date::TIMESTAMP,
    order_estimated_delivery_date::TIMESTAMP
FROM olist_orders_raw;

INSERT INTO olist_products
SELECT
    product_id,
    product_category_name,
    product_name_lenght::INTEGER,
    product_description_lenght::INTEGER,
    product_photos_qty::INTEGER,
    product_weight_g::INTEGER,
    product_length_cm::INTEGER,
    product_height_cm::INTEGER,
    product_width_cm::INTEGER
FROM olist_products_raw;

INSERT INTO olist_sellers
SELECT
    seller_id,
    seller_zip_code_prefix::INTEGER,
    seller_city,
    seller_state::CHAR(2)
FROM olist_sellers_raw;

INSERT INTO olist_order_items
SELECT
    order_id,
    order_item_id::INTEGER,
    product_id,
    seller_id,
    shipping_limit_date::TIMESTAMP,
    price::NUMERIC(12, 2),
    freight_value::NUMERIC(12, 2)
FROM olist_order_items_raw;
    """

    STUB_SQL = """
DROP TABLE IF EXISTS olist_order_items CASCADE;
DROP TABLE IF EXISTS olist_orders      CASCADE;
DROP TABLE IF EXISTS olist_customers   CASCADE;
DROP TABLE IF EXISTS olist_products    CASCADE;
DROP TABLE IF EXISTS olist_sellers     CASCADE;

CREATE TABLE olist_customers (
    customer_id              TEXT PRIMARY KEY,
    customer_unique_id       TEXT NOT NULL,
    customer_zip_code_prefix INTEGER,
    customer_state           CHAR(2) NOT NULL,
    customer_city            TEXT
);

CREATE TABLE olist_orders (
    order_id                      TEXT PRIMARY KEY,
    customer_id                   TEXT NOT NULL REFERENCES olist_customers(customer_id),
    order_status                  TEXT NOT NULL,
    order_purchase_timestamp      TIMESTAMP NOT NULL,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,
    CHECK (order_status IN (
        'created', 'approved', 'invoiced', 'processing',
        'shipped', 'delivered', 'unavailable', 'canceled'
    ))
);

CREATE TABLE olist_products (
    product_id                 TEXT PRIMARY KEY,
    product_category_name      TEXT,
    product_name_length        INTEGER CHECK (product_name_length IS NULL OR product_name_length >= 0),
    product_description_length INTEGER CHECK (product_description_length IS NULL OR product_description_length >= 0),
    product_photos_qty         INTEGER CHECK (product_photos_qty IS NULL OR product_photos_qty >= 0),
    product_weight_g           INTEGER CHECK (product_weight_g IS NULL OR product_weight_g >= 0),
    product_length_cm          INTEGER CHECK (product_length_cm IS NULL OR product_length_cm >= 0),
    product_height_cm          INTEGER CHECK (product_height_cm IS NULL OR product_height_cm >= 0),
    product_width_cm           INTEGER CHECK (product_width_cm IS NULL OR product_width_cm >= 0)
);

CREATE TABLE olist_sellers (
    seller_id              TEXT PRIMARY KEY,
    seller_zip_code_prefix INTEGER,
    seller_city            TEXT,
    seller_state           CHAR(2) NOT NULL
);

CREATE TABLE olist_order_items (
    order_id            TEXT NOT NULL REFERENCES olist_orders(order_id),
    order_item_id       INTEGER NOT NULL,
    product_id          TEXT REFERENCES olist_products(product_id),
    seller_id           TEXT REFERENCES olist_sellers(seller_id),
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(12, 2) CHECK (price IS NULL OR price >= 0),
    freight_value       NUMERIC(12, 2) CHECK (freight_value IS NULL OR freight_value >= 0),
    PRIMARY KEY (order_id, order_item_id)
);

INSERT INTO olist_sellers (
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state
)
VALUES
    ('s_01', 10001, 'Sao Paulo', 'SP'),
    ('s_02', 20001, 'Rio de Janeiro', 'RJ'),
    ('s_03', 30001, 'Belo Horizonte', 'MG');

INSERT INTO olist_products (
    product_id,
    product_category_name,
    product_name_length,
    product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm
)
VALUES
    ('p_01', 'electronics', 10, 100, 2,  800, 20, 10, 15),
    ('p_02', 'electronics', 12, 120, 3, 1200, 25, 12, 18),
    ('p_03', 'home',        8,  90, 1, 1500, 30, 20, 25),
    ('p_04', 'home',        9,  80, 2,  700, 18, 10, 14),
    ('p_05', 'fashion',     7,  60, 1,  300, 10,  5,  8),
    ('p_06', 'beauty',      6,  50, 1,  200,  8,  4,  6),
    ('p_07', 'sport',       9,  70, 2,  900, 20, 15, 16);

INSERT INTO olist_customers (
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_state,
    customer_city
)
SELECT
    'c_' || LPAD(n::TEXT, 3, '0'),
    'u_' || LPAD(((n - 1) % 25 + 1)::TEXT, 3, '0'),
    10000 + n,
    (ARRAY['SP', 'RJ', 'MG', 'BA', 'PR'])[(n % 5) + 1],
    'City' || (n % 10)
FROM generate_series(1, 30) AS n;

INSERT INTO olist_orders (
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date
)
SELECT
    'o_' || LPAD(n::TEXT, 3, '0'),
    'c_' || LPAD(((n % 30) + 1)::TEXT, 3, '0'),
    (ARRAY['delivered', 'delivered', 'delivered', 'canceled', 'shipped'])[(n % 5) + 1],
    TIMESTAMP '2024-01-01 00:00:00' + (n * INTERVAL '7 days'),
    TIMESTAMP '2024-01-01 00:00:00' + (n * INTERVAL '7 days') + INTERVAL '1 day',
    TIMESTAMP '2024-01-01 00:00:00' + (n * INTERVAL '7 days') + INTERVAL '3 days',
    TIMESTAMP '2024-01-01 00:00:00' + (n * INTERVAL '7 days') + INTERVAL '8 days',
    TIMESTAMP '2024-01-01 00:00:00' + (n * INTERVAL '7 days') + INTERVAL '10 days'
FROM generate_series(1, 50) AS n;

INSERT INTO olist_order_items (
    order_id,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date,
    price,
    freight_value
)
SELECT
    'o_' || LPAD(((n - 1) % 50 + 1)::TEXT, 3, '0'),
    ((n - 1) / 50) + 1,
    'p_0' || ((n % 7) + 1),
    's_0' || ((n % 3) + 1),
    TIMESTAMP '2024-01-01 00:00:00' + (n * INTERVAL '7 days') + INTERVAL '5 days',
    (n % 200 + 10)::NUMERIC(12, 2),
    (n % 30 + 5)::NUMERIC(12, 2)
FROM generate_series(1, 100) AS n;
    """

    if DATA_MODE == "olist":
        for table_name, path in csv_paths.items():
            df = pd.read_csv(path)
            df.to_sql(
                table_name, engine, if_exists="replace", index=False,
                chunksize=5_000, method="multi"
            )
            print(f"{table_name}: {len(df):,} rows")
            del df

        run_sql(TYPED_DDL)
        run_sql(RAW_TO_TYPED_SQL)
    else:
        run_sql(STUB_SQL)


def smoke_test():
    header("Smoke-test кількості рядків")
    # Додайте smoke-test кількості рядків.
    run_sql("""
SELECT 'customers' AS table_name, COUNT(*) AS n_rows
FROM olist_customers

UNION ALL

SELECT 'orders', COUNT(*)
FROM olist_orders

UNION ALL

SELECT 'order_items', COUNT(*)
FROM olist_order_items

UNION ALL

SELECT 'products', COUNT(*)
FROM olist_products

UNION ALL

SELECT 'sellers', COUNT(*)
FROM olist_sellers

ORDER BY table_name;
    """)

    with engine.connect() as conn:
        for base in ["customers", "orders", "order_items", "products", "sellers"]:
            n_typed = conn.execute(text(f"SELECT COUNT(*) FROM olist_{base}")).scalar_one()

            if DATA_MODE == "olist":
                n_raw = conn.execute(text(f"SELECT COUNT(*) FROM olist_{base}_raw")).scalar_one()
                assert n_raw == n_typed, f"{base}: raw={n_raw}, typed={n_typed}"

            assert n_typed > 0, f"Порожня таблиця: {base}"

    print("Smoke test: OK; усі 5 typed-таблиць заповнені.")


def feature_pipeline():
    global FEATURE_SQL
    header("Завдання 2. CTE-chain pipeline")
    # Завдання 2. CTE-chain pipeline з ≥5 stages
    CTE_COMMON = """
WITH
-- Stage 0: стабільна дата для історичного датасету
reference_date AS (
    SELECT (MAX(order_purchase_timestamp)::DATE + 1) AS as_of_date
    FROM olist_orders
),

-- Stage 1: одна сума та один статус для кожного замовлення
stage1_orders_total AS (
    SELECT
        o.customer_id,
        o.order_id,
        o.order_status,
        o.order_purchase_timestamp AS order_ts,
        o.order_purchase_timestamp::DATE AS order_date,
        COALESCE(SUM(
            COALESCE(oi.price, 0) + COALESCE(oi.freight_value, 0)
        ), 0)::NUMERIC(12, 2) AS order_total
    FROM olist_orders AS o
    LEFT JOIN olist_order_items AS oi
        ON oi.order_id = o.order_id
    GROUP BY
        o.customer_id,
        o.order_id,
        o.order_status,
        o.order_purchase_timestamp
),

-- Stage 2: RFM та дата першого замовлення для кожного customer_id
stage2_rfm AS (
    SELECT
        s.customer_id,
        (rd.as_of_date - MAX(s.order_date))::INTEGER AS recency_days,
        COUNT(*) AS frequency,
        SUM(s.order_total)::NUMERIC(12, 2) AS monetary,
        MIN(s.order_date) AS first_order_date
    FROM stage1_orders_total AS s
    CROSS JOIN reference_date AS rd
    GROUP BY
        s.customer_id,
        rd.as_of_date
),

-- Stage 3: квартал когорти за першим замовленням
stage3_cohort AS (
    SELECT
        r.*,
        DATE_TRUNC('quarter', r.first_order_date)::DATE AS cohort_quarter
    FROM stage2_rfm AS r
),

-- Stage 4: ковзний середній чек за попередні 30 діб
stage4_rolling_aov AS (
    SELECT
        s.customer_id,
        s.order_id,
        s.order_ts,
        AVG(s.order_total) OVER (
            PARTITION BY s.customer_id
            ORDER BY s.order_ts
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
        )::NUMERIC(12, 2) AS avg_order_value_30d,
        ROW_NUMBER() OVER (
            PARTITION BY s.customer_id
            ORDER BY s.order_ts DESC, s.order_id DESC
        ) AS rn_recent
    FROM stage1_orders_total AS s
),

-- Stage 5: частка скасованих замовлень
stage5_cancel_rate AS (
    SELECT
        customer_id,
        AVG(
            CASE
                WHEN order_status = 'canceled' THEN 1.0
                ELSE 0.0
            END
        )::NUMERIC(6, 4) AS cancellation_rate
    FROM stage1_orders_total
    GROUP BY customer_id
),

-- Stage 6: виручка за категоріями товарів для кожного customer_id
stage6_category_revenue AS (
    SELECT
        o.customer_id,
        COALESCE(p.product_category_name, '(unknown)') AS product_category_name,
        SUM(COALESCE(oi.price, 0) + COALESCE(oi.freight_value, 0))
            ::NUMERIC(12, 2) AS category_revenue
    FROM olist_orders AS o
    JOIN olist_order_items AS oi
        ON oi.order_id = o.order_id
    LEFT JOIN olist_products AS p
        ON p.product_id = oi.product_id
    GROUP BY
        o.customer_id,
        COALESCE(p.product_category_name, '(unknown)')
),

-- Stage 7: top-1 категорія за виручкою з алфавітним tie-break
stage7_preferred_category AS (
    SELECT
        customer_id,
        product_category_name,
        category_revenue
    FROM (
        SELECT
            cr.*,
            ROW_NUMBER() OVER (
                PARTITION BY cr.customer_id
                ORDER BY cr.category_revenue DESC, cr.product_category_name
            ) AS rn
        FROM stage6_category_revenue AS cr
    ) AS ranked
    WHERE rn = 1
),

-- Stage 8: один фінальний рядок для кожного customer_id
stage8_features AS (
    SELECT
        c.customer_id,
        c.customer_state,
        COALESCE(coh.recency_days, 9999) AS recency_days,
        COALESCE(coh.frequency, 0) AS frequency,
        COALESCE(coh.monetary, 0)::NUMERIC(12, 2) AS monetary,
        coh.first_order_date,
        coh.cohort_quarter,
        COALESCE(aov.avg_order_value_30d, 0)::NUMERIC(12, 2)
            AS avg_order_value_30d_recent,
        COALESCE(cancel.cancellation_rate, 0)::NUMERIC(6, 4) AS cancellation_rate,
        COALESCE(pc.product_category_name, '(none)') AS preferred_category,
        COALESCE(pc.category_revenue, 0)::NUMERIC(12, 2)
            AS preferred_category_revenue
    FROM olist_customers AS c
    LEFT JOIN stage3_cohort AS coh
        ON coh.customer_id = c.customer_id
    LEFT JOIN stage4_rolling_aov AS aov
        ON aov.customer_id = c.customer_id
       AND aov.rn_recent = 1
    LEFT JOIN stage5_cancel_rate AS cancel
        ON cancel.customer_id = c.customer_id
    LEFT JOIN stage7_preferred_category AS pc
        ON pc.customer_id = c.customer_id
)
    """

    FEATURE_SQL = CTE_COMMON + """
SELECT
    *
FROM stage8_features
    """

    # Для аналізу показуємо топ-20, проте FEATURE_SQL повертає всі рядки.
    run_sql(FEATURE_SQL + """
ORDER BY
    monetary DESC NULLS LAST,
    customer_id
LIMIT 20;
    """)


def referrals():
    header("Завдання 3. Recursive CTE для referral chain")
    # Завдання 3. Recursive CTE для referral chain

    run_sql("""
DROP TABLE IF EXISTS hw5_referrals CASCADE;

CREATE TABLE hw5_referrals (
    referrer_customer_id TEXT NOT NULL REFERENCES olist_customers(customer_id),
    referred_customer_id TEXT NOT NULL REFERENCES olist_customers(customer_id),
    referred_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (referred_customer_id),
    CHECK (referrer_customer_id <> referred_customer_id)
);

WITH ordered_customers AS (
    SELECT
        customer_id,
        ROW_NUMBER() OVER (
            ORDER BY customer_id
        ) AS rn
    FROM olist_customers
    ORDER BY customer_id
    LIMIT 10
)
INSERT INTO hw5_referrals (
    referrer_customer_id,
    referred_customer_id
)
SELECT
    prev.customer_id AS referrer_customer_id,
    nxt.customer_id AS referred_customer_id
FROM ordered_customers AS prev
JOIN ordered_customers AS nxt
    ON nxt.rn = prev.rn + 1
ON CONFLICT (referred_customer_id)
DO NOTHING;
    """)


def referral_depth():
    header("Завдання 3. Глибина referral chain")
    run_sql("""
WITH RECURSIVE referral_depth AS (
    -- ANCHOR: root customers, які не були referred іншими customers
    SELECT
        c.customer_id,
        1 AS depth,
        ARRAY[c.customer_id]::TEXT[] AS path_ids,
        c.customer_id::TEXT AS path_text
    FROM olist_customers AS c
    WHERE NOT EXISTS (
        SELECT
            1
        FROM hw5_referrals AS r
        WHERE r.referred_customer_id = c.customer_id
    )

    UNION ALL

    -- RECURSIVE: перейти від referrer до його referred customers
    SELECT
        r.referred_customer_id AS customer_id,
        rd.depth + 1 AS depth,
        rd.path_ids || r.referred_customer_id AS path_ids,
        rd.path_text || ' -> ' || r.referred_customer_id AS path_text
    FROM hw5_referrals AS r
    JOIN referral_depth AS rd
        ON rd.customer_id = r.referrer_customer_id
    WHERE NOT r.referred_customer_id = ANY(rd.path_ids)
      AND rd.depth < 50
)
SELECT
    depth,
    COUNT(*) AS n_customers,
    MAX(path_text) AS sample_path
FROM referral_depth
GROUP BY depth
ORDER BY depth;
    """)


def materialized_view():
    header("Завдання 4. Materialized View")
    # Завдання 4. Materialized View з CONCURRENT REFRESH
    run_sql("""
DROP MATERIALIZED VIEW IF EXISTS mv_olist_customer_features CASCADE;
    """)

    run_sql(f"""
CREATE MATERIALIZED VIEW mv_olist_customer_features AS
{FEATURE_SQL};
    """)

    run_sql("""
CREATE UNIQUE INDEX idx_mv_olist_customer_features_customer_id
    ON mv_olist_customer_features (customer_id);
    """)
    run_sql("""
SELECT
    COUNT(*) AS mv_rows
FROM mv_olist_customer_features;
    """)

    run_sql("""
SELECT
    *
FROM mv_olist_customer_features
ORDER BY
    monetary DESC NULLS LAST,
    customer_id
LIMIT 5;
    """)

    with engine.connect() as conn:
        n_mv = conn.execute(text("""
        SELECT COUNT(*)
        FROM mv_olist_customer_features
        """)).scalar_one()
        n_customers = conn.execute(text("""
        SELECT COUNT(*)
        FROM olist_customers
        """)).scalar_one()
        assert n_mv == n_customers, f"MV: {n_mv} рядків, customers: {n_customers}"


def refresh_materialized_view():
    header("Завдання 4. Конкурентне оновлення")
    # Конкурентне оновлення
    run_sql("""
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_olist_customer_features;
    """)

    run_sql("""
SELECT
    COUNT(*) AS rows_after_refresh
FROM mv_olist_customer_features;
    """)


# Завдання 5. EXPLAIN ANALYZE + Reflection

# EXPLAIN виконує запит, але не повертає результатів самого SELECT.
def explain_analyze(query: str,):
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            EXPLAIN (ANALYZE, BUFFERS)
            {query}
        """))
        lines = [str(row[0]) for row in result.fetchall()]
    plan_text = "\n".join(lines)
    return plan_text


def explain_plans():
    # 5.1. Повний feature engineering pipeline
    header("Завдання 5.1. Повний feature engineering pipeline")
    print(explain_analyze(FEATURE_SQL))

    MV_LOOKUP_SQL = """
WITH target_customer AS (
    SELECT
        customer_id
    FROM olist_customers
    ORDER BY customer_id
    LIMIT 1
)
SELECT
    mv.*
FROM mv_olist_customer_features AS mv
JOIN target_customer AS t
    ON t.customer_id = mv.customer_id
    """

    # 5.2. Точкове читання з Materialized View
    header("Завдання 5.2. Точкове читання з Materialized View")
    print(explain_analyze(MV_LOOKUP_SQL))


def main():
    global engine
    pg = pgserver.get_server(PG_DATA_DIR)
    # SQLAlchemy 2.1+ defaults to psycopg 3, the project uses psycopg2
    url = make_url(pg.get_uri()).set(drivername="postgresql+psycopg2")
    engine = create_engine(url)
    try:
        show_version()
        prepare_dataset()
        load_tables()
        smoke_test()
        feature_pipeline()
        referrals()
        referral_depth()
        materialized_view()
        refresh_materialized_view()
        explain_plans()
    finally:
        engine.dispose()
        pg.cleanup()


if __name__ == "__main__":
    main()
