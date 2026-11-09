from datetime import datetime, time, timedelta
import hashlib
import json
from typing import Any
from pydantic import BaseModel
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    and_,
    bindparam,
    cast,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy.dialects import postgresql, sqlite
from backend.query.plan_schema import MetricQueryPlan, Period, resolve_comparison_period
from backend.semantic.models import CertifiedMetricSpec

view_meta = MetaData()

v_campaigns = Table(
    "v_campaigns",
    view_meta,
    Column("campaign_id", String),
    Column("campaign_name", String),
    Column("channel", String),
    Column("campaign_status", String),
)

v_daily_campaign_performance = Table(
    "v_daily_campaign_performance",
    view_meta,
    Column("id", String),
    Column("campaign_id", String),
    Column("report_date", Date),
    Column("impressions", Integer),
    Column("clicks", Integer),
    Column("spend_usd", Numeric(12, 2)),
    Column("source_batch_id", String),
)

v_customer_acquisitions = Table(
    "v_customer_acquisitions",
    view_meta,
    Column("acquisition_id", String),
    Column("customer_id", String),
    Column("campaign_id", String),
    Column("acquired_at", DateTime),
    Column("attribution_model", String),
    Column("is_valid", Boolean),
    Column("first_order_revenue_usd", Numeric(12, 2)),
    Column("source_batch_id", String),
)


class CompiledQueryArtifact(BaseModel):
    metric_id: str
    metric_version: int
    sql_text: str
    display_sql: str
    bound_params: dict[str, Any]
    tables_accessed: list[str]
    approved_joins: list[str]
    query_fingerprint: str
    current_period: Period
    comparison_period: Period | None


class SQLCompiler:
    def compile(
        self,
        plan: MetricQueryPlan,
        spec: CertifiedMetricSpec,
        dialect_name: str = "postgresql",
    ) -> CompiledQueryArtifact:
        if plan.metric_id != spec.metric_id:
            raise ValueError(f"Plan metric_id '{plan.metric_id}' does not match spec '{spec.metric_id}'.")

        comp_period = resolve_comparison_period(plan.period, plan.comparison.type)
        params: dict[str, Any] = {
            "cur_start_date": plan.period.start_date,
            "cur_end_date": plan.period.end_date,
            "cur_start_ts": datetime.combine(plan.period.start_date, time.min),
            "cur_end_excl_ts": datetime.combine(plan.period.end_date + timedelta(days=1), time.min),
        }

        spend_cur = (
            select(
                v_daily_campaign_performance.c.campaign_id.label("campaign_id"),
                func.coalesce(func.sum(v_daily_campaign_performance.c.spend_usd), 0).label("spend_usd"),
                func.coalesce(func.sum(v_daily_campaign_performance.c.clicks), 0).label("clicks"),
                func.coalesce(func.sum(v_daily_campaign_performance.c.impressions), 0).label("impressions"),
            )
            .where(
                and_(
                    v_daily_campaign_performance.c.report_date >= bindparam("cur_start_date"),
                    v_daily_campaign_performance.c.report_date <= bindparam("cur_end_date"),
                )
            )
            .group_by(v_daily_campaign_performance.c.campaign_id)
            .cte("spend_cur")
        )

        acq_cur_conds = [
            v_customer_acquisitions.c.acquired_at >= bindparam("cur_start_ts"),
            v_customer_acquisitions.c.acquired_at < bindparam("cur_end_excl_ts"),
        ]
        if "invalid_customer_records" in spec.exclusions:
            params["is_valid_req"] = True
            acq_cur_conds.append(v_customer_acquisitions.c.is_valid == bindparam("is_valid_req"))
        if spec.attribution.model == "last_non_direct_paid_click":
            params["attr_model"] = "last_non_direct_paid_click"
            acq_cur_conds.append(v_customer_acquisitions.c.attribution_model == bindparam("attr_model"))

        acq_cur = (
            select(
                v_customer_acquisitions.c.campaign_id.label("campaign_id"),
                func.count(func.distinct(v_customer_acquisitions.c.customer_id)).label("new_customers"),
                func.coalesce(func.sum(v_customer_acquisitions.c.first_order_revenue_usd), 0).label(
                    "revenue_usd"
                ),
            )
            .where(and_(*acq_cur_conds))
            .group_by(v_customer_acquisitions.c.campaign_id)
            .cte("acq_cur")
        )

        if comp_period is not None:
            params["prev_start_date"] = comp_period.start_date
            params["prev_end_date"] = comp_period.end_date
            params["prev_start_ts"] = datetime.combine(comp_period.start_date, time.min)
            params["prev_end_excl_ts"] = datetime.combine(
                comp_period.end_date + timedelta(days=1), time.min
            )

            spend_prev = (
                select(
                    v_daily_campaign_performance.c.campaign_id.label("campaign_id"),
                    func.coalesce(func.sum(v_daily_campaign_performance.c.spend_usd), 0).label("spend_usd"),
                    func.coalesce(func.sum(v_daily_campaign_performance.c.clicks), 0).label("clicks"),
                    func.coalesce(func.sum(v_daily_campaign_performance.c.impressions), 0).label(
                        "impressions"
                    ),
                )
                .where(
                    and_(
                        v_daily_campaign_performance.c.report_date >= bindparam("prev_start_date"),
                        v_daily_campaign_performance.c.report_date <= bindparam("prev_end_date"),
                    )
                )
                .group_by(v_daily_campaign_performance.c.campaign_id)
                .cte("spend_prev")
            )

            acq_prev_conds = [
                v_customer_acquisitions.c.acquired_at >= bindparam("prev_start_ts"),
                v_customer_acquisitions.c.acquired_at < bindparam("prev_end_excl_ts"),
            ]
            if "invalid_customer_records" in spec.exclusions:
                acq_prev_conds.append(v_customer_acquisitions.c.is_valid == bindparam("is_valid_req"))
            if spec.attribution.model == "last_non_direct_paid_click":
                acq_prev_conds.append(v_customer_acquisitions.c.attribution_model == bindparam("attr_model"))

            acq_prev = (
                select(
                    v_customer_acquisitions.c.campaign_id.label("campaign_id"),
                    func.count(func.distinct(v_customer_acquisitions.c.customer_id)).label("new_customers"),
                    func.coalesce(func.sum(v_customer_acquisitions.c.first_order_revenue_usd), 0).label(
                        "revenue_usd"
                    ),
                )
                .where(and_(*acq_prev_conds))
                .group_by(v_customer_acquisitions.c.campaign_id)
                .cte("acq_prev")
            )
        else:
            spend_prev = None
            acq_prev = None

        join_clause = v_campaigns.outerjoin(
            spend_cur, spend_cur.c.campaign_id == v_campaigns.c.campaign_id
        ).outerjoin(acq_cur, acq_cur.c.campaign_id == v_campaigns.c.campaign_id)

        if spend_prev is not None and acq_prev is not None:
            join_clause = join_clause.outerjoin(
                spend_prev, spend_prev.c.campaign_id == v_campaigns.c.campaign_id
            ).outerjoin(acq_prev, acq_prev.c.campaign_id == v_campaigns.c.campaign_id)

        group_cols = []
        if "campaign" in plan.group_by:
            dim_expr = v_campaigns.c.campaign_name.label("dimension_key")
            channel_expr = v_campaigns.c.channel.label("channel")
            group_cols = [v_campaigns.c.campaign_name, v_campaigns.c.channel]
        elif "channel" in plan.group_by:
            dim_expr = v_campaigns.c.channel.label("dimension_key")
            channel_expr = v_campaigns.c.channel.label("channel")
            group_cols = [v_campaigns.c.channel]
        else:
            dim_expr = literal("ALL").label("dimension_key")
            channel_expr = literal("ALL").label("channel")

        cur_spend_sum = func.coalesce(func.sum(spend_cur.c.spend_usd), 0)
        cur_clicks_sum = func.coalesce(func.sum(spend_cur.c.clicks), 0)
        cur_imp_sum = func.coalesce(func.sum(spend_cur.c.impressions), 0)
        cur_cust_sum = func.coalesce(func.sum(acq_cur.c.new_customers), 0)
        cur_rev_sum = func.coalesce(func.sum(acq_cur.c.revenue_usd), 0)

        cur_num_expr = self._measure_expr(
            spec.formula.numerator, cur_spend_sum, cur_clicks_sum, cur_imp_sum, cur_cust_sum, cur_rev_sum
        )
        cur_den_expr = self._measure_expr(
            spec.formula.denominator, cur_spend_sum, cur_clicks_sum, cur_imp_sum, cur_cust_sum, cur_rev_sum
        )
        scale = 100.0 if spec.formula.aggregation == "percentage" else 1.0
        cur_metric_expr = (
            (cast(cur_num_expr, Float) * scale) / func.nullif(cast(cur_den_expr, Float), 0.0)
        ).label("cur_metric_value")

        if spend_prev is not None and acq_prev is not None:
            prev_spend_sum = func.coalesce(func.sum(spend_prev.c.spend_usd), 0)
            prev_clicks_sum = func.coalesce(func.sum(spend_prev.c.clicks), 0)
            prev_imp_sum = func.coalesce(func.sum(spend_prev.c.impressions), 0)
            prev_cust_sum = func.coalesce(func.sum(acq_prev.c.new_customers), 0)
            prev_rev_sum = func.coalesce(func.sum(acq_prev.c.revenue_usd), 0)

            prev_num_expr = self._measure_expr(
                spec.formula.numerator,
                prev_spend_sum,
                prev_clicks_sum,
                prev_imp_sum,
                prev_cust_sum,
                prev_rev_sum,
            )
            prev_den_expr = self._measure_expr(
                spec.formula.denominator,
                prev_spend_sum,
                prev_clicks_sum,
                prev_imp_sum,
                prev_cust_sum,
                prev_rev_sum,
            )
            prev_metric_expr = (
                (cast(prev_num_expr, Float) * scale) / func.nullif(cast(prev_den_expr, Float), 0.0)
            ).label("prev_metric_value")
        else:
            prev_spend_sum = literal(0)
            prev_clicks_sum = literal(0)
            prev_imp_sum = literal(0)
            prev_cust_sum = literal(0)
            prev_rev_sum = literal(0)
            prev_num_expr = literal(0)
            prev_den_expr = literal(0)
            prev_metric_expr = literal(None).label("prev_metric_value")

        where_conds = []
        if "internal_test_campaigns" in spec.exclusions:
            params["active_status"] = "ACTIVE"
            where_conds.append(v_campaigns.c.campaign_status == bindparam("active_status"))

        for fk, fv in plan.filters.items():
            if fk == "channel":
                val = fv[0] if isinstance(fv, list) else fv
                params["filter_channel"] = str(val).upper()
                where_conds.append(v_campaigns.c.channel == bindparam("filter_channel"))
            elif fk == "campaign":
                val = fv[0] if isinstance(fv, list) else fv
                params["filter_campaign"] = str(val)
                where_conds.append(v_campaigns.c.campaign_name == bindparam("filter_campaign"))

        activity_conds = [
            func.coalesce(spend_cur.c.spend_usd, 0) > 0,
            func.coalesce(acq_cur.c.new_customers, 0) > 0,
        ]
        if spend_prev is not None and acq_prev is not None:
            activity_conds.extend(
                [
                    func.coalesce(spend_prev.c.spend_usd, 0) > 0,
                    func.coalesce(acq_prev.c.new_customers, 0) > 0,
                ]
            )
        where_conds.append(or_(*activity_conds))

        stmt = (
            select(
                dim_expr,
                channel_expr,
                cur_spend_sum.label("cur_spend_usd"),
                cur_clicks_sum.label("cur_clicks"),
                cur_imp_sum.label("cur_impressions"),
                cur_cust_sum.label("cur_new_customers"),
                cur_rev_sum.label("cur_revenue_usd"),
                cur_num_expr.label("cur_numerator"),
                cur_den_expr.label("cur_denominator"),
                cur_metric_expr,
                prev_spend_sum.label("prev_spend_usd"),
                prev_clicks_sum.label("prev_clicks"),
                prev_imp_sum.label("prev_impressions"),
                prev_cust_sum.label("prev_new_customers"),
                prev_rev_sum.label("prev_revenue_usd"),
                prev_num_expr.label("prev_numerator"),
                prev_den_expr.label("prev_denominator"),
                prev_metric_expr,
            )
            .select_from(join_clause)
            .where(and_(*where_conds))
        )

        if group_cols:
            stmt = stmt.group_by(*group_cols)

        order_key = plan.order_by[0] if plan.order_by else "metric_desc"
        if order_key == "metric_asc":
            stmt = stmt.order_by(cur_metric_expr.asc(), dim_expr.asc())
        elif order_key == "spend_desc":
            stmt = stmt.order_by(cur_spend_sum.desc(), dim_expr.asc())
        elif order_key == "customers_desc":
            stmt = stmt.order_by(cur_cust_sum.desc(), dim_expr.asc())
        else:
            stmt = stmt.order_by(cur_spend_sum.desc(), dim_expr.asc())

        stmt = stmt.limit(plan.limit)

        target_dialect = (
            sqlite.dialect(paramstyle="named")
            if dialect_name == "sqlite"
            else postgresql.dialect(paramstyle="named")
        )
        compiled_exec = stmt.compile(dialect=target_dialect)
        compiled_pg_display = stmt.compile(dialect=postgresql.dialect(paramstyle="named"))

        sql_text = str(compiled_exec)
        display_sql = str(compiled_pg_display)
        merged_params = {**dict(compiled_exec.params), **params}

        canonical_payload = json.dumps(
            {
                "sql": display_sql,
                "params": {k: str(v) for k, v in sorted(params.items())},
                "metric_id": spec.metric_id,
                "version": spec.version,
            },
            sort_keys=True,
        )
        fingerprint = f"sha256:{hashlib.sha256(canonical_payload.encode('utf-8')).hexdigest()}"

        tables_accessed = ["v_campaigns", "v_daily_campaign_performance"]
        if "customer_acquisitions" in spec.sources:
            tables_accessed.append("v_customer_acquisitions")

        approved_joins = [
            "v_campaigns LEFT JOIN spend_cur ON spend_cur.campaign_id = v_campaigns.campaign_id",
            "v_campaigns LEFT JOIN acq_cur ON acq_cur.campaign_id = v_campaigns.campaign_id",
        ]
        if comp_period is not None:
            approved_joins.extend(
                [
                    "v_campaigns LEFT JOIN spend_prev ON spend_prev.campaign_id = v_campaigns.campaign_id",
                    "v_campaigns LEFT JOIN acq_prev ON acq_prev.campaign_id = v_campaigns.campaign_id",
                ]
            )

        return CompiledQueryArtifact(
            metric_id=spec.metric_id,
            metric_version=spec.version,
            sql_text=sql_text,
            display_sql=display_sql,
            bound_params=merged_params,
            tables_accessed=tables_accessed,
            approved_joins=approved_joins,
            query_fingerprint=fingerprint,
            current_period=plan.period,
            comparison_period=comp_period,
        )

    def _measure_expr(
        self, measure_name: str, spend, clicks, impressions, customers, revenue
    ):
        if measure_name in ("total_paid_media_spend", "total_loaded_acquisition_spend"):
            return spend
        if measure_name in ("paid_attributed_new_customers", "total_valid_new_customers"):
            return customers
        if measure_name == "total_ad_clicks":
            return clicks
        if measure_name == "total_ad_impressions":
            return impressions
        if measure_name == "paid_attributed_revenue":
            return revenue
        raise ValueError(f"Unsupported measure expression: {measure_name}")
