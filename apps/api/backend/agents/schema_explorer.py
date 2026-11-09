from backend.semantic.models import CertifiedMetricSpec
from backend.semantic.relationship_graph import CuratedSchemaContext, build_curated_schema_context


class SchemaExplorer:
    def explore(self, metric_spec: CertifiedMetricSpec) -> CuratedSchemaContext:
        return build_curated_schema_context(metric_spec)

