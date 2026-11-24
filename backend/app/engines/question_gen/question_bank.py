"""Curated question bank containing technical, behavioral, HR, communication, and presentation questions."""

from typing import Any, Dict, List

SEED_QUESTIONS: List[Dict[str, Any]] = [
    # --------------------------------------------------------------------------
    # TECHNICAL QUESTIONS (Easy, Medium, Hard)
    # --------------------------------------------------------------------------
    {
        "category": "technical",
        "difficulty": "easy",
        "target_roles": ["software_engineer", "backend_developer", "fullstack_developer", "general"],
        "question_text": "Explain the key differences between SQL (relational) and NoSQL databases, and when you would choose one over the other.",
        "expected_duration_seconds": 120,
        "ideal_answer_rubric": "Candidates should define ACID properties in SQL and BASE in NoSQL. They should discuss schema rigidity vs flexibility, vertical vs horizontal scaling, and give concrete use cases (e.g., transactional financial data for SQL vs high-velocity unstructured logging or graph data for NoSQL).",
        "keywords": ["ACID", "relational", "schema", "horizontal scaling", "NoSQL", "transactions", "consistency"],
    },
    {
        "category": "technical",
        "difficulty": "easy",
        "target_roles": ["software_engineer", "backend_developer", "frontend_developer", "general"],
        "question_text": "What is RESTful API architecture, and what are the main HTTP methods and their idempotency characteristics?",
        "expected_duration_seconds": 120,
        "ideal_answer_rubric": "A comprehensive answer explains statelessness, client-server separation, resource-oriented URIs, and details GET, POST, PUT, PATCH, DELETE with accurate explanation of safe vs idempotent operations.",
        "keywords": ["REST", "stateless", "GET", "POST", "PUT", "DELETE", "idempotent", "status codes"],
    },
    {
        "category": "technical",
        "difficulty": "medium",
        "target_roles": ["software_engineer", "backend_developer", "systems_engineer"],
        "question_text": "How does caching work in a distributed system, and how do you handle cache invalidation strategies such as write-through, write-behind, and cache-aside?",
        "expected_duration_seconds": 180,
        "ideal_answer_rubric": "Should cover Redis/Memcached use cases, cache-aside pattern lifecycle, write-through vs write-back latency/durability trade-offs, cache stampede prevention, and TTL-based invalidation strategies.",
        "keywords": ["Redis", "cache-aside", "write-through", "write-behind", "invalidation", "TTL", "cache stampede"],
    },
    {
        "category": "technical",
        "difficulty": "medium",
        "target_roles": ["software_engineer", "backend_developer", "data_engineer"],
        "question_text": "Describe database indexing mechanisms (such as B-Trees and Hash indexes). What are the trade-offs of adding multiple indexes to high-throughput tables?",
        "expected_duration_seconds": 180,
        "ideal_answer_rubric": "Candidate explains B-Tree hierarchical lookup O(log N) vs Hash index O(1) equality, composite indexing order, and the write amplification penalty on INSERT/UPDATE/DELETE operations along with storage overhead.",
        "keywords": ["B-Tree", "Hash index", "read performance", "write overhead", "composite index", "lookup"],
    },
    {
        "category": "technical",
        "difficulty": "hard",
        "target_roles": ["software_engineer", "backend_developer", "systems_architect"],
        "question_text": "How would you design a distributed rate limiter that operates reliably across multiple stateless backend service instances?",
        "expected_duration_seconds": 240,
        "ideal_answer_rubric": "Must evaluate algorithms (Token Bucket, Leaky Bucket, Sliding Window Counter), centralized state storage (Redis Lua scripts to prevent race conditions), resilience against Redis failure, and client response headers (429 Too Many Requests, Retry-After).",
        "keywords": ["Token Bucket", "Sliding Window", "Redis", "Lua script", "atomic", "race conditions", "429"],
    },
    {
        "category": "technical",
        "difficulty": "hard",
        "target_roles": ["software_engineer", "systems_architect"],
        "question_text": "Explain the CAP theorem and the differences between strong consistency and eventual consistency. How would you handle a network partition in a payment processing pipeline?",
        "expected_duration_seconds": 240,
        "ideal_answer_rubric": "Deep breakdown of Consistency, Availability, Partition Tolerance trade-offs. Explains why payment workflows favor consistency (CP), using two-phase commits, idempotency keys, outbox patterns, and saga orchestration.",
        "keywords": ["CAP theorem", "eventual consistency", "strong consistency", "partition tolerance", "two-phase commit", "saga", "idempotency"],
    },

    # --------------------------------------------------------------------------
    # BEHAVIORAL QUESTIONS (Easy, Medium, Hard)
    # --------------------------------------------------------------------------
    {
        "category": "behavioral",
        "difficulty": "easy",
        "target_roles": ["general", "software_engineer", "product_manager"],
        "question_text": "Tell me about a project you are particularly proud of. What was your specific contribution, and what impact did it have?",
        "expected_duration_seconds": 150,
        "ideal_answer_rubric": "Candidate should use the STAR method (Situation, Task, Action, Result), clearly separating their individual contributions from team efforts, and quantifying results (e.g. latency reduced by 40%, user engagement increased).",
        "keywords": ["STAR method", "ownership", "impact", "contribution", "problem solving", "results"],
    },
    {
        "category": "behavioral",
        "difficulty": "medium",
        "target_roles": ["general", "software_engineer", "product_manager"],
        "question_text": "Describe a situation where you had a significant technical disagreement with a team member or lead. How did you handle it and what was the outcome?",
        "expected_duration_seconds": 180,
        "ideal_answer_rubric": "Strong answers demonstrate empathy, active listening, reliance on empirical data and benchmarks rather than ego, collaborative decision-making, and commit-and-deliver alignment once a decision is finalized.",
        "keywords": ["disagreement", "active listening", "data-driven", "collaboration", "compromise", "resolution"],
    },
    {
        "category": "behavioral",
        "difficulty": "medium",
        "target_roles": ["general", "software_engineer", "product_manager"],
        "question_text": "Can you give an example of a time when a project deadline was at risk? What steps did you take to mitigate the risk and communicate with stakeholders?",
        "expected_duration_seconds": 180,
        "ideal_answer_rubric": "Focuses on proactive early communication, scope de-scoping vs deferring, transparent risk assessment, prioritization using critical paths, and avoiding burnout while meeting core business commitments.",
        "keywords": ["deadline", "scope negotiation", "prioritization", "stakeholder communication", "risk mitigation"],
    },
    {
        "category": "behavioral",
        "difficulty": "hard",
        "target_roles": ["general", "software_engineer", "tech_lead"],
        "question_text": "Tell me about a major mistake or production outage you caused or were deeply involved with. How did you respond in the moment, and what long-term preventive measures did you implement?",
        "expected_duration_seconds": 240,
        "ideal_answer_rubric": "Demonstrates extreme ownership, absence of blame-shifting, rapid incident triage and mitigation under pressure, transparent stakeholder alerting, and conducting blameless post-mortems with permanent architectural safeguards.",
        "keywords": ["production outage", "incident triage", "blameless post-mortem", "root cause analysis", "prevention", "monitoring"],
    },

    # --------------------------------------------------------------------------
    # HR QUESTIONS (Easy, Medium, Hard)
    # --------------------------------------------------------------------------
    {
        "category": "hr",
        "difficulty": "easy",
        "target_roles": ["general"],
        "question_text": "What motivated you to apply for this role, and what aspects of our mission and engineering culture resonate most with you?",
        "expected_duration_seconds": 120,
        "ideal_answer_rubric": "Shows genuine research into company domain, alignment between company challenges and candidate's growth goals, enthusiasm for engineering practices, and clear articulation of value add.",
        "keywords": ["motivation", "culture fit", "company mission", "career goals", "value alignment"],
    },
    {
        "category": "hr",
        "difficulty": "medium",
        "target_roles": ["general"],
        "question_text": "Where do you see yourself professionally in the next 3 to 5 years, and what skills or responsibilities are you actively working to develop?",
        "expected_duration_seconds": 150,
        "ideal_answer_rubric": "Realistic and ambition-balanced roadmap showing commitment to continuous learning, progression from individual contributor to senior or technical leadership, and deliberate mentorship goals.",
        "keywords": ["long-term vision", "growth mindset", "leadership", "continuous learning", "mentorship"],
    },
    {
        "category": "hr",
        "difficulty": "hard",
        "target_roles": ["general", "tech_lead", "manager"],
        "question_text": "How do you maintain work-life balance and psychological safety within your team during prolonged high-pressure delivery cycles?",
        "expected_duration_seconds": 180,
        "ideal_answer_rubric": "Discusses setting realistic sprint boundaries, identifying early warning signs of burnout, establishing blameless culture, encouraging open feedback, and protecting focused deep-work time.",
        "keywords": ["psychological safety", "burnout prevention", "work-life balance", "empathy", "sustainable pace"],
    },

    # --------------------------------------------------------------------------
    # COMMUNICATION QUESTIONS (Easy, Medium, Hard)
    # --------------------------------------------------------------------------
    {
        "category": "communication",
        "difficulty": "easy",
        "target_roles": ["general", "software_engineer"],
        "question_text": "How do you explain a complex technical bug or concept to a non-technical customer support or sales representative?",
        "expected_duration_seconds": 120,
        "ideal_answer_rubric": "Avoids jargon, uses intuitive real-world analogies, focuses on business impact and expected user experience, and confirms mutual understanding through active checks.",
        "keywords": ["plain language", "analogies", "business impact", "clarity", "active listening"],
    },
    {
        "category": "communication",
        "difficulty": "medium",
        "target_roles": ["general", "software_engineer", "product_manager"],
        "question_text": "How do you approach giving constructive, critical feedback on a pull request or design document to a colleague without damaging rapport?",
        "expected_duration_seconds": 150,
        "ideal_answer_rubric": "Emphasizes framing feedback around code/architecture rather than personal attributes, phrasing suggestions as questions, highlighting positives, explaining the 'why' behind principles, and offering pairing.",
        "keywords": ["constructive feedback", "code review", "empathy", "objective reasoning", "collaboration"],
    },
    {
        "category": "communication",
        "difficulty": "hard",
        "target_roles": ["general", "software_engineer", "tech_lead"],
        "question_text": "Describe how you would facilitate a cross-functional architectural alignment meeting when product, design, and engineering teams have conflicting priorities.",
        "expected_duration_seconds": 180,
        "ideal_answer_rubric": "Focuses on establishing shared north-star goals, defining clear trade-off matrix (time-to-market vs technical debt), establishing transparent decision criteria (e.g. DACI/RACI), and documenting decisions in ADRs.",
        "keywords": ["cross-functional", "alignment", "trade-off matrix", "decision framework", "ADR", "stakeholders"],
    },

    # --------------------------------------------------------------------------
    # PRESENTATION QUESTIONS (Easy, Medium, Hard)
    # --------------------------------------------------------------------------
    {
        "category": "presentation",
        "difficulty": "easy",
        "target_roles": ["general", "software_engineer", "product_manager"],
        "question_text": "Deliver a 2-minute elevator pitch summarizing a developer tool or software application you admire. What core problem does it solve and why is it compelling?",
        "expected_duration_seconds": 120,
        "ideal_answer_rubric": "Crisp hook, clear definition of the user pain point, concise explanation of the solution, compelling competitive differentiator, and polished, articulate delivery within time limits.",
        "keywords": ["hook", "value proposition", "pain point", "concise delivery", "differentiator"],
    },
    {
        "category": "presentation",
        "difficulty": "medium",
        "target_roles": ["software_engineer", "tech_lead"],
        "question_text": "Present the business and technical trade-offs of migrating a legacy monolithic application to a microservices architecture to senior executives.",
        "expected_duration_seconds": 180,
        "ideal_answer_rubric": "Structures the presentation into Problem -> Options -> Recommendation. Highlights cost, deployment velocity, team independence against operational complexity, distributed observability, and phased migration (Strangler Fig pattern).",
        "keywords": ["monolith vs microservices", "Strangler Fig pattern", "executive summary", "business value", "operational cost"],
    },
    {
        "category": "presentation",
        "difficulty": "hard",
        "target_roles": ["systems_architect", "tech_lead", "engineering_manager"],
        "question_text": "Present a strategic proposal for addressing critical technical debt in a core revenue-generating service while ongoing roadmap feature development is concurrently demanded by leadership.",
        "expected_duration_seconds": 240,
        "ideal_answer_rubric": "High-level strategic pitch demonstrating quantified risk of inaction (outage risk, slowing feature velocity, attrition), proposed 20% budget allocation or parallel refactoring track, milestone-based risk reduction, and ROI measurement.",
        "keywords": ["technical debt", "business case", "risk quantification", "velocity", "ROI", "executive pitch"],
    },
]
