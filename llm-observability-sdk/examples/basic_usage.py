"""Basic usage example for LLM Observability SDK.

This example demonstrates the core features of the SDK:
1. Backend configuration
2. LLM call instrumentation
3. Nested span hierarchy (agent → retriever → llm)
4. Automatic attribute capture

To run this example:
1. Ensure you have an OTLP-compatible backend running (e.g., Tempo, Jaeger)
2. Update the endpoint in the OTLPAdapter configuration
3. Run: python examples/basic_usage.py
"""

from llm_observability import observe
from llm_observability.adapters import OTLPAdapter


# ============================================================================
# Step 1: Configure Backend (one-time setup)
# ============================================================================

def configure_observability():
    """Configure the SDK to send traces to an OTLP backend."""
    adapter = OTLPAdapter(
        endpoint="http://localhost:4317",  # Update with your endpoint
        protocol="grpc"
    )

    observe.configure(
        adapter=adapter,
        service_name="llm-observability-example",
        service_version="0.1.0",
        deployment_environment="dev"
    )
    print("✅ Observability configured (endpoint: http://localhost:4317)")


# ============================================================================
# Step 2: Instrument Your Functions
# ============================================================================

@observe.retriever(
    name="search_knowledge_base",
    retriever_type="keyword",
    source="mock-db"
)
def search_documents(query: str, limit: int = 5) -> list[str]:
    """Mock retrieval function - simulates searching a knowledge base.

    In a real application, this would query Pinecone, Elasticsearch, etc.
    """
    print(f"   🔍 Searching for: '{query}' (limit: {limit})")

    # Mock results
    results = [
        f"Document about {query} - result 1",
        f"Document about {query} - result 2",
        f"Document about {query} - result 3",
    ]

    print(f"   ✅ Found {len(results)} documents")
    return results


@observe.llm(
    name="generate_answer",
    model="gpt-4o",
    provider="openai",
    temperature=0.7
)
def generate_answer(context: list[str], question: str) -> str:
    """Mock LLM call - simulates calling OpenAI API.

    In a real application, this would call openai.chat.completions.create().
    """
    print(f"   🤖 Generating answer for: '{question}'")
    print(f"   📄 Using {len(context)} context documents")

    # Mock response (in reality, this would call OpenAI)
    answer = f"Based on the context, the answer to '{question}' is: [mock answer]"

    print(f"   ✅ Generated answer: {answer[:50]}...")
    return answer


@observe.agent(
    name="qa_agent",
    agent_type="rag",
    tools=["search_documents", "generate_answer"]
)
def qa_agent(user_question: str) -> str:
    """Question-answering agent using RAG pattern.

    This demonstrates automatic span nesting:
    - qa_agent (agent span)
      ├─ search_documents (retriever span)
      └─ generate_answer (llm span)
    """
    print(f"\n🤖 Agent received question: '{user_question}'")

    # Step 1: Retrieve relevant documents
    print("\n📚 Step 1: Retrieving documents...")
    documents = search_documents(user_question, limit=3)

    # Step 2: Generate answer using LLM
    print("\n💭 Step 2: Generating answer...")
    answer = generate_answer(documents, user_question)

    print(f"\n✅ Agent completed!\n")
    return answer


# ============================================================================
# Step 3: Use Your Instrumented Functions
# ============================================================================

def main():
    """Main example demonstrating the SDK in action."""
    print("=" * 70)
    print("LLM Observability SDK - Basic Usage Example")
    print("=" * 70)

    # Configure observability
    configure_observability()

    # Run the agent (this will create nested spans automatically)
    print("\n" + "-" * 70)
    print("Running QA Agent...")
    print("-" * 70)

    question = "How do I debug Kubernetes pods?"
    answer = qa_agent(question)

    print("\n" + "=" * 70)
    print("Trace Information:")
    print("=" * 70)
    print("""
    ✅ A trace has been sent to your OTLP backend with the following structure:

    span: llm.agent (qa_agent)
    ├─ llm.agent.type: "rag"
    ├─ llm.agent.tools: ["search_documents", "generate_answer"]
    │
    ├─ span: llm.retriever (search_knowledge_base)
    │  ├─ llm.retriever.query: "How do I debug Kubernetes pods?"
    │  ├─ llm.retriever.type: "keyword"
    │  ├─ llm.retriever.source: "mock-db"
    │  ├─ llm.retriever.top_k: 3
    │  └─ llm.retriever.results_count: 3
    │
    └─ span: llm.call (generate_answer)
       ├─ llm.model: "gpt-4o"
       ├─ llm.provider: "openai"
       ├─ llm.temperature: 0.7
       ├─ llm.input.messages: [context + question]
       ├─ llm.output.message: [answer]
       └─ llm.usage.total_tokens: [if available]

    View this trace in your observability backend (Grafana, Jaeger, etc.)
    """)

    print("\n" + "=" * 70)
    print("Example Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
