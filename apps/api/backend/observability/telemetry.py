from contextlib import contextmanager
from typing import Any, Iterator
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from backend.config import settings

_resource = Resource.create({"service.name": "metrictruth-api", "service.version": "0.1.0"})
_provider = TracerProvider(resource=_resource)
span_exporter = InMemorySpanExporter()
_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("metrictruth.harness")


@contextmanager
def trace_agent_step(
    run_id: str,
    component: str,
    attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    with tracer.start_as_current_span(f"gen_ai.agent.{component}") as span:
        span.set_attribute("metrictruth.run_id", run_id)
        span.set_attribute("gen_ai.agent.name", component)
        if attributes:
            for k, v in attributes.items():
                if not settings.otel_capture_content and k in ("raw_prompt", "raw_completion"):
                    continue
                if v is not None:
                    span.set_attribute(k, str(v) if not isinstance(v, (int, float, bool)) else v)
        yield span

