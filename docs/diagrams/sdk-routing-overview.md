## Moved: SDK Routing Overview (Agnostic Core + Optional Provider Agents)

This diagram now lives under the Layered Modular project:

- See: `docs/projects/layered-modular/diagrams.md`

For convenience, the decision logic is summarized below.

```text
User → SDK Core → Decide (Call | Agent) → Provider Adapter or Provider‑Native Agent Adapter → Normalized events/result
```

Details and full ASCII diagrams are maintained in the project file above.


