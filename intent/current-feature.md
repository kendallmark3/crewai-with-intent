# Intent: Build a Simple Engineering Recommendation Service

## Business Outcome

Demonstrate how a small CrewAI engineering team can take a human-authored intent and collaboratively produce a useful engineering implementation proposal.

The result should be simple enough to understand in one sitting but complete enough to show the CrewAI operating model.

## Intent

Create an engineering recommendation for a small HTTP service that accepts a software project description and returns three implementation recommendations.

The recommendation should include:

- a proposed architecture
- a minimal API design
- the suggested project structure
- key implementation steps
- testing recommendations
- risks and assumptions

## Inputs

The agents should assume the hypothetical service receives JSON similar to:

```json
{
  "project_name": "Order Status Service",
  "description": "A small internal service that returns order status by order ID.",
  "expected_users": 500,
  "cloud": "AWS"
}
```

## Outputs

Create one final Markdown report containing:

1. interpreted requirements
2. architecture
3. API design
4. implementation approach
5. testing strategy
6. risks and assumptions
7. final reviewer verdict on whether the proposal satisfies this intent

## Success Criteria

The workflow is successful when:

- all four agents execute
- each agent has a clear role
- later agents use the work of earlier agents
- the final report is understandable without reading the Python source
- the final report explicitly checks itself against this intent
- the application writes the final report to `output/final_report.md`

## Boundaries

- Keep this example intentionally small.
- Do not build or deploy the actual HTTP service.
- Do not add a database unless the architecture justifies one.
- Do not add external tools or MCP servers yet.
- Do not use autonomous looping.
- Execute the crew sequentially.
- Prefer clarity over framework sophistication.

## Human / Agent / System Model

### Human
Declares intent, boundaries, inputs, outputs, and success criteria.

### Agents
Interpret, design, plan, and review.

### System
For this starter, the system only writes the final artifact. Future versions should add deterministic tests, hooks, policy checks, and evidence collection.
